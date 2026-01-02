"""Event-related database queries"""

import json
from typing import Optional, Dict, Any
from datetime import datetime

from app.models.event import VehicleEvent
from .connection_pool import db_pool

class EventQueries:
    """Event-related database queries"""
    
    @staticmethod
    def create_event_table() -> bool:
        """Create vehicle_events table if it doesn't exist"""
        with db_pool.get_connection_context() as conn:
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS vehicle_events (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        plate_num VARCHAR(20) NOT NULL,
                        event_type ENUM('entry', 'exit') NOT NULL,
                        event_data JSON,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        handled TINYINT DEFAULT 0,
                        INDEX idx_handled_timestamp (handled, timestamp),
                        INDEX idx_plate_timestamp (plate_num, timestamp)
                    )
                """)
                conn.commit()
                return True
            except Exception as e:
                print(f"Database error creating event table: {e}")
                return False
    
    @staticmethod
    def create_event(plate_num: str, event_type: str, event_data: Dict[str, Any]) -> Optional[int]:
        """Create a new vehicle event"""
        with db_pool.get_connection_context() as conn:
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO vehicle_events (plate_num, event_type, event_data, handled)
                    VALUES (%s, %s, %s, 0)
                """, (plate_num, event_type, json.dumps(event_data)))
                conn.commit()
                return cursor.lastrowid
            except Exception as e:
                print(f"Database error creating event: {e}")
                return None
    
    @staticmethod
    def get_latest_unhandled_event() -> Optional[VehicleEvent]:
        """Get the latest unhandled event"""
        with db_pool.get_connection_context() as conn:
            try:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("""
                    SELECT id, plate_num, event_type, event_data, timestamp, handled
                    FROM vehicle_events 
                    WHERE handled = 0 
                    ORDER BY timestamp DESC 
                    LIMIT 1
                """)
                result = cursor.fetchone()
                
                if result:
                    event_data = {}
                    if result['event_data']:
                        try:
                            event_data = json.loads(result['event_data'])
                        except json.JSONDecodeError:
                            event_data = {}
                    
                    return VehicleEvent(
                        id=result['id'],
                        plate_num=result['plate_num'],
                        event_type=result['event_type'],
                        event_data=event_data,
                        timestamp=result['timestamp'],
                        handled=result['handled']
                    )
                return None
            except Exception as e:
                print(f"Database error getting latest event: {e}")
                return None
    
    @staticmethod
    def mark_event_handled(event_id: int) -> bool:
        """Mark an event as handled"""
        with db_pool.get_connection_context() as conn:
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE vehicle_events 
                    SET handled = 1 
                    WHERE id = %s
                """, (event_id,))
                conn.commit()
                return cursor.rowcount > 0
            except Exception as e:
                print(f"Database error marking event handled: {e}")
                return False
    
    @staticmethod
    def get_latest_event() -> Optional[VehicleEvent]:
        """Get the latest event (alias for get_latest_unhandled_event)"""
        return EventQueries.get_latest_unhandled_event()
    
    @staticmethod
    def acknowledge_event(event_id: int) -> bool:
        """Acknowledge an event (alias for mark_event_handled)"""
        return EventQueries.mark_event_handled(event_id)
    
    @staticmethod
    def cleanup_old_events(days: int = 7) -> bool:
        """Clean up events older than specified days"""
        with db_pool.get_connection_context() as conn:
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM vehicle_events 
                    WHERE timestamp < DATE_SUB(NOW(), INTERVAL %s DAY)
                """, (days,))
                conn.commit()
                return True
            except Exception as e:
                print(f"Database error cleaning up events: {e}")
                return False