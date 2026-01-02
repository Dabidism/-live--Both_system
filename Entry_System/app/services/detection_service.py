"""Vehicle and plate detection service"""

import cv2
import numpy as np
from ultralytics import YOLO
import threading
import time
from typing import List, Dict, Any, Optional, Tuple

from app.config.performance_config import PerformanceConfig
from app.utils.cache import LRUCache

class DetectionService:
    """Vehicle and license plate detection service"""
    
    def __init__(self, config: Optional[PerformanceConfig] = None):
        self.config = config or PerformanceConfig()
        
        # Load models with CPU-only configuration
        self.vehicle_model = YOLO("models/yolov8n.pt")
        self.plate_model = YOLO("models/best.pt")  # Philippine plates trained model
        
        # Configure models for CPU-only operation
        self.vehicle_model.to('cpu')
        self.plate_model.to('cpu')
        
        # Detection cache
        self.detection_cache = LRUCache(max_size=50, ttl=2.0)
        
    def detect_vehicles(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Detect vehicles in frame"""
        if frame is None or frame.size == 0:
            return []
        
        # Resize for performance
        h, w = frame.shape[:2]
        if w > 416:
            scale = 416 / w
            small_frame = cv2.resize(frame, None, fx=scale, fy=scale)
        else:
            small_frame = frame
            scale = 1.0
        
        # Run detection with CPU-optimized settings
        results = self.vehicle_model(
            small_frame, 
            verbose=False, 
            conf=self.config.detection.vehicle_confidence,
            imgsz=416,
            device='cpu'
        )
        
        vehicles = []
        if results[0].boxes:
            for box in results[0].boxes:
                cls = int(box.cls)
                label = self.vehicle_model.names[cls]
                
                if label.lower() in ["car", "motorcycle"]:
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                    
                    # Scale back to original size
                    x1, y1, x2, y2 = int(x1/scale), int(y1/scale), int(x2/scale), int(y2/scale)
                    
                    # Filter by minimum size
                    if (x2 - x1) > 80 and (y2 - y1) > 60:
                        vehicles.append({
                            'bbox': (x1, y1, x2, y2),
                            'label': label,
                            'confidence': float(box.conf)
                        })
        
        return vehicles
    
    def detect_plates(self, vehicle_crop: np.ndarray) -> List[Dict[str, Any]]:
        """Detect license plates in vehicle crop"""
        if vehicle_crop is None or vehicle_crop.size == 0:
            return []
        
        # Check cache
        cache_key = str(hash(vehicle_crop.tobytes()))
        cached_result = self.detection_cache.get(cache_key)
        if cached_result is not None:
            return cached_result
        
        # Resize for optimal performance with Philippine plates
        h, w = vehicle_crop.shape[:2]
        if w > 416:
            scale = 416 / w
            small_crop = cv2.resize(vehicle_crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
        else:
            small_crop = vehicle_crop
            scale = 1.0
        
        # Run plate detection with optimized settings
        results = self.plate_model(
            small_crop,
            verbose=False,
            conf=self.config.detection.plate_confidence,
            imgsz=416,  # Slightly larger for better accuracy
            device='cpu',
            half=False,  # Ensure no half precision issues
            augment=False  # Disable augmentation for speed
        )
        
        plates = []
        if results[0].boxes:
            for box in results[0].boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                
                # Scale back
                x1, y1, x2, y2 = int(x1/scale), int(y1/scale), int(x2/scale), int(y2/scale)
                
                # Validate plate size for Philippine plates
                plate_width = x2 - x1
                plate_height = y2 - y1
                aspect_ratio = plate_width / plate_height if plate_height > 0 else 0
                
                # Philippine plates typically have aspect ratio between 2.5-4.0
                if (plate_width > self.config.detection.min_plate_width and 
                    plate_height > self.config.detection.min_plate_height and
                    2.0 <= aspect_ratio <= 5.0):
                    plates.append({
                        'bbox': (x1, y1, x2, y2),
                        'confidence': float(box.conf)
                    })
        
        # Cache result
        self.detection_cache.put(cache_key, plates)
        return plates
    
    def preprocess_plate(self, plate_crop: np.ndarray) -> Optional[np.ndarray]:
        """Preprocess plate image for OCR"""
        if plate_crop is None or plate_crop.size == 0:
            return None
        
        # Convert to grayscale
        if len(plate_crop.shape) == 3:
            gray = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY)
        else:
            gray = plate_crop
        
        # Resize if too small
        h, w = gray.shape
        if w < 100 or h < 25:
            scale = max(2.0, 100/w, 25/h)
            gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        
        # Apply threshold
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        return thresh