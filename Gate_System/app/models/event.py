"""Vehicle event models"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime

@dataclass
class VehicleEvent:
    """Vehicle event data model"""
    id: Optional[int] = None
    plate_num: str = ""
    event_type: str = ""  # 'entry' or 'exit'
    event_data: Dict[str, Any] = None
    timestamp: Optional[datetime] = None
    handled: int = 0  # 0 = unhandled, 1 = handled
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'plate_num': self.plate_num,
            'event_type': self.event_type,
            'event_data': self.event_data or {},
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'handled': self.handled
        }