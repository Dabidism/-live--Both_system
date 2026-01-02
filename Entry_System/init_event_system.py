#!/usr/bin/env python3
"""
Initialize the event handling system by creating the necessary database tables
"""

import mysql.connector
from app.config.database_config import DatabaseConfig

def initialize_event_system():
    """Initialize the event handling database tables"""
    try:
        config = DatabaseConfig()
        conn = mysql.connector.connect(**config.get_connection_params())
        cursor = conn.cursor()
        
        # Create vehicle_events table
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vehicle_events (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    event_type ENUM('ANPR', 'RFID', 'ENTRY', 'EXIT') NOT NULL,
                    plate_num VARCHAR(20) NOT NULL,
                    rfid_code VARCHAR(100),
                    vehicle_data TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    handled TINYINT(1) DEFAULT 0,
                    INDEX idx_handled (handled),
                    INDEX idx_timestamp (timestamp),
                    INDEX idx_plate (plate_num)
                )
            """)
            print("vehicle_events table created/verified")
        except mysql.connector.Error as e:
            if "already exists" not in str(e):
                print(f"Warning: Could not create vehicle_events table: {e}")
            else:
                print("vehicle_events table already exists")
        
        # Add handled column to historical_log if it doesn't exist
        try:
            cursor.execute("ALTER TABLE historical_log ADD COLUMN handled TINYINT(1) DEFAULT 0")
            cursor.execute("ALTER TABLE historical_log ADD INDEX idx_handled (handled)")
        except mysql.connector.Error as e:
            if "Duplicate column name" not in str(e):
                print(f"Warning: Could not add handled column to historical_log: {e}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("Event handling system initialized successfully!")
        
    except Exception as e:
        print(f"Error initializing event system: {e}")

if __name__ == '__main__':
    initialize_event_system()