"""Validation utilities"""

import re
from typing import List

class PlateValidator:
    """License plate validation utilities"""
    
    # Common plate patterns
    PATTERNS = [
        r'^[A-Z]{2,3}\d{3,4}$',  # AB123, ABC1234
        r'^\d{3}[A-Z]{2,3}$',    # 123AB, 123ABC
        r'^[A-Z]{2}\d{2}[A-Z]{2}$',  # AB12CD
    ]
    
    @classmethod
    def is_valid_plate(cls, text: str) -> bool:
        """Validate if text matches plate patterns"""
        if not text or len(text) < 4 or len(text) > 8:
            return False
        
        # Must have both letters and numbers
        has_letter = any(c.isalpha() for c in text)
        has_digit = any(c.isdigit() for c in text)
        
        if not (has_letter and has_digit):
            return False
        
        # Check against patterns
        return any(re.match(pattern, text) for pattern in cls.PATTERNS)
    
    @classmethod
    def clean_plate_text(cls, text: str) -> str:
        """Clean and normalize plate text"""
        # Remove non-alphanumeric and convert to uppercase
        cleaned = re.sub(r'[^A-Z0-9]', '', text.upper())
        
        # Basic OCR corrections
        corrections = {'O': '0', 'I': '1', 'S': '5', 'Z': '2'}
        for old, new in corrections.items():
            cleaned = cleaned.replace(old, new)
        
        return cleaned