"""Performance configuration settings"""

from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass
class CameraSettings:
    """Camera configuration"""
    fps: int = 15
    width: int = 480
    height: int = 360
    buffer_size: int = 1
    fourcc: str = 'MJPG'

@dataclass
class DetectionThresholds:
    """Detection confidence thresholds"""
    vehicle_confidence: float = 0.3
    plate_confidence: float = 0.5  # Higher confidence for Philippine plates
    ocr_confidence: float = 0.4    # Adjusted for Philippine plate format
    min_vehicle_size: int = 25
    min_plate_width: int = 30      # Philippine plates are wider
    min_plate_height: int = 15     # Adjusted for Philippine plate dimensions

@dataclass
class CacheSettings:
    """Caching configuration"""
    vehicle_info_cache_size: int = 500
    detection_cooldown: int = 10
    overlay_display_time: int = 2
    max_overlays: int = 10

@dataclass
class PerformanceConfig:
    """Main performance configuration"""
    camera: CameraSettings = field(default_factory=CameraSettings)
    detection: DetectionThresholds = field(default_factory=DetectionThresholds)
    cache: CacheSettings = field(default_factory=CacheSettings)
    
    # Frame processing
    skip_frames: int = 5
    max_processing_width: int = 480
    
    # Performance monitoring
    enable_gpu: bool = False
    half_precision: bool = False