"""Caching utilities"""

import threading
import time
from typing import Any, Optional, Dict, Tuple

class LRUCache:
    """Thread-safe LRU cache with TTL support"""
    
    def __init__(self, max_size: int = 100, ttl: float = 300.0):
        self.max_size = max_size
        self.ttl = ttl
        self.cache: Dict[str, Tuple[Any, float]] = {}
        self.access_order: Dict[str, float] = {}
        self.lock = threading.Lock()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        with self.lock:
            if key not in self.cache:
                return None
            
            value, timestamp = self.cache[key]
            
            # Check TTL
            if time.time() - timestamp > self.ttl:
                del self.cache[key]
                del self.access_order[key]
                return None
            
            # Update access time
            self.access_order[key] = time.time()
            return value
    
    def put(self, key: str, value: Any) -> None:
        """Put value in cache"""
        with self.lock:
            current_time = time.time()
            
            # Remove oldest if at capacity
            if len(self.cache) >= self.max_size and key not in self.cache:
                oldest_key = min(self.access_order.keys(), key=lambda k: self.access_order[k])
                del self.cache[oldest_key]
                del self.access_order[oldest_key]
            
            self.cache[key] = (value, current_time)
            self.access_order[key] = current_time
    
    def clear(self) -> None:
        """Clear all cache entries"""
        with self.lock:
            self.cache.clear()
            self.access_order.clear()
    
    def size(self) -> int:
        """Get current cache size"""
        with self.lock:
            return len(self.cache)