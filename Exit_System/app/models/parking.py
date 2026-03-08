"""Parking-related models"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class ParkingStatus:
    """Parking status data model"""
    total_capacity: int
    current_available: int
    allocated_students: int = 100
    allocated_faculty: int = 50
    allocated_staff: int = 30
    allocated_guests: int = 20
    
    @property
    def occupied_count(self) -> int:
        """Get number of occupied spaces"""
        return self.total_capacity - self.current_available
    
    @property
    def occupancy_rate(self) -> float:
        """Get occupancy rate as percentage"""
        if self.total_capacity == 0:
            return 0.0
        return (self.occupied_count / self.total_capacity) * 100

@dataclass
class ParkingLog:
    """Parking log entry model"""
    log_id: str
    plate_num: str
    entry_time: datetime
    exit_time: Optional[datetime] = None
    status: str = 'entered'
    
    @property
    def duration_minutes(self) -> Optional[int]:
        """Get parking duration in minutes"""
        if self.exit_time and self.entry_time:
            delta = self.exit_time - self.entry_time
            return int(delta.total_seconds() / 60)
        return None