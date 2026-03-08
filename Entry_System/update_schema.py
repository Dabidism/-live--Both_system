
import sys
import os
from dotenv import load_dotenv

# Load env before importing app
load_dotenv()
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.connection_pool import db_pool

def update_schema():
    print("Updating database schema...")
    with db_pool.get_connection_context() as conn:
        cursor = conn.cursor()
        
        # Check if columns exist
        cursor.execute("SHOW COLUMNS FROM parkingstatus LIKE 'studentLimit'")
        if not cursor.fetchone():
            print("Adding studentLimit column...")
            cursor.execute("ALTER TABLE parkingstatus ADD COLUMN studentLimit INT DEFAULT 20")
            
        cursor.execute("SHOW COLUMNS FROM parkingstatus LIKE 'facultyLimit'")
        if not cursor.fetchone():
            print("Adding facultyLimit column...")
            cursor.execute("ALTER TABLE parkingstatus ADD COLUMN facultyLimit INT DEFAULT 160")
            
        cursor.execute("SHOW COLUMNS FROM parkingstatus LIKE 'guestLimit'")
        if not cursor.fetchone():
            print("Adding guestLimit column...")
            cursor.execute("ALTER TABLE parkingstatus ADD COLUMN guestLimit INT DEFAULT 20")
            
        conn.commit()
    print("Schema update complete.")

if __name__ == "__main__":
    try:
        update_schema()
    except Exception as e:
        print(f"Error updating schema: {e}")
