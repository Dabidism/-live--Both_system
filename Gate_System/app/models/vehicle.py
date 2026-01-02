"""Vehicle and VehicleOwner models"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class VehicleOwner:
    """Vehicle owner data model"""
    owner_id: int
    first_name: str
    last_name: str
    middle_name: Optional[str] = None
    role: str = 'guest'
    college: str = 'Unknown'
    registration_status: str = 'active'
    
    @property
    def full_name(self) -> str:
        """Get formatted full name"""
        parts = [self.first_name]
        if self.middle_name:
            parts.append(self.middle_name)
        parts.append(self.last_name)
        return ' '.join(parts).strip()

@dataclass
class Vehicle:
    """Vehicle data model"""
    plate_num: str
    vehicle_type: str
    model: str
    manufacturer: Optional[str] = None
    color: Optional[str] = None
    owner: Optional[VehicleOwner] = None
    
    def categorize_type(self) -> str:
        """Categorize vehicle into standard types"""
        vehicle_type_lower = self.vehicle_type.lower()
        
        if any(x in vehicle_type_lower for x in ['motorcycle', 'bike', 'scooter']):
            return '2_wheeler'
        elif any(x in vehicle_type_lower for x in ['tricycle', 'auto', 'rickshaw']):
            return '3_wheeler'
        elif any(x in vehicle_type_lower for x in ['truck', 'bus', 'lorry']):
            return '6_wheeler'
        else:
            return '4_wheeler'
    
    @property
    def display_name(self) -> str:
        """Get formatted vehicle display name"""
        parts = [self.vehicle_type]
        if self.model:
            parts.append(self.model)
        return ' '.join(parts).strip()