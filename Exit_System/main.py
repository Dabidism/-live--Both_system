#!/usr/bin/env python3
"""
ANPR Exit System - Standalone Exit Guard Application
"""

import sys
import os
from typing import Optional

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.controllers.web_controller import create_app
from app.services.anpr_service import ANPRService
from app.database.event_queries import EventQueries

def main() -> None:
    """Main exit application entry point"""
    print("=" * 50)
    print("ANPR Exit Guard System Starting...")
    print("=" * 50)
    print("Access the exit dashboard at: http://localhost:5001")
    print("Press Ctrl+C to stop the server")
    print("=" * 50)
    
    # Set environment variable for exit system
    os.environ['SERVER_PORT'] = '5001'
    os.environ['SYSTEM_TYPE'] = 'EXIT'
    
    # Initialize event table
    print("Initializing event system...")
    EventQueries.create_event_table()
    
    app = create_app()
    anpr_service: Optional[ANPRService] = None
    
    try:
        app.run(debug=False, host='0.0.0.0', port=5001, threaded=True)
    except KeyboardInterrupt:
        print("\nShutting down Exit Guard system...")
        if anpr_service:
            anpr_service.stop_camera()
        print("Exit Guard system stopped.")
    except Exception as e:
        print(f"Application error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()