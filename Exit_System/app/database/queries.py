"""Database query classes for different entities"""

import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime

from app.models.vehicle import Vehicle, VehicleOwner
from app.models.parking import ParkingStatus, ParkingLog
from app.models.user import User
from .connection_pool import db_pool

class VehicleQueries:
    """Vehicle-related database queries"""
    
    @staticmethod
    def get_vehicle_info(plate_num: str) -> Optional[Vehicle]:
        """Get vehicle information by plate number"""
        with db_pool.get_connection_context() as conn:
            try:
                cursor = conn.cursor(dictionary=True)
                query = """
                SELECT v.plateNum, v.vehicleType, v.model, v.manufacturer, v.color,
                       vo.OwnerID, vo.fName, vo.lName, vo.mName, vo.role, 
                       vo.college, vo.registrationStatus
                FROM vehicle v
                JOIN vehicleowner vo ON v.OwnerID = vo.OwnerID
                WHERE v.plateNum = %s
                """
                cursor.execute(query, (plate_num,))
                result = cursor.fetchone()
                
                if result:
                    owner = VehicleOwner(
                        owner_id=result['OwnerID'],
                        first_name=result['fName'],
                        last_name=result['lName'],
                        middle_name=result.get('mName'),
                        role=result.get('role', 'guest'),
                        college=result.get('college', 'Unknown'),
                        registration_status=result.get('registrationStatus', 'active')
                    )
                    
                    return Vehicle(
                        plate_num=result['plateNum'],
                        vehicle_type=result['vehicleType'],
                        model=result['model'],
                        manufacturer=result.get('manufacturer'),
                        color=result.get('color'),
                        owner=owner
                    )
                return None
            except Exception as e:
                print(f"Database error in get_vehicle_info: {e}")
                return None
    
    @staticmethod
    def get_vehicle_with_rfid(plate_num: str) -> Optional[Dict[str, Any]]:
        """Get vehicle information including RFID details"""
        with db_pool.get_connection_context() as conn:
            try:
                cursor = conn.cursor(dictionary=True)
                # Clean the plate number to handle spacing issues
                clean_plate = plate_num.replace(' ', '').upper()
                
                query = """
                SELECT v.plateNum, v.vehicleType, v.model, v.manufacturer, v.color,
                       v.stickerID, r.status as rfid_status,
                       vo.OwnerID, vo.fName, vo.lName, vo.mName, vo.role, 
                       vo.college, vo.registrationStatus,
                       vis.fullName as visitor_name, vis.purposeOfVisit
                FROM vehicle v
                LEFT JOIN vehicleowner vo ON v.OwnerID = vo.OwnerID
                LEFT JOIN visitor vis ON v.visitorID = vis.visitorID
                LEFT JOIN rfidtag r ON v.stickerID = r.stickerID
                WHERE REPLACE(UPPER(v.plateNum), ' ', '') = %s 
                   OR UPPER(v.plateNum) = %s
                   OR v.plateNum = %s
                """
                cursor.execute(query, (clean_plate, plate_num.upper(), plate_num))
                result = cursor.fetchone()
                
                if result:
                    owner_name = 'Unknown'
                    if result['fName'] and result['lName']:
                        owner_name = f"{result['fName']} {result['lName']}".strip()
                    elif result.get('visitor_name'):
                        owner_name = result['visitor_name']
                    
                    vehicle_info = f"{result['manufacturer'] or ''} {result['model'] or ''}".strip()
                    if not vehicle_info:
                        vehicle_info = 'Unknown Vehicle'
                    
                    return {
                        'plate': result['plateNum'],
                        'rfid': result['stickerID'] or 'No RFID',
                        'rfid_status': result['rfid_status'] or 'inactive',
                        'owner': owner_name,
                        'vehicle': vehicle_info,
                        'color': result['color'] or 'Unknown',
                        'owner_type': result['role'] or 'visitor',
                        'college': result['college'] or 'N/A',
                        'purpose': result.get('purposeOfVisit', 'N/A')
                    }
                return None
            except Exception as e:
                print(f"Database error in get_vehicle_with_rfid for plate '{plate_num}': {e}")
                return None

