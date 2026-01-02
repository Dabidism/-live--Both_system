"""Main ANPR service orchestrating detection and processing"""

import cv2
import threading
import time
import os
from typing import Dict, Any, Optional
from datetime import datetime

from app.config.performance_config import PerformanceConfig
from app.services.detection_service import DetectionService
from app.services.ocr_service import OCRService
from app.database.queries import VehicleQueries, ParkingQueries
from app.database.event_queries import EventQueries
from app.models.vehicle import Vehicle
from app.utils.formatters import TextFormatter
from app.utils.cache import LRUCache

class ANPRService:
    """Main ANPR service coordinating all detection and processing"""
    
    def __init__(self, config: Optional[PerformanceConfig] = None):
        self.config = config or PerformanceConfig()
        
        # Services
        self.detection_service = DetectionService(config)
        self.ocr_service = OCRService(config)
        
        # Camera state
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_running = False
        
        # Detection state
        self.detected_plates = LRUCache(max_size=1000, ttl=10)  # Reduced TTL for faster updates
        self.current_vehicle_info: Dict[str, Any] = {}
        
        # Counters (will be refreshed from database)
        self.vehicle_counts = {'2_wheeler': 0, '3_wheeler': 0, '4_wheeler': 0, '6_wheeler': 0}
        self.allocation_counts = {'student': 0, 'faculty': 0, 'guest': 0}
        
        # Performance tracking
        self.last_cleanup = time.time()
    
    def start_camera(self, camera_url: str = None) -> bool:
        """Start camera capture"""
        if self.is_running:
            return True
        
        # Set camera URL based on configuration
        if camera_url is None:
            system_type = os.getenv('SYSTEM_TYPE', 'ENTRY').upper()
            if system_type == 'EXIT':
                camera_url = os.getenv('CAMERA_URL_EXIT', "rtsp://admin:abcd1234@192.168.1.108:554/cam/realmonitor?channel=2&subtype=1")
            else:
                camera_url = os.getenv('CAMERA_URL_ENTRY', "rtsp://admin:abcd1234@192.168.1.108:554/cam/realmonitor?channel=1&subtype=1")
        
        print(f"Starting camera connection to: {camera_url}")
        
        try:
            self.cap = cv2.VideoCapture(camera_url, cv2.CAP_FFMPEG)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, self.config.camera.buffer_size)
            self.cap.set(cv2.CAP_PROP_FPS, self.config.camera.fps)
            
            if self.cap.isOpened():
                self.is_running = True
                print("Camera started successfully.")
                return True
            else:
                print("Failed to open camera: capture is not opened.")
        except Exception as e:
            print(f"Camera start error: {e}")
        
        return False
    
    def stop_camera(self) -> None:
        """Stop camera capture"""
        self.is_running = False
        if self.cap:
            self.cap.release()
    
    def generate_frames(self):
        """Generate processed video frames"""
        frame_count = 0
        
        while self.is_running:
            try:
                ret, frame = self.cap.read()
                if not ret:
                    time.sleep(0.1)
                    continue
                
                # Skip more frames for better performance
                frame_count += 1
                if frame_count % (self.config.skip_frames * 2) != 0:
                    ret, buffer = cv2.imencode('.jpg', frame)
                    frame_bytes = buffer.tobytes()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                    continue
                
                # Process frame
                processed_frame = self.process_frame(frame)
                
                # Encode and yield frame
                ret, buffer = cv2.imencode('.jpg', processed_frame)
                frame_bytes = buffer.tobytes()
                
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                
            except Exception as e:
                print(f"Frame processing error: {e}")
                time.sleep(0.1)
    
    def process_frame(self, frame) -> Any:
        """Process single frame for vehicle and plate detection"""
        # Resize for performance
        h, w = frame.shape[:2]
        if w > self.config.max_processing_width:
            scale = self.config.max_processing_width / w
            frame = cv2.resize(frame, None, fx=scale, fy=scale)
        
        # Detect vehicles - limit to 2 for performance
        vehicles = self.detection_service.detect_vehicles(frame)
        if not vehicles:
            return frame
        
        current_time = time.time()
        
        # Process only first vehicle for better performance
        for vehicle in vehicles[:1]:
            x1, y1, x2, y2 = vehicle['bbox']
            label = vehicle['label']
            
            # Draw vehicle box
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
            cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            
            # Process plates for larger vehicles only
            if (x2 - x1) * (y2 - y1) > 8000:
                self._process_vehicle_plates(frame, vehicle, current_time)
        
        return frame
    
    def _process_vehicle_plates(self, frame, vehicle: Dict[str, Any], current_time: float) -> None:
        """Process plates for a detected vehicle"""
        x1, y1, x2, y2 = vehicle['bbox']
        label = vehicle['label']
        
        vehicle_crop = frame[y1:y2, x1:x2]
        plates = self.detection_service.detect_plates(vehicle_crop)
        
        for plate in plates[:1]:  # Process first plate only
            px1, py1, px2, py2 = plate['bbox']
            plate_x1, plate_y1 = x1 + px1, y1 + py1
            plate_x2, plate_y2 = x1 + px2, y1 + py2
            
            # Draw plate box
            cv2.rectangle(frame, (plate_x1, plate_y1), (plate_x2, plate_y2), (0, 255, 0), 2)
            
            # Extract and process plate
            plate_crop = vehicle_crop[py1:py2, px1:px2]
            processed_plate = self.detection_service.preprocess_plate(plate_crop)
            
            if processed_plate is not None:
                # Process OCR in separate thread
                threading.Thread(
                    target=self._process_ocr,
                    args=(processed_plate, current_time, label),
                    daemon=True
                ).start()
    
    def _process_ocr(self, processed_plate, current_time: float, vehicle_type: str) -> None:
        """Process OCR and handle entry/exit logic with RFID matching"""
        try:
            # Extract text
            text = self.ocr_service.read_plate_text(processed_plate)
            if not text:
                return
            
            # Check for RFID match first
            rfid_match_result = self._check_rfid_match(text)
            
            vehicle_info = VehicleQueries.get_vehicle_with_rfid(text)
            
            self.current_vehicle_info = {
                'plate': text,
                'rfid': vehicle_info.get('rfid', 'N/A') if vehicle_info else 'N/A',
                'owner': vehicle_info.get('owner', 'Unknown') if vehicle_info else 'Unknown',
                'vehicle': vehicle_info.get('vehicle', 'Unknown') if vehicle_info else 'Unknown',
                'color': vehicle_info.get('color', 'Unknown') if vehicle_info else 'Unknown',
                'role': vehicle_info.get('owner_type', 'visitor') if vehicle_info else 'visitor',
                'ownerType': vehicle_info.get('owner_type', 'visitor') if vehicle_info else 'visitor',
                'college': vehicle_info.get('college', 'N/A') if vehicle_info else 'N/A',
                'timestamp': TextFormatter.format_timestamp(),
                'time': TextFormatter.format_timestamp(),
                'date': TextFormatter.format_date(),
                'rfid_match': rfid_match_result
            }
            
            # Check cooldown for entry/exit processing only
            if self.detected_plates.get(text):
                return
            
            # Get basic vehicle info for entry/exit processing
            vehicle = VehicleQueries.get_vehicle_info(text)
            if vehicle:
                is_entry = self._determine_entry_exit(text)
                self._handle_entry_exit_only(vehicle, is_entry)
            
            self.detected_plates.put(text, current_time)
            
            if current_time - self.last_cleanup > 60:
                self._cleanup_old_data()
                self.last_cleanup = current_time
                
        except Exception as e:
            print(f"OCR processing error: {e}")
    
    def _handle_entry_exit_only(self, vehicle: Vehicle, is_entry: bool) -> None:
        """Handle vehicle entry/exit database logging and event creation"""
        system_type = os.getenv('SYSTEM_TYPE', 'ENTRY').upper()
        
        if system_type == 'ENTRY':
            threading.Thread(target=ParkingQueries.log_entry, args=(vehicle.plate_num,), daemon=True).start()
            self.current_vehicle_info['action'] = 'ENTERED'
            
            # Create entry event for popup
            threading.Thread(target=self._create_entry_event, args=(vehicle.plate_num,), daemon=True).start()

        elif system_type == 'EXIT':
            threading.Thread(target=ParkingQueries.log_exit, args=(vehicle.plate_num,), daemon=True).start()
            self.current_vehicle_info['action'] = 'EXITED'
        
        self._refresh_counts()
    
    def _refresh_counts(self) -> None:
        """Refresh counts from database"""
        try:
            self.vehicle_counts = ParkingQueries.get_daily_vehicle_counts()
            self.allocation_counts = ParkingQueries.get_daily_allocation_counts()
        except Exception as e:
            print(f"Error refreshing counts: {e}")
    
    def _determine_entry_exit(self, plate_num: str) -> bool:
        """Determine if this is an entry or exit based on system type"""
        try:
            system_type = os.getenv('SYSTEM_TYPE', 'ENTRY').upper()
            return system_type == 'ENTRY'
        except Exception as e:
            print(f"Error determining entry/exit: {e}")
            return True  # Default to entry
    
    def _cleanup_old_data(self) -> None:
        """Clean up old detection data"""
        # Refresh counts from database
        self._refresh_counts()
    
    def get_current_vehicle_info(self) -> Dict[str, Any]:
        """Get current vehicle information"""
        return self.current_vehicle_info.copy()
    
    def get_vehicle_counts(self) -> Dict[str, int]:
        """Get vehicle type counts from database"""
        try:
            return ParkingQueries.get_daily_vehicle_counts()
        except Exception:
            return {'2_wheeler': 0, '3_wheeler': 0, '4_wheeler': 0, '6_wheeler': 0}
    
    def _create_entry_event(self, plate_num: str) -> None:
        """Create entry event in database for popup display"""
        try:
            # Get current vehicle info for the event
            event_data = self.current_vehicle_info.copy()
            # Ensure all required fields are present
            event_data.update({
                'plate': plate_num,
                'action': 'ENTERED',
                'timestamp': TextFormatter.format_timestamp()
            })
            EventQueries.create_event(plate_num, 'entry', event_data)
            print(f"Created entry event for plate: {plate_num}")
        except Exception as e:
            print(f"Error creating entry event: {e}")
    
    def get_allocation_counts(self) -> Dict[str, Any]:
        """Get allocation counts with limits from database"""
        try:
            status = ParkingQueries.get_parking_status()
            allocation_counts = ParkingQueries.get_daily_allocation_counts()
            
            total_capacity = status.total_capacity
            total_occupied = status.occupied_count
            
            # Use dynamic limits from database (user schema)
            student_max = status.allocated_students
            faculty_max = status.allocated_faculty
            staff_max = status.allocated_staff
            guest_max = status.allocated_guests
            
            return {
                'students': {'current': allocation_counts['students'], 'max': student_max},
                'faculty': {'current': allocation_counts['faculty'], 'max': faculty_max},
                'staff': {'current': allocation_counts['staff'], 'max': staff_max},
                'guests': {'current': allocation_counts['guests'], 'max': guest_max},
                'total_occupied': total_occupied
            }
        except Exception:
            return {
                'students': {'current': 0, 'max': 20},
                'faculty': {'current': 0, 'max': 160},
                'staff': {'current': 0, 'max': 10},
                'guests': {'current': 0, 'max': 20},
                'total_occupied': 0
            }
    
    def _check_rfid_match(self, detected_plate: str) -> Dict[str, Any]:
        """Check if detected plate matches current RFID data"""
        try:
            from app.controllers.web_controller import rfid_service
            if rfid_service:
                return rfid_service.verify_plate_match(detected_plate)
            return {'match': False, 'reason': 'no_rfid_service'}
        except Exception as e:
            print(f"Error checking RFID match: {e}")
            return {'match': False, 'reason': 'error', 'error': str(e)}