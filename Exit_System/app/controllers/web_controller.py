"""Web controller for Flask application"""

import os
import logging
from flask import Flask, render_template, Response, jsonify, request, redirect, url_for, session
from typing import Optional

from app.services.anpr_service import ANPRService
from app.services.auth_service import AuthService

from app.database.queries import ParkingQueries, AccessLogQueries, VehicleQueries, UserQueries
from app.database.event_queries import EventQueries
from app.config.performance_config import PerformanceConfig

# Global service instances
anpr_service: Optional[ANPRService] = None

def create_app() -> Flask:
    """Create and configure Flask application"""
    app = Flask(__name__, 
                template_folder='../../templates',
                static_folder='../../static')
    
    # Disable request logging to reduce console spam
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    
    # Configuration
    app.secret_key = os.getenv('SECRET_KEY', 'anpr_guard_system_2024')
    
    # Initialize services
    global anpr_service
    config = PerformanceConfig()
    anpr_service = ANPRService(config)
    
    # Register routes
    register_auth_routes(app)
    register_api_routes(app)
    register_main_routes(app)
    
    return app



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
                # Determine guard type based on port
                import os
                server_port = os.environ.get('SERVER_PORT', '5000')
                guard_type = 'Exit System' if server_port == '5001' else 'Entry System'
                session['guard_type'] = guard_type
                
                description = f'{guard_type} - Guard {user.username} logged in successfully'
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
        print(f"Logout attempt - Guard ID: {guard_id}, Username: {username}")
        
        if guard_id:
            try:
                guard_type = session.get('guard_type', 'Unknown System')
                result = AccessLogQueries.log_guard_action(guard_id, 'logout', f'{guard_type} - Guard {username} logged out')
                print(f"Logout logging result: {result}")
            except Exception as e:
                print(f"Error logging logout: {e}")
        
        session.clear()
        return redirect(url_for('login'))
    
    @app.route('/test_log')
    def test_log():
        try:
            result = AccessLogQueries.log_guard_action('TEST', 'login', 'Test log entry')
            return f'Test log result: {result}'
        except Exception as e:
            return f'Test log error: {e}'

def register_main_routes(app: Flask) -> None:
    """Register main application routes"""
    
    @app.route('/')
    def index():
        if 'guard_id' not in session:
            return redirect(url_for('login'))
        # Check if running on exit port (5001) to show exit dashboard
        if request.environ.get('SERVER_PORT') == '5001':
            return render_template('exit_dashboard.html', guard_id=session.get('username', session['guard_id']))
        return render_template('dashboard.html', guard_id=session.get('username', session['guard_id']))
    
    @app.route('/exit')
    def exit_dashboard():
        if 'guard_id' not in session:
            return redirect(url_for('login'))
        return render_template('exit_dashboard.html', guard_id=session.get('username', session['guard_id']))
    
    @app.route('/video_feed')
    def video_feed():
        if 'guard_id' not in session:
            return redirect(url_for('login'))
        
        if not anpr_service.is_running:
            anpr_service.start_camera()
        
        return Response(anpr_service.generate_frames(),
                       mimetype='multipart/x-mixed-replace; boundary=frame')

def register_api_routes(app: Flask) -> None:
    """Register API routes"""
    
    @app.route('/api/dashboard')
    def get_dashboard():
        if 'guard_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        
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
            return jsonify({
                'vehicle_info': {},
                'dashboard_stats': {
                    'parking': {'total_capacity': 200, 'current_available': 200, 'occupied': 0, 'occupancy_rate': 0},
                    'vehicle_counts': {'2_wheeler': 0, '3_wheeler': 0, '4_wheeler': 0, '6_wheeler': 0},
                    'allocations': {'students': {'current': 0, 'max': 20}, 'faculty': {'current': 0, 'max': 160}, 'guests': {'current': 0, 'max': 20}}
                }
            })
    
    @app.route('/api/vehicle_info')
    def get_vehicle_info():
        if 'guard_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        
        try:
            vehicle_info = anpr_service.get_current_vehicle_info()
            return jsonify({'vehicle_info': vehicle_info})
        except Exception as e:
            return jsonify({'vehicle_info': {}})
    
    @app.route('/api/start_camera')
    def start_camera():
        if 'guard_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        
        try:
            success = anpr_service.start_camera()
            return jsonify({'success': success})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
    
    @app.route('/api/vehicle/<plate_num>')
    def get_vehicle_details(plate_num):
        if 'guard_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        
        try:
            vehicle_info = VehicleQueries.get_vehicle_with_rfid(plate_num)
            if vehicle_info:
                return jsonify(vehicle_info)
            else:
                return jsonify({'error': 'Vehicle not found'}), 404
        except Exception as e:
            return jsonify({'error': 'Internal server error'}), 500
    
    @app.route('/api/latest_event')
    def get_latest_event():
        if 'guard_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        
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
    def acknowledge_event():
        if 'guard_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        
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
    

    