class ParkingQueries:
    """Parking-related database queries"""
    
    @staticmethod
    def get_parking_status() -> ParkingStatus:
        """Get current parking status based on today's entries"""
        with db_pool.get_connection_context() as conn:
            try:
                cursor = conn.cursor(dictionary=True)
                
                # Get total capacity
                cursor.execute("SELECT totalCapacity FROM parkingstatus WHERE id = 1")
                capacity_result = cursor.fetchone()
                total_capacity = capacity_result['totalCapacity'] if capacity_result else 200
                
                # Count vehicles currently inside (entered today but not exited)
                cursor.execute("""
                    SELECT COUNT(*) as occupied_count
                    FROM historical_log 
                    WHERE DATE(entryTime) = CURDATE() AND status = 'entered'
                """)
                occupied_result = cursor.fetchone()
                occupied_count = occupied_result['occupied_count'] if occupied_result else 0
                
                current_available = max(0, total_capacity - occupied_count)
                
                return ParkingStatus(
                    total_capacity=total_capacity,
                    current_available=current_available
                )
            except Exception as e:
                print(f"Database error in get_parking_status: {e}")
                return ParkingStatus(total_capacity=200, current_available=200)
    
    @staticmethod
    def get_daily_vehicle_counts() -> Dict[str, int]:
        """Get vehicle type counts for today (currently inside)"""
        with db_pool.get_connection_context() as conn:
            try:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("""
                    SELECT 
                        COALESCE(v.numOfWheels, 4) as numOfWheels, 
                        COUNT(DISTINCT h.plateNum) as count
                    FROM historical_log h
                    LEFT JOIN vehicle v ON h.plateNum = v.plateNum
                    WHERE DATE(h.entryTime) = CURDATE() AND h.status = 'entered'
                    GROUP BY COALESCE(v.numOfWheels, 4)
                """)
                results = cursor.fetchall()
                
                counts = {'2_wheeler': 0, '3_wheeler': 0, '4_wheeler': 0, '6_wheeler': 0}
                for result in results:
                    wheels = result['numOfWheels'] or 4
                    count = result['count']
                    if wheels == 2:
                        counts['2_wheeler'] = count
                    elif wheels == 3:
                        counts['3_wheeler'] = count
                    elif wheels == 4:
                        counts['4_wheeler'] = count
                    elif wheels >= 6:
                        counts['6_wheeler'] = count
                
                return counts
            except Exception as e:
                print(f"Database error in get_daily_vehicle_counts: {e}")
                return {'2_wheeler': 0, '3_wheeler': 0, '4_wheeler': 0, '6_wheeler': 0}
    
    @staticmethod
    def get_daily_allocation_counts() -> Dict[str, int]:
        """Get allocation counts for today (currently inside)"""
        with db_pool.get_connection_context() as conn:
            try:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("""
                    SELECT 
                        COALESCE(LOWER(vo.role), 'guest') as role, 
                        COUNT(DISTINCT h.plateNum) as count
                    FROM historical_log h
                    LEFT JOIN vehicle v ON h.plateNum = v.plateNum
                    LEFT JOIN vehicleowner vo ON v.OwnerID = vo.OwnerID
                    WHERE DATE(h.entryTime) = CURDATE() AND h.status = 'entered'
                    GROUP BY COALESCE(LOWER(vo.role), 'guest')
                """)
                results = cursor.fetchall()
                
                counts = {'student': 0, 'faculty': 0, 'guest': 0}
                for result in results:
                    role = result['role'] or 'guest'
                    count = result['count']
                    if role in ['student', 'faculty']:
                        counts[role] = count
                    else:
                        counts['guest'] += count
                
                return counts
            except Exception as e:
                print(f"Database error in get_daily_allocation_counts: {e}")
                return {'student': 0, 'faculty': 0, 'guest': 0}
    
    @staticmethod
    def log_entry(plate_num: str) -> bool:
        """Log vehicle entry"""
        with db_pool.get_connection_context() as conn:
            try:
                cursor = conn.cursor()
                # Check if vehicle already entered today
                cursor.execute("""
                    SELECT COUNT(*) as count FROM historical_log 
                    WHERE plateNum = %s AND DATE(entryTime) = CURDATE() AND status = 'entered'
                """, (plate_num,))
                result = cursor.fetchone()
                
                if result[0] == 0:  # Not already entered today
                    # Get next log ID number
                    cursor.execute("""
                        SELECT COUNT(*) + 1 as next_id FROM historical_log
                    """)
                    next_id_result = cursor.fetchone()
                    next_id = next_id_result[0] if next_id_result else 1
                    
                    # Format as L001, L002, etc.
                    log_id = f"L{next_id:03d}"
                    
                    cursor.execute("""
                        INSERT INTO historical_log (logID, plateNum, entryTime, status) 
                        VALUES (%s, %s, NOW(), 'entered')
                    """, (log_id, plate_num))
                    conn.commit()
                return True
            except Exception as e:
                print(f"Database error in log_entry: {e}")
                return False
    
    @staticmethod
    def log_exit(plate_num: str) -> bool:
        """Log vehicle exit"""
        with db_pool.get_connection_context() as conn:
            try:
                cursor = conn.cursor()
                
                # Get next exit log ID number
                cursor.execute("""
                    SELECT COUNT(*) + 1 as next_id FROM entryexitlog
                """)
                next_id_result = cursor.fetchone()
                next_id = next_id_result[0] if next_id_result else 1
                
                # Format as L001, L002, etc.
                exit_log_id = f"L{next_id:03d}"
                
                # Move from historical_log to entryexitlog for today's entry
                cursor.execute("""
                    INSERT INTO entryexitlog (logID, plateNum, entryTime, exitTime, status) 
                    SELECT %s, plateNum, entryTime, NOW(), 'exited' 
                    FROM historical_log 
                    WHERE plateNum = %s AND DATE(entryTime) = CURDATE() AND status = 'entered' 
                    ORDER BY entryTime DESC LIMIT 1
                """, (exit_log_id, plate_num))
                
                cursor.execute("""
                    DELETE FROM historical_log 
                    WHERE plateNum = %s AND DATE(entryTime) = CURDATE() AND status = 'entered'
                """, (plate_num,))
                
                conn.commit()
                return True
            except Exception as e:
                print(f"Database error in log_exit: {e}")
                return False

class AccessLogQueries:
    """Access log database queries"""
    
    @staticmethod
    def check_guard_login_status(user_id: str) -> bool:
        """Check if guard is already logged in (has login without logout)"""
        with db_pool.get_connection_context() as conn:
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT action FROM accesslog 
                    WHERE userID = %s AND action IN ('login', 'logout')
                    ORDER BY timestamp DESC LIMIT 1
                """, (user_id,))
                
                result = cursor.fetchone()
                return result and result[0] == 'login'
            except Exception as e:
                print(f"Database error in check_guard_login_status: {e}")
                return False
    
    @staticmethod
    def log_guard_action(user_id: str, action: str, description: str = None) -> bool:
        """Log guard login/logout action"""
        with db_pool.get_connection_context() as conn:
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO accesslog (userID, action, description) 
                    VALUES (%s, %s, %s)
                """, (user_id, action, description))
                
                conn.commit()
                print(f"Access log created: {action} for user {user_id}")
                return True
            except Exception as e:
                print(f"Database error in log_guard_action: {e}")
                return False

class UserQueries:
    """User-related database queries"""
    
    @staticmethod
    def get_user_by_username(username: str) -> Optional[User]:
        """Get user by username"""
        with db_pool.get_connection_context() as conn:
            try:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("""
                    SELECT userID, username, password, role 
                    FROM user 
                    WHERE username = %s AND role = 'guard'
                """, (username,))
                result = cursor.fetchone()
                
                if result:
                    return User(
                        user_id=result['userID'],
                        username=result['username'],
                        password_hash=result['password'],
                        role=result['role']
                    )
                return None
            except Exception as e:
                print(f"Database error in get_user_by_username: {e}")
                return None