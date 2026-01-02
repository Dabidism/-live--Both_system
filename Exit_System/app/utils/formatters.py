"""Text formatting utilities"""

from datetime import datetime
from typing import Optional

class TextFormatter:
    """Text formatting utilities"""
    
    @staticmethod
    def format_timestamp(dt: Optional[datetime] = None) -> str:
        """Format timestamp for display"""
        if dt is None:
            dt = datetime.now()
        return dt.strftime('%H:%M:%S')
    
    @staticmethod
    def format_date(dt: Optional[datetime] = None) -> str:
        """Format date for display"""
        if dt is None:
            dt = datetime.now()
        return dt.strftime('%Y-%m-%d')
    
    @staticmethod
    def format_full_name(first: str, last: str, middle: Optional[str] = None) -> str:
        """Format full name from components"""
        parts = [first]
        if middle:
            parts.append(middle)
        parts.append(last)
        return ' '.join(parts).strip()
    
    @staticmethod
    def format_vehicle_display(vehicle_type: str, model: Optional[str] = None) -> str:
        """Format vehicle display name"""
        parts = [vehicle_type]
        if model:
            parts.append(model)
        return ' '.join(parts).strip()