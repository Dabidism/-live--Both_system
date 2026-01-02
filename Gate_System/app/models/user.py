"""User model for authentication"""

from dataclasses import dataclass
from typing import Optional

@dataclass
class User:
    """User data model"""
    user_id: int
    username: str
    password_hash: str
    role: str
    
    def is_guard(self) -> bool:
        """Check if user has guard role"""
        return self.role.lower() == 'guard'
    
    def is_admin(self) -> bool:
        """Check if user has admin role"""
        return self.role.lower() == 'admin'