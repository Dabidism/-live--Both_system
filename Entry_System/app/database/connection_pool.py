"""Database connection pool for efficient connection management"""

import threading
import queue
import time
from typing import Optional
from contextlib import contextmanager
import mysql.connector
from mysql.connector import Error

from app.config.database_config import create_connection

class DatabasePool:
    """Thread-safe database connection pool"""
    
    def __init__(self, pool_size: int = 5):
        self.pool_size = pool_size
        self.pool = queue.Queue(maxsize=pool_size)
        self.lock = threading.Lock()
        self._initialize_pool()
    
    def _initialize_pool(self) -> None:
        """Initialize connection pool"""
        for _ in range(self.pool_size):
            try:
                conn = create_connection()
                self.pool.put(conn)
            except Exception as e:
                print(f"Failed to create DB connection: {e}")
    
    def get_connection(self) -> mysql.connector.MySQLConnection:
        """Get connection from pool with timeout"""
        try:
            return self.pool.get(timeout=2.0)
        except queue.Empty:
            # Create new connection if pool is empty
            return create_connection()
    
    def return_connection(self, conn: mysql.connector.MySQLConnection) -> None:
        """Return connection to pool"""
        try:
            if conn and conn.is_connected():
                self.pool.put(conn, timeout=0.1)
            else:
                # Replace broken connection
                new_conn = create_connection()
                self.pool.put(new_conn, timeout=0.1)
        except (queue.Full, Exception):
            if conn:
                conn.close()
    
    @contextmanager
    def get_connection_context(self):
        """Context manager for database connections"""
        conn = None
        try:
            conn = self.get_connection()
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                self.return_connection(conn)
    
    def close_all(self) -> None:
        """Close all connections in pool"""
        while not self.pool.empty():
            try:
                conn = self.pool.get_nowait()
                if conn:
                    conn.close()
            except queue.Empty:
                break

# Global pool instance
db_pool = DatabasePool()