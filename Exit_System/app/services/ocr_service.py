"""OCR service for license plate text recognition"""

import easyocr
import numpy as np
from typing import Optional

from app.config.performance_config import PerformanceConfig
from app.utils.validators import PlateValidator
from app.utils.cache import LRUCache

class OCRService:
    """OCR service for reading license plates"""
    
    def __init__(self, config: Optional[PerformanceConfig] = None):
        self.config = config or PerformanceConfig()
        
        # Initialize EasyOCR with CPU-only and optimized settings
        self.reader = easyocr.Reader(['en'], gpu=False, verbose=False)
        
        # OCR cache
        self.ocr_cache = LRUCache(max_size=20, ttl=5.0)
    
    def read_plate_text(self, plate_image: np.ndarray) -> Optional[str]:
        """Extract text from license plate image"""
        if plate_image is None or plate_image.size == 0:
            return None
        
        # Check cache
        cache_key = str(hash(plate_image.tobytes()))
        cached_result = self.ocr_cache.get(cache_key)
        if cached_result is not None:
            return cached_result
        
        try:
            # Run OCR with optimized settings
            results = self.reader.readtext(
                plate_image,
                detail=True,
                paragraph=False,
                width_ths=0.7,
                height_ths=0.7,
                batch_size=1
            )
            
            best_text = None
            best_confidence = 0
            
            for (bbox, text, confidence) in results:
                if confidence > 0.4:  # Lower OCR confidence for distant plates
                    cleaned_text = PlateValidator.clean_plate_text(text)
                    print(f"Scanned: '{text}' -> '{cleaned_text}' ({confidence:.2f})")
                    
                    if PlateValidator.is_valid_plate(cleaned_text) and confidence > best_confidence:
                        best_text = cleaned_text
                        best_confidence = confidence
            
            # Cache result
            self.ocr_cache.put(cache_key, best_text)
            return best_text
            
        except Exception as e:
            print(f"OCR error: {e}")
            return None