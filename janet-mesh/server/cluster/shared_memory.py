"""
Shared Memory Pool - Cluster-wide short-term memory cache using local Redis
Provides cluster-wide context sharing, conversation context sharing, and task queue distribution
"""
import logging
from typing import Dict, Optional, List, Any
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None


class SharedMemoryPool:
    """
    Shared memory pool using local Redis instance (offline-first, no cloud dependencies).
    
    Provides:
    - Cluster-wide short-term memory cache
    - Conversation context sharing
    - Task queue distribution
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        use_redis: bool = True
    ):
        """
        Initialize Shared Memory Pool.
        
        Args:
            host: Redis host (default: localhost)
            port: Redis port (default: 6379)
            db: Redis database number (default: 0)
            password: Optional Redis password
            use_redis: Whether to use Redis (falls back to in-memory dict if False)
        """
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.use_redis = use_redis and REDIS_AVAILABLE
        
        # Redis client
        self.redis_client = None
        
        # Fallback: in-memory dictionary (if Redis not available)
        self.memory_store: Dict[str, Dict[str, Any]] = {}
        
        # Initialize Redis if available and requested
        if self.use_redis:
            try:
                self.redis_client = redis.Redis(
                    host=host,
                    port=port,
                    db=db,
                    password=password,
                    decode_responses=True,
                    socket_connect_timeout=2
                )
                # Test connection
                self.redis_client.ping()
                logger.info(f"Connected to Redis at {host}:{port}")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}. Using in-memory fallback.")
                self.use_redis = False
                self.redis_client = None
        
        if not self.use_redis:
            logger.info("Using in-memory fallback for shared memory (no Redis)")
    
    def _get_key(self, prefix: str, key: str) -> str:
        """Generate Redis key with prefix."""
        return f"janet:cluster:{prefix}:{key}"
    
    def store_context(
        self,
        client_id: str,
        context: List[Dict[str, Any]],
        ttl: int = 3600  # Default: 1 hour
    ):
        """
        Store conversation context in shared memory.
        
        Args:
            client_id: Client identifier
            context: Conversation context (list of messages)
            ttl: Time-to-live in seconds
        """
        key = self._get_key("context", client_id)
        value = json.dumps({
            "context": context,
            "stored_at": datetime.utcnow().isoformat(),
            "client_id": client_id
        })
        
        try:
            if self.use_redis and self.redis_client:
                self.redis_client.setex(key, ttl, value)
            else:
                # In-memory fallback with expiration
                self.memory_store[key] = {
                    "value": value,
                    "expires_at": datetime.utcnow() + timedelta(seconds=ttl)
                }
                self._cleanup_expired()
        except Exception as e:
            logger.error(f"Error storing context: {e}")
    
    def get_context(self, client_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get conversation context from shared memory.
        
        Args:
            client_id: Client identifier
            
        Returns:
            Conversation context or None if not found
        """
        key = self._get_key("context", client_id)
        
        try:
            if self.use_redis and self.redis_client:
                value = self.redis_client.get(key)
                if value:
                    data = json.loads(value)
                    return data.get("context")
            else:
                # In-memory fallback
                if key in self.memory_store:
                    entry = self.memory_store[key]
                    if datetime.utcnow() < entry["expires_at"]:
                        data = json.loads(entry["value"])
                        return data.get("context")
                    else:
                        # Expired, remove
                        del self.memory_store[key]
        except Exception as e:
            logger.error(f"Error getting context: {e}")
        
        return None
    
    def add_to_queue(
        self,
        queue_name: str,
        task: Dict[str, Any],
        priority: int = 0
    ):
        """
        Add task to distributed queue.
        
        Args:
            queue_name: Queue name
            task: Task data dictionary
            priority: Task priority (higher = more priority)
        """
        queue_key = self._get_key("queue", queue_name)
        task_data = json.dumps({
            "task": task,
            "priority": priority,
            "created_at": datetime.utcnow().isoformat()
        })
        
        try:
            if self.use_redis and self.redis_client:
                # Use sorted set for priority queue
                self.redis_client.zadd(queue_key, {task_data: priority})
            else:
                # In-memory fallback (simple list)
                if queue_key not in self.memory_store:
                    self.memory_store[queue_key] = {"value": []}
                self.memory_store[queue_key]["value"].append({
                    "task_data": task_data,
                    "priority": priority
                })
                # Sort by priority
                self.memory_store[queue_key]["value"].sort(key=lambda x: x["priority"], reverse=True)
        except Exception as e:
            logger.error(f"Error adding to queue: {e}")
    
    def get_from_queue(self, queue_name: str) -> Optional[Dict[str, Any]]:
        """
        Get next task from distributed queue (FIFO with priority).
        
        Args:
            queue_name: Queue name
            
        Returns:
            Task data or None if queue empty
        """
        queue_key = self._get_key("queue", queue_name)
        
        try:
            if self.use_redis and self.redis_client:
                # Get highest priority task
                results = self.redis_client.zrevrange(queue_key, 0, 0, withscores=True)
                if results:
                    task_data = results[0][0]
                    self.redis_client.zrem(queue_key, task_data)
                    data = json.loads(task_data)
                    return data.get("task")
            else:
                # In-memory fallback
                if queue_key in self.memory_store:
                    queue = self.memory_store[queue_key]["value"]
                    if queue:
                        task_entry = queue.pop(0)  # Highest priority first
                        data = json.loads(task_entry["task_data"])
                        return data.get("task")
        except Exception as e:
            logger.error(f"Error getting from queue: {e}")
        
        return None
    
    def set_cluster_data(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set cluster-wide data."""
        cluster_key = self._get_key("data", key)
        value_str = json.dumps(value)
        
        try:
            if self.use_redis and self.redis_client:
                if ttl:
                    self.redis_client.setex(cluster_key, ttl, value_str)
                else:
                    self.redis_client.set(cluster_key, value_str)
            else:
                # In-memory fallback
                entry = {"value": value_str}
                if ttl:
                    entry["expires_at"] = datetime.utcnow() + timedelta(seconds=ttl)
                self.memory_store[cluster_key] = entry
                self._cleanup_expired()
        except Exception as e:
            logger.error(f"Error setting cluster data: {e}")
    
    def get_cluster_data(self, key: str) -> Optional[Any]:
        """Get cluster-wide data."""
        cluster_key = self._get_key("data", key)
        
        try:
            if self.use_redis and self.redis_client:
                value = self.redis_client.get(cluster_key)
                if value:
                    return json.loads(value)
            else:
                # In-memory fallback
                if cluster_key in self.memory_store:
                    entry = self.memory_store[cluster_key]
                    if "expires_at" not in entry or datetime.utcnow() < entry["expires_at"]:
                        return json.loads(entry["value"])
                    else:
                        del self.memory_store[cluster_key]
        except Exception as e:
            logger.error(f"Error getting cluster data: {e}")
        
        return None
    
    def _cleanup_expired(self):
        """Clean up expired entries from in-memory store."""
        now = datetime.utcnow()
        expired_keys = [
            key for key, entry in self.memory_store.items()
            if "expires_at" in entry and now >= entry["expires_at"]
        ]
        for key in expired_keys:
            del self.memory_store[key]
    
    def is_available(self) -> bool:
        """Check if shared memory pool is available."""
        if self.use_redis and self.redis_client:
            try:
                self.redis_client.ping()
                return True
            except Exception:
                return False
        return True  # In-memory fallback always available
