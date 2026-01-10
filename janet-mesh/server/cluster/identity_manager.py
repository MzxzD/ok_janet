"""
Identity Manager - Unified identity across cluster with prime instance selection
Manages shared identity key, leader election for "voice of Janet", load balancing, and resource pooling
"""
import logging
import hashlib
import secrets
from typing import Dict, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class IdentityManager:
    """
    Manages unified identity across cluster.
    
    Features:
    - Shared identity key across cluster
    - Prime instance selection (leader becomes "voice of Janet")
    - Load balancing for LLM requests
    - CPU/memory resource pooling
    """
    
    def __init__(
        self,
        cluster_orchestrator=None,
        shared_memory=None,
        node_id: Optional[str] = None
    ):
        """
        Initialize Identity Manager.
        
        Args:
            cluster_orchestrator: ClusterOrchestrator instance
            shared_memory: SharedMemoryPool instance
            node_id: Current node identifier
        """
        self.cluster_orchestrator = cluster_orchestrator
        self.shared_memory = shared_memory
        self.node_id = node_id
        
        # Identity key (shared across cluster)
        self.identity_key = None
        self.identity_key_hash = None
        
        # Prime instance (current leader)
        self.prime_instance_id: Optional[str] = None
        
        # Resource tracking
        self.resource_usage: Dict[str, Dict[str, float]] = {}
        
        # Load balancing state
        self.request_count = 0
        self.node_loads: Dict[str, int] = {}
    
    def initialize_identity(self, identity_key: Optional[str] = None) -> str:
        """
        Initialize or retrieve shared identity key.
        
        Args:
            identity_key: Optional existing identity key (generates if None)
            
        Returns:
            Identity key string
        """
        if identity_key:
            self.identity_key = identity_key
        else:
            # Try to get from shared memory
            if self.shared_memory:
                existing_key = self.shared_memory.get_cluster_data("identity_key")
                if existing_key:
                    self.identity_key = existing_key
                    logger.info("Retrieved existing identity key from shared memory")
            
            # Generate new key if not found
            if not self.identity_key:
                self.identity_key = secrets.token_urlsafe(32)
                logger.info("Generated new identity key for cluster")
                
                # Store in shared memory
                if self.shared_memory:
                    self.shared_memory.set_cluster_data("identity_key", self.identity_key)
        
        # Compute hash for verification
        self.identity_key_hash = hashlib.sha256(self.identity_key.encode()).hexdigest()
        
        return self.identity_key
    
    def get_prime_instance(self) -> Optional[str]:
        """
        Get the prime instance ID (current leader/voice of Janet).
        
        Returns:
            Prime instance ID or None if no leader
        """
        if self.cluster_orchestrator:
            leader = self.cluster_orchestrator.get_leader()
            if leader:
                self.prime_instance_id = leader.node_id
                return self.prime_instance_id
        
        return self.prime_instance_id
    
    def is_prime_instance(self) -> bool:
        """Check if this node is the prime instance (voice of Janet)."""
        if self.cluster_orchestrator:
            return self.cluster_orchestrator.is_leader()
        
        return self.prime_instance_id == self.node_id
    
    def update_resource_usage(
        self,
        node_id: str,
        cpu_percent: float,
        memory_percent: float
    ):
        """
        Update resource usage for a node.
        
        Args:
            node_id: Node identifier
            cpu_percent: CPU usage percentage
            memory_percent: Memory usage percentage
        """
        self.resource_usage[node_id] = {
            "cpu_percent": cpu_percent,
            "memory_percent": memory_percent,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        # Store in shared memory for cluster-wide visibility
        if self.shared_memory:
            self.shared_memory.set_cluster_data(
                f"resources:{node_id}",
                self.resource_usage[node_id],
                ttl=60  # Expire after 60 seconds
            )
    
    def get_least_loaded_node(self) -> Optional[str]:
        """
        Get the least loaded node for load balancing.
        
        Returns:
            Node ID of least loaded node, or None if cluster empty
        """
        if not self.cluster_orchestrator:
            return self.node_id
        
        # Get all nodes from orchestrator
        nodes = self.cluster_orchestrator.nodes
        
        if not nodes:
            return self.node_id
        
        # Find node with lowest load
        least_loaded_id = None
        min_load = float('inf')
        
        for node_id, node in nodes.items():
            # Get request count for this node
            load = self.node_loads.get(node_id, 0)
            
            # Get resource usage if available
            if node_id in self.resource_usage:
                cpu = self.resource_usage[node_id].get("cpu_percent", 0)
                memory = self.resource_usage[node_id].get("memory_percent", 0)
                # Combined load metric (request count + resource usage)
                load = load + (cpu * 0.5) + (memory * 0.3)
            
            if load < min_load:
                min_load = load
                least_loaded_id = node_id
        
        return least_loaded_id or self.node_id
    
    def allocate_request(self, node_id: Optional[str] = None) -> str:
        """
        Allocate a request to a node (load balancing).
        
        Args:
            node_id: Optional specific node ID (uses load balancing if None)
            
        Returns:
            Node ID to handle the request
        """
        if node_id:
            target_node = node_id
        else:
            # Load balance: select least loaded node
            target_node = self.get_least_loaded_node()
        
        # Increment request count for target node
        self.node_loads[target_node] = self.node_loads.get(target_node, 0) + 1
        
        return target_node
    
    def release_request(self, node_id: str):
        """
        Release a request from a node (decrement load counter).
        
        Args:
            node_id: Node identifier
        """
        if node_id in self.node_loads and self.node_loads[node_id] > 0:
            self.node_loads[node_id] -= 1
    
    def get_cluster_identity(self) -> Dict[str, Any]:
        """
        Get cluster identity information.
        
        Returns:
            Dictionary with cluster identity details
        """
        return {
            "identity_key_hash": self.identity_key_hash,
            "prime_instance_id": self.get_prime_instance(),
            "is_prime": self.is_prime_instance(),
            "node_id": self.node_id,
            "resource_usage": self.resource_usage,
            "node_loads": self.node_loads
        }
    
    def verify_identity(self, identity_key: str) -> bool:
        """
        Verify identity key matches cluster identity.
        
        Args:
            identity_key: Identity key to verify
            
        Returns:
            True if identity matches
        """
        if not self.identity_key:
            return False
        
        key_hash = hashlib.sha256(identity_key.encode()).hexdigest()
        return key_hash == self.identity_key_hash
