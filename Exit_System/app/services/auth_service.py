"""Authentication service"""

import bcrypt
from typing import Optional

from app.models.user import User
from app.database.queries import UserQueries

class AuthService:
    """Authentication service for user login"""
    
    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Verify password against hash"""
        try:
            # Handle PHP bcrypt format compatibility
            if hashed.startswith('$2y$'):
                python_hash = '$2b$' + hashed[4:]
            else:
                python_hash = hashed
            
            return bcrypt.checkpw(password.encode('utf-8'), python_hash.encode('utf-8'))
        except Exception as e:
            print(f"Password verification error: {e}")
            return False
    
    @staticmethod
    def authenticate_guard(username: str, password: str) -> Optional[User]:
        """Authenticate guard user"""
        try:
            user = UserQueries.get_user_by_username(username)
            
            if user and user.is_guard():
                if AuthService.verify_password(password, user.password_hash):
                    # Check if user is already logged in
                    from app.database.queries import AccessLogQueries
                    if AccessLogQueries.check_guard_login_status(user.user_id):
                        return None  # User already logged in
                    return user
                else:
                    print(f"Password verification failed for {username}")
            else:
                print(f"No guard user found with username: {username}")
            
            return None
        except Exception as e:
            print(f"Authentication error: {e}")
            return None