"""RFID service for scanning and matching RFID tags with vehicle data"""

import serial
import threading
import time
from typing import Optional, Dict, Any, Callable
from datetime import datetime

from app.database.queries import VehicleQueries

class RFIDService:
    """Service for handling RFID scanning and vehicle matching"""
    
    def __init__(self, port: str = 'COM9', baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self.serial_connection: Optional[serial.Serial] = None
        self.is_running = False
        self.scanning_thread: Optional[threading.Thread] = None
        
        # Current RFID state
        self.current_rfid_data: Optional[Dict[str, Any]] = None
        self.last_rfid_code = ""
        self.rfid_callback: Optional[Callable] = None
        
    def start_scanning(self, callback: Optional[Callable] = None) -> bool:
        """Start RFID scanning"""
        if self.is_running:
            return True
            
        try:
            self.serial_connection = serial.Serial(self.port, self.baudrate, timeout=1)
            self.is_running = True
            self.rfid_callback = callback
            
            self.scanning_thread = threading.Thread(target=self._scan_loop, daemon=True)
            self.scanning_thread.start()
            
            print(f"RFID Scanner started on {self.port}")
            return True
        except Exception as e:
            print(f"Failed to start RFID scanner: {e}")
            return False
    
    def stop_scanning(self) -> None:
        """Stop RFID scanning"""
        self.is_running = False
        if self.serial_connection:
            self.serial_connection.close()
        print("RFID Scanner stopped")
    
    def _scan_loop(self) -> None:
        """Main RFID scanning loop"""
        while self.is_running:
            try:
                if self.serial_connection and self.serial_connection.in_waiting > 0:
                    data = self.serial_connection.read(self.serial_connection.in_waiting)
                    if data:
                        epc_hex = data.hex().upper()
                        
                        if len(epc_hex) >= 50:
                            epc_clean = epc_hex[:50]
                            
                            if epc_clean != self.last_rfid_code:
                                print(f"RFID Detected: {epc_clean}")
                                self._process_rfid(epc_clean)
                                self.last_rfid_code = epc_clean
                
                time.sleep(0.1)
            except Exception as e:
                print(f"RFID scanning error: {e}")
                time.sleep(1)
    
    def _process_rfid(self, rfid_code: str) -> None:
        """Process detected RFID code"""
        try:
            # Get vehicle info by RFID
            vehicle_info = self._get_vehicle_by_rfid(rfid_code)
            
            if vehicle_info:
                self.current_rfid_data = {
                    'rfid_code': rfid_code,
                    'plate': vehicle_info['plateNum'],
                    'owner': f"{vehicle_info['fName']} {vehicle_info['lName']}".strip(),
                    'vehicle': f"{vehicle_info['manufacturer']} {vehicle_info['model']}".strip(),
                    'color': vehicle_info['color'],
                    'owner_type': vehicle_info['role'],
                    'college': vehicle_info['college'],
                    'rfid_status': vehicle_info['rfid_status'],
                    'timestamp': datetime.now().strftime('%I:%M %p'),
                    'date': datetime.now().strftime('%Y-%m-%d'),
                    'status': 'waiting_for_plate'  # Waiting for camera to scan plate
                }
                
                print(f"RFID matched to vehicle: {vehicle_info['plateNum']}")
                
                # Call callback if provided
                if self.rfid_callback:
                    self.rfid_callback(self.current_rfid_data)
            else:
                self.current_rfid_data = {
                    'rfid_code': rfid_code,
                    'status': 'no_match',
                    'timestamp': datetime.now().strftime('%I:%M %p')
                }
                print(f"No vehicle found for RFID: {rfid_code}")
        except Exception as e:
            print(f"Error processing RFID: {e}")
    
    def _get_vehicle_by_rfid(self, rfid_code: str) -> Optional[Dict[str, Any]]:
        """Get vehicle and owner info by RFID code"""
        try:
            from app.database.connection_pool import db_pool
            
            with db_pool.get_connection_context() as conn:
                cursor = conn.cursor(dictionary=True)
                
                query = """
                SELECT v.plateNum, v.vehicleType, v.model, v.manufacturer, v.color,
                       vo.fName, vo.lName, vo.role, vo.college, vo.registrationStatus,
                       r.status as rfid_status, r.expirationDate
                FROM vehicle v
                LEFT JOIN vehicleowner vo ON v.OwnerID = vo.OwnerID
                LEFT JOIN rfidtag r ON v.stickerID = r.stickerID
                WHERE r.rfidCode = %s
                """
                
                cursor.execute(query, (rfid_code,))
                result = cursor.fetchone()
                
                return result
        except Exception as e:
            print(f"Database error in _get_vehicle_by_rfid: {e}")
            return None
    
    def get_current_rfid_data(self) -> Optional[Dict[str, Any]]:
        """Get current RFID data"""
        return self.current_rfid_data.copy() if self.current_rfid_data else None
    
    def clear_current_rfid(self) -> None:
        """Clear current RFID data"""
        self.current_rfid_data = None
        self.last_rfid_code = ""
    
    def verify_plate_match(self, detected_plate: str) -> Dict[str, Any]:
        """Verify if detected plate matches current RFID data"""
        if not self.current_rfid_data:
            return {'match': False, 'reason': 'no_rfid_data'}
        
        expected_plate = self.current_rfid_data.get('plate', '').replace(' ', '').upper()
        detected_plate_clean = detected_plate.replace(' ', '').upper()
        
        if expected_plate == detected_plate_clean:
            # Update status to matched
            self.current_rfid_data['status'] = 'matched'
            return {
                'match': True,
                'rfid_data': self.current_rfid_data,
                'message': 'RFID and plate match confirmed'
            }
        else:
            return {
                'match': False,
                'reason': 'plate_mismatch',
                'expected': expected_plate,
                'detected': detected_plate_clean,
                'message': f'Plate mismatch: Expected {expected_plate}, got {detected_plate_clean}'
            }