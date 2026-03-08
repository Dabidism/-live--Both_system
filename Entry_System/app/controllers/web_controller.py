"""Web controller for Flask application"""

import os
import logging
from functools import wraps
from flask import Flask, render_template, Response, jsonify, request, redirect, url_for, session
from typing import Optional

from app.services.anpr_service import ANPRService
from app.services.auth_service import AuthService
from app.services.rfid_service import RFIDService
from app.database.queries import ParkingQueries, AccessLogQueries, VehicleQueries, UserQueries
from app.database.event_queries import EventQueries
from app.config.performance_config import PerformanceConfig

# Global service instances
anpr_service: Optional[ANPRService] = None
rfid_service: Optional[RFIDService] = None

def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'guard_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def create_app() -> Flask:
    """Create and configure Flask application"""
    app = Flask(__name__, 
                template_folder='../../templates',
                static_folder='../../static')
    
    # Disable request logging to reduce console spam
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    
    # Configuration
    app.secret_key = os.getenv('SECRET_KEY', 'default_insecure_secret_key_change_me')
    app.config['SESSION_COOKIE_NAME'] = 'entry_system_session'
    
    # Initialize services
    global anpr_service, rfid_service
    config = PerformanceConfig()
    anpr_service = ANPRService(config)
    rfid_service = RFIDService()
    
    # Start RFID scanning with callback if enabled
    if os.getenv('RFID_ENABLED', 'true').lower() == 'true':
        rfid_service.start_scanning(callback=_handle_rfid_detection)
    
    # Register routes
    register_auth_routes(app)
    register_api_routes(app)
    register_main_routes(app)
    
    return app

def _handle_rfid_detection(rfid_data: dict) -> None:
    """Handle RFID detection callback"""
    print(f"RFID detected: {rfid_data.get('rfid_code', 'Unknown')}")
    # RFID data is stored in the service, will be retrieved by API calls

def register_auth_routes(app: Flask) -> None:
    """Register authentication routes"""
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form.get('guard_id', '').strip()
            password = request.form.get('password', '')
            
            if not username or not password:
                return render_template('login.html', error='Please provide both username and password')
            
            user = AuthService.authenticate_guard(username, password)
            if user:
                session['guard_id'] = user.user_id
                session['username'] = user.username
                
                # Determine guard type based on configured system type
                system_type = os.getenv('SYSTEM_TYPE', 'ENTRY').upper()
                session['guard_type'] = f"{system_type.capitalize()} System"
                
                description = f'{session["guard_type"]} - Guard {user.username} logged in successfully'
                AccessLogQueries.log_guard_action(user.user_id, 'login', description)
                return redirect(url_for('index'))
            else:
                # Check if credentials are valid but user is already logged in
                temp_user = UserQueries.get_user_by_username(username)
                if temp_user and temp_user.is_guard() and AuthService.verify_password(password, temp_user.password_hash):
                    print(f"Valid credentials for {username}, checking login status...")
                    if AccessLogQueries.check_guard_login_status(temp_user.user_id):
                        print(f"User {username} is already logged in")
                        return render_template('login.html', error='User is already logged in from another session. Please logout first.')
                print(f"Authentication failed for {username}")
                return render_template('login.html', error='Invalid credentials or insufficient permissions')
        
        return render_template('login.html')
    
    @app.route('/logout')
    def logout():
        guard_id = session.get('guard_id')
        username = session.get('username', 'unknown')
        
        if guard_id:
            try:
                guard_type = session.get('guard_type', 'Unknown System')
                AccessLogQueries.log_guard_action(guard_id, 'logout', f'{guard_type} - Guard {username} logged out')
            except Exception as e:
                print(f"Error logging logout: {e}")
        
        session.clear()
        return redirect(url_for('login'))

def register_main_routes(app: Flask) -> None:
    """Register main application routes"""
    
    @app.route('/')
    @login_required
    def index():
        # Check if running on exit port to show exit dashboard
        system_type = os.getenv('SYSTEM_TYPE', 'ENTRY').upper()
        if system_type == 'EXIT':
            return render_template('exit_dashboard.html', guard_id=session.get('username', session['guard_id']))
        return render_template('dashboard.html', guard_id=session.get('username', session['guard_id']))
    
    @app.route('/exit')
    @login_required
    def exit_dashboard():
        # Force exit dashboard view if explicitly requested? 
        # Or maybe this route should be deprecated if we are unifying logic?
        # Keeping it for backward compatibility but using the unified template
        return render_template('exit_dashboard.html', guard_id=session.get('username', session['guard_id']))
    
    @app.route('/video_feed')
    @login_required
    def video_feed():
        if not anpr_service.is_running:
            anpr_service.start_camera()
        
        return Response(anpr_service.generate_frames(),
                       mimetype='multipart/x-mixed-replace; boundary=frame')

def register_api_routes(app: Flask) -> None:
    """Register API routes"""
    
    @app.route('/api/dashboard')
    @login_required
    def get_dashboard():
        try:
            # Get vehicle info
            vehicle_info = anpr_service.get_current_vehicle_info()

            # Get parking status
            status = ParkingQueries.get_parking_status()
            
            # Get vehicle counts
            vehicle_counts = anpr_service.get_vehicle_counts()
            
            # Get allocation counts
            allocation_counts = anpr_service.get_allocation_counts()
            
            return jsonify({
                'vehicle_info': vehicle_info,
                'dashboard_stats': {
                    'parking': {
                        'total_capacity': status.total_capacity,
                        'current_available': status.current_available,
                        'occupied': status.occupied_count,
                        'occupancy_rate': status.occupancy_rate
                    },
                    'vehicle_counts': vehicle_counts,
                    'allocations': allocation_counts
                }
            })
        except Exception as e:
            print(f"Dashboard API error: {e}")
            return jsonify({'error': 'Internal server error'}), 500
    
    @app.route('/api/vehicle_info')
    @login_required
    def get_vehicle_info():
        try:
            vehicle_info = anpr_service.get_current_vehicle_info()
            return jsonify({'vehicle_info': vehicle_info})
        except Exception as e:
            return jsonify({'vehicle_info': {}})
    
    @app.route('/api/start_camera')
    @login_required
    def start_camera():
        try:
            success = anpr_service.start_camera()
            return jsonify({'success': success})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
    
    @app.route('/api/vehicle/<plate_num>')
    @login_required
    def get_vehicle_details(plate_num):
        try:
            vehicle_info = VehicleQueries.get_vehicle_with_rfid(plate_num)
            if vehicle_info:
                return jsonify(vehicle_info)
            else:
                return jsonify({'error': 'Vehicle not found'}), 404
        except Exception as e:
            return jsonify({'error': 'Internal server error'}), 500
    
    @app.route('/api/rfid_status')
    @login_required
    def get_rfid_status():
        try:
            rfid_data = rfid_service.get_current_rfid_data() if rfid_service else None
            return jsonify({
                'rfid_active': rfid_service.is_running if rfid_service else False,
                'current_rfid': rfid_data
            })
        except Exception as e:
            return jsonify({'rfid_active': False, 'current_rfid': None})
    
    @app.route('/api/clear_rfid', methods=['POST'])
    @login_required
    def clear_rfid():
        try:
            if rfid_service:
                rfid_service.clear_current_rfid()
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
    
    @app.route('/api/latest_event')
    @login_required
    def get_latest_event():
        try:
            event = EventQueries.get_latest_unhandled_event()
            if event:
                return jsonify({'event': event.to_dict()})
            else:
                return jsonify({'event': None})
        except Exception as e:
            print(f"Error getting latest event: {e}")
            return jsonify({'event': None})
    
    @app.route('/api/ack_event', methods=['POST'])
    @login_required
    def acknowledge_event():
        try:
            data = request.get_json()
            event_id = data.get('event_id')
            if event_id:
                success = EventQueries.mark_event_handled(event_id)
                return jsonify({'success': success})
            else:
                return jsonify({'success': False, 'error': 'Missing event_id'})
        except Exception as e:
            print(f"Error acknowledging event: {e}")
            return jsonify({'success': False, 'error': str(e)})
