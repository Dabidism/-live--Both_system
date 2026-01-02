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
                
                # Get limits from user's schema (allocated* columns)
                cursor.execute("""
                    SELECT totalCapacity, 
                           allocatedStudents, allocatedFaculty, 
                           allocatedStaff, allocatedGuests
                    FROM parkingstatus ORDER BY id ASC LIMIT 1
                """)
                status_result = cursor.fetchone()
                
                total_capacity = status_result['totalCapacity'] if status_result else 200
                allocated_students = status_result['allocatedStudents'] if status_result else 100
                allocated_faculty = status_result['allocatedFaculty'] if status_result else 50
                allocated_staff = status_result['allocatedStaff'] if status_result else 30
                allocated_guests = status_result['allocatedGuests'] if status_result else 20
                
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
                    current_available=current_available,
                    allocated_students=allocated_students,
                    allocated_faculty=allocated_faculty,
                    allocated_staff=allocated_staff,
                    allocated_guests=allocated_guests
                )
            except Exception as e:
                print(f"Database error in get_parking_status: {e}")
                return ParkingStatus(
                    total_capacity=200, 
                    current_available=200,
                    allocated_students=100,
                    allocated_faculty=50,
                    allocated_staff=30,
                    allocated_guests=20
                )
    
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
        """Get allocation counts by role category matching user logic"""
        with db_pool.get_connection_context() as conn:
            try:
                cursor = conn.cursor(dictionary=True)
                # Logic matches user's PHP script
                cursor.execute("""
                    SELECT 
                        CASE 
                            WHEN vo.role = 'student' THEN 'students'
                            WHEN vo.role = 'faculty' THEN 'faculty'
                            WHEN vo.role IN ('non-teaching', 'staff') THEN 'staff'
                            WHEN v.visitorID IS NOT NULL THEN 'guests'
                            ELSE 'guests'
                        END as role_category,
                        COUNT(DISTINCT h.plateNum) as count
                    FROM historical_log h
                    JOIN vehicle v ON h.plateNum = v.plateNum
                    LEFT JOIN vehicleowner vo ON v.OwnerID = vo.OwnerID
                    WHERE DATE(h.entryTime) = CURDATE() AND h.status = 'entered'
                    GROUP BY role_category
                """)
                results = cursor.fetchall()
                
                counts = {'students': 0, 'faculty': 0, 'staff': 0, 'guests': 0}
                for result in results:
                    category = result['role_category']
                    if category in counts:
                        counts[category] = result['count']
                
                # Update DB parkingstatus with current occupancy to keep sync with admin panel
                try:
                     update_cursor = conn.cursor()
                     update_cursor.execute("""
                        UPDATE parkingstatus SET 
                        currentOccupiedStudents = %s,
                        currentOccupiedFaculty = %s,
                        currentOccupiedStaff = %s,
                        currentOccupiedGuests = %s
                        WHERE id = 1
                     """, (counts['students'], counts['faculty'], counts['staff'], counts['guests']))
                     conn.commit()
                except Exception as ex:
                    print(f"Failed to sync parking status table: {ex}")

                return counts
            except Exception as e:
                print(f"Database error in get_daily_allocation_counts: {e}")
                return {'students': 0, 'faculty': 0, 'staff': 0, 'guests': 0}
    
    @staticmethod
    def get_total_registered_vehicles() -> Dict[str, int]:
        """Get total registered vehicles by type"""
        with db_pool.get_connection_context() as conn:
            try:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("""
                    SELECT 
                        COUNT(CASE WHEN vo.role = 'student' THEN 1 END) as students,
                        COUNT(CASE WHEN vo.role IN ('faculty', 'employee', 'non-teaching') THEN 1 END) as faculty,
                        COUNT(CASE WHEN v.visitorID IS NOT NULL THEN 1 END) as visitors
                    FROM vehicle v
                    LEFT JOIN vehicleowner vo ON v.OwnerID = vo.OwnerID
                    WHERE vo.registrationStatus = 'approved' OR v.visitorID IS NOT NULL
                """)
                result = cursor.fetchone()
                return {
                    'students': result['students'] or 0,
                    'faculty': result['faculty'] or 0,
                    'visitors': result['visitors'] or 0
                }
            except Exception as e:
                print(f"Database error in get_total_registered_vehicles: {e}")
                return {'students': 0, 'faculty': 0, 'visitors': 0}
    
    @staticmethod
    def get_rfid_stats() -> Dict[str, int]:
        """Get RFID tag statistics"""
        with db_pool.get_connection_context() as conn:
            try:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(CASE WHEN status = 'active' THEN 1 END) as active,
                        COUNT(CASE WHEN status = 'inactive' THEN 1 END) as inactive
                    FROM rfidtag
                """)
                result = cursor.fetchone()
                return {
                    'total': result['total'] or 0,
                    'active': result['active'] or 0,
                    'inactive': result['inactive'] or 0
                }
            except Exception as e:
                print(f"Database error in get_rfid_stats: {e}")
                return {'total': 0, 'active': 0, 'inactive': 0}
    
    @staticmethod
    def get_application_stats() -> Dict[str, int]:
        """Get application statistics"""
        with db_pool.get_connection_context() as conn:
            try:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(CASE WHEN registrationStatus = 'pending' THEN 1 END) as pending,
                        COUNT(CASE WHEN registrationStatus = 'approved' THEN 1 END) as approved,
                        COUNT(CASE WHEN registrationStatus = 'rejected' THEN 1 END) as rejected
                    FROM applications
                """)
                result = cursor.fetchone()
                return {
                    'total': result['total'] or 0,
                    'pending': result['pending'] or 0,
                    'approved': result['approved'] or 0,
                    'rejected': result['rejected'] or 0
                }
            except Exception as e:
                print(f"Database error in get_application_stats: {e}")
                return {'total': 0, 'pending': 0, 'approved': 0, 'rejected': 0}
    
    @staticmethod
    def get_visitor_pass_stats() -> Dict[str, int]:
        """Get visitor pass statistics"""
        with db_pool.get_connection_context() as conn:
            try:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(CASE WHEN status = 'active' THEN 1 END) as active,
                        COUNT(CASE WHEN status = 'expired' THEN 1 END) as expired,
                        COUNT(CASE WHEN DATE(issueDate) = CURDATE() THEN 1 END) as today
                    FROM temporaryvehiclepass
                """)
                result = cursor.fetchone()
                return {
                    'total': result['total'] or 0,
                    'active': result['active'] or 0,
                    'expired': result['expired'] or 0,
                    'today': result['today'] or 0
                }
            except Exception as e:
                print(f"Database error in get_visitor_pass_stats: {e}")
                return {'total': 0, 'active': 0, 'expired': 0, 'today': 0}
    
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
    
    @staticmethod
    def get_user_stats() -> Dict[str, int]:
        """Get user statistics"""
        with db_pool.get_connection_context() as conn:
            try:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(CASE WHEN role = 'admin' THEN 1 END) as admins,
                        COUNT(CASE WHEN role = 'staff' THEN 1 END) as staff,
                        COUNT(CASE WHEN role = 'guard' THEN 1 END) as guards
                    FROM user
                """)
                result = cursor.fetchone()
                return {
                    'total': result['total'] or 0,
                    'admins': result['admins'] or 0,
                    'staff': result['staff'] or 0,
                    'guards': result['guards'] or 0
                }
            except Exception as e:
                print(f"Database error in get_user_stats: {e}")
                return {'total': 0, 'admins': 0, 'staff': 0, 'guards': 0}

class ViolationQueries:
    """Violation-related database queries"""
    
    @staticmethod
    def get_violation_stats() -> Dict[str, int]:
        """Get violation statistics"""
        with db_pool.get_connection_context() as conn:
            try:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
                        COUNT(CASE WHEN status = 'resolved' THEN 1 END) as resolved,
                        COUNT(CASE WHEN DATE(violationDate) = CURDATE() THEN 1 END) as today
                    FROM violations
                """)
                result = cursor.fetchone()
                return {
                    'total': result['total'] or 0,
                    'pending': result['pending'] or 0,
                    'resolved': result['resolved'] or 0,
                    'today': result['today'] or 0
                }
            except Exception as e:
                print(f"Database error in get_violation_stats: {e}")
                return {'total': 0, 'pending': 0, 'resolved': 0, 'today': 0}



class DashboardQueries:
    """Dashboard-specific aggregated queries"""
    
    @staticmethod
    def get_dashboard_stats() -> Dict[str, Any]:
        """Get all dashboard statistics"""
        try:
            parking_status = ParkingQueries.get_parking_status()
            vehicle_counts = ParkingQueries.get_daily_vehicle_counts()
            allocation_counts = ParkingQueries.get_daily_allocation_counts()
            registered_vehicles = ParkingQueries.get_total_registered_vehicles()
            rfid_stats = ParkingQueries.get_rfid_stats()
            application_stats = ParkingQueries.get_application_stats()
            visitor_stats = ParkingQueries.get_visitor_pass_stats()
            user_stats = UserQueries.get_user_stats()
            
            # Get limits from parking_status object
            student_max = parking_status.allocated_students
            faculty_max = parking_status.allocated_faculty
            staff_max = parking_status.allocated_staff
            guest_max = parking_status.allocated_guests
            
            return {
                'parking': {
                    'total_capacity': parking_status.total_capacity,
                    'current_available': parking_status.current_available,
                    'occupied': parking_status.occupied_count,
                    'occupancy_rate': parking_status.occupancy_rate
                },
                'vehicle_counts': vehicle_counts,
                'allocations': {
                    'students': {'current': allocation_counts['students'], 'max': student_max},
                    'faculty': {'current': allocation_counts['faculty'], 'max': faculty_max},
                    'staff': {'current': allocation_counts['staff'], 'max': staff_max},
                    'guests': {'current': allocation_counts['guests'], 'max': guest_max}
                },
                'registered_vehicles': registered_vehicles,
                'rfid': rfid_stats,
                'applications': application_stats,
                'visitor_passes': visitor_stats,
                'users': user_stats
            }
        except Exception as e:
            print(f"Database error in get_dashboard_stats: {e}")
            return {
                'parking': {'total_capacity': 200, 'current_available': 200, 'occupied': 0, 'occupancy_rate': 0},
                'vehicle_counts': {'2_wheeler': 0, '3_wheeler': 0, '4_wheeler': 0, '6_wheeler': 0},
                'allocations': {'students': {'current': 0, 'max': 20}, 'faculty': {'current': 0, 'max': 160}, 'guests': {'current': 0, 'max': 20}},
                'registered_vehicles': {'students': 0, 'faculty': 0, 'visitors': 0},
                'rfid': {'total': 0, 'active': 0, 'inactive': 0},
                'applications': {'total': 0, 'pending': 0, 'approved': 0, 'rejected': 0},
                'visitor_passes': {'total': 0, 'active': 0, 'expired': 0, 'today': 0},
                'users': {'total': 0, 'admins': 0, 'staff': 0, 'guards': 0}
            }