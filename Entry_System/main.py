#!/usr/bin/env python3
"""
Gate System - Unified Entry/Exit Application
"""

import sys
import os
import argparse
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.controllers.web_controller import create_app
from app.services.anpr_service import ANPRService
from app.database.event_queries import EventQueries

def main() -> None:
    """Main application entry point"""
    
    # Parse command line arguments to override env vars
    parser = argparse.ArgumentParser(description='Gate Pass Guard System')
    parser.add_argument('--type', choices=['ENTRY', 'EXIT'], help='System type (ENTRY or EXIT)')
    parser.add_argument('--port', type=int, help='Port to run on (default: 5000 for ENTRY, 5001 for EXIT)')
    args = parser.parse_args()

    # Determine System Type
    system_type = args.type or os.getenv('SYSTEM_TYPE', 'ENTRY').upper()
    os.environ['SYSTEM_TYPE'] = system_type # Context for other modules

    # Determine Port
    default_port = 5001 if system_type == 'EXIT' else 5000
    port = args.port or int(os.getenv('PORT', default_port))
    os.environ['SERVER_PORT'] = str(port)

    print("=" * 50)
    print(f"ANPR {system_type} Guard System Starting...")
    print("=" * 50)
    print(f"Access the {system_type.lower()} dashboard at: http://localhost:{port}")
    print("Press Ctrl+C to stop the server")
    print("=" * 50)
    
    # Initialize event table
    print("Initializing event system...")
    try:
        EventQueries.create_event_table()
    except Exception as e:
        print(f"Warning: Could not initialize event table: {e}")
    
    app = create_app()
    anpr_service: Optional[ANPRService] = None
    
    try:
        # Run Flask app
        app.run(debug=False, host='0.0.0.0', port=port, threaded=True)
    except KeyboardInterrupt:
        print(f"\nShutting down {system_type} Guard system...")
        # Since ANPR service is global in web_controller, we rely on its cleanup
        # In a cleaner architecture, we would have a reference here
        print(f"{system_type} Guard system stopped.")
    except Exception as e:
        print(f"Application error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()