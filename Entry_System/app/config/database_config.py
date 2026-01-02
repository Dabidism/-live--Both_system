"""Database configuration with secure connection handling"""

import os
from typing import Dict, Any
from dataclasses import dataclass
import mysql.connector
from mysql.connector import Error

@dataclass
class DatabaseConfig:
    """Database configuration settings"""
    host: str = os.getenv('DB_HOST', 'localhost')
    user: str = os.getenv('DB_USER', 'root')
    password: str = os.getenv('DB_PASSWORD', '')
    database: str = os.getenv('DB_NAME', 'gate_pass_system')
    port: int = int(os.getenv('DB_PORT', '3306'))
    
    def get_connection_params(self) -> Dict[str, Any]:
        """Get connection parameters as dictionary"""
        return {
            'host': self.host,
            'user': self.user,
            'password': self.password,
            'database': self.database,
            'port': self.port,
            'autocommit': False,
            'raise_on_warnings': True
        }

def create_connection() -> mysql.connector.MySQLConnection:
    """Create database connection with proper error handling"""
    config = DatabaseConfig()
    
    try:
        connection = mysql.connector.connect(**config.get_connection_params())
        if connection.is_connected():
            return connection
    except Error as e:
        raise ConnectionError(f"Database connection failed: {e}")
    
    raise ConnectionError("Failed to establish database connection")