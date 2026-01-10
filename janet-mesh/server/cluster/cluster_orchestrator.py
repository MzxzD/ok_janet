"""
Cluster Orchestrator - RAFT-like leader election and node discovery
Manages cluster state, health checks, automatic failover, and inter-process communication via ZeroMQ
"""
import logging
import threading
import time
import uuid
from typing import Dict, Optional, List, Any, Callable
from datetime import datetime
from enum import Enum
import json

logger = logging.getLogger(__name__)

try:
    import zmq
    ZMQ_AVAILABLE = True
except ImportError:
    ZMQ_AVAILABLE = False
    zmq = None


class NodeState(Enum):
    """Node state in cluster."""
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"
    DISCONNECTED = "disconnected"


class ClusterNode:
    """Represents a node in the cluster."""
    def __init__(
        self,
        node_id: str,
        address: str,
        port: int,
        state: NodeState = NodeState.FOLLOWER
    ):
        self.node_id = node_id
        self.address = address
        self.port = port
        self.state = state
        self.last_heartbeat = datetime.utcnow()
        self.term = 0  # RAFT term
        self.voted_for: Optional[str] = None
        self.health_status = "healthy"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "node_id": self.node_id,
            "address": self.address,
            "port": self.port,
            "state": self.state.value,
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "term": self.term,
            "voted_for": self.voted_for,
            "health_status": self.health_status
        }


class ClusterOrchestrator:
    """
    Cluster Orchestrator with RAFT-like leader election protocol.
    
    Manages:
    - Node discovery via Bonjour/mDNS (extends existing discovery)
    - Health checks and automatic failover
    - Inter-process communication via ZeroMQ
    - Leader election for unified "voice of Janet"
    """
    
    def __init__(
        self,
        node_id: Optional[str] = None,
        bind_address: str = "0.0.0.0",
        cluster_port: int = 8766,
        heartbeat_interval: float = 5.0,
        election_timeout: float = 15.0
    ):
        """
        Initialize Cluster Orchestrator.
        
        Args:
            node_id: Unique node identifier (generates if None)
            bind_address: Address to bind cluster communication to
            cluster_port: Port for cluster communication
            heartbeat_interval: Interval for heartbeat messages (seconds)
            election_timeout: Timeout for leader election (seconds)
        """
        self.node_id = node_id or str(uuid.uuid4())
        self.bind_address = bind_address
        self.cluster_port = cluster_port
        self.heartbeat_interval = heartbeat_interval
        self.election_timeout = election_timeout
        
        # Cluster state
        self.nodes: Dict[str, ClusterNode] = {}
        self.current_term = 0
        self.state = NodeState.FOLLOWER
        self.leader_id: Optional[str] = None
        self.voted_for: Optional[str] = None
        
        # ZeroMQ context and sockets
        self.zmq_context = None
        self.zmq_socket = None
        self.zmq_available = ZMQ_AVAILABLE
        
        # Threading
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        # Callbacks
        self.on_leader_change: Optional[Callable[[str], None]] = None
        
        # Initialize ZeroMQ if available
        if self.zmq_available:
            try:
                self.zmq_context = zmq.Context()
                self.zmq_socket = self.zmq_context.socket(zmq.REP)  # Reply socket for requests
                self.zmq_socket.bind(f"tcp://{bind_address}:{cluster_port}")
                logger.info(f"ZeroMQ socket bound to tcp://{bind_address}:{cluster_port}")
            except Exception as e:
                logger.error(f"Failed to initialize ZeroMQ: {e}")
                self.zmq_available = False
        
        # Add self to cluster
        self.add_node(self.node_id, bind_address, cluster_port, self.state)
    
    def add_node(
        self,
        node_id: str,
        address: str,
        port: int,
        state: NodeState = NodeState.FOLLOWER
    ) -> ClusterNode:
        """
        Add a node to the cluster.
        
        Args:
            node_id: Unique node identifier
            address: Node address
            port: Node port
            state: Initial node state
            
        Returns:
            ClusterNode instance
        """
        with self._lock:
            node = ClusterNode(node_id, address, port, state)
            self.nodes[node_id] = node
            logger.info(f"Added node to cluster: {node_id} at {address}:{port}")
            return node
    
    def remove_node(self, node_id: str):
        """Remove a node from the cluster."""
        with self._lock:
            if node_id in self.nodes:
                del self.nodes[node_id]
                logger.info(f"Removed node from cluster: {node_id}")
                
                # If removed node was leader, trigger election
                if self.leader_id == node_id:
                    self.leader_id = None
                    self.state = NodeState.FOLLOWER
                    self._start_election()
    
    def get_leader(self) -> Optional[ClusterNode]:
        """Get the current leader node."""
        if self.leader_id and self.leader_id in self.nodes:
            return self.nodes[self.leader_id]
        return None
    
    def is_leader(self) -> bool:
        """Check if this node is the leader."""
        return self.state == NodeState.LEADER and self.leader_id == self.node_id
    
    def _start_election(self):
        """Start leader election process (RAFT-like)."""
        with self._lock:
            if self.state == NodeState.LEADER:
                return
            
            self.current_term += 1
            self.state = NodeState.CANDIDATE
            self.voted_for = self.node_id  # Vote for self
            logger.info(f"Started election for term {self.current_term}")
    
    def _become_leader(self):
        """Become the leader node."""
        with self._lock:
            self.state = NodeState.LEADER
            self.leader_id = self.node_id
            logger.info(f"Node {self.node_id} became leader for term {self.current_term}")
            
            # Notify callback
            if self.on_leader_change:
                try:
                    self.on_leader_change(self.node_id)
                except Exception as e:
                    logger.error(f"Error in leader change callback: {e}")
    
    def _update_heartbeat(self, node_id: str):
        """Update heartbeat for a node."""
        with self._lock:
            if node_id in self.nodes:
                self.nodes[node_id].last_heartbeat = datetime.utcnow()
                self.nodes[node_id].health_status = "healthy"
    
    def _check_health(self):
        """Check health of all nodes and detect failures."""
        with self._lock:
            now = datetime.utcnow()
            for node_id, node in list(self.nodes.items()):
                # Check if heartbeat is stale
                time_since_heartbeat = (now - node.last_heartbeat).total_seconds()
                if time_since_heartbeat > self.election_timeout:
                    # In standalone mode, if it's ourselves and we're not leader yet, become leader
                    if len(self.nodes) == 1 and node_id == self.node_id and not self.is_leader():
                        logger.debug(f"Standalone mode: node {node_id} has stale heartbeat, becoming leader")
                        self._become_leader()
                        # Update heartbeat immediately
                        node.last_heartbeat = now
                        node.health_status = "healthy"
                        continue
                    
                    # Node is unhealthy
                    node.health_status = "unhealthy"
                    logger.warning(f"Node {node_id} is unhealthy (no heartbeat for {time_since_heartbeat:.1f}s)")
                    
                    # If unhealthy node was leader, trigger election
                    if self.leader_id == node_id and self.state != NodeState.LEADER:
                        logger.info(f"Leader {node_id} is unhealthy, triggering election")
                        self.leader_id = None
                        self.state = NodeState.FOLLOWER
                        self._start_election()
                    # In standalone mode, if we detect our own stale heartbeat but we are leader, update it
                    elif len(self.nodes) == 1 and node_id == self.node_id and self.is_leader():
                        logger.debug(f"Leader node {node_id} heartbeat check - updating heartbeat")
                        node.last_heartbeat = now
                        node.health_status = "healthy"
    
    def start(self):
        """Start the cluster orchestrator."""
        if self._running:
            logger.warning("Cluster orchestrator already running")
            return
        
        # In standalone mode (single node), automatically become leader
        if len(self.nodes) == 1 and self.state == NodeState.FOLLOWER:
            logger.info(f"Standalone mode detected - automatically electing node {self.node_id} as leader")
            self._become_leader()
        
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info(f"Cluster orchestrator started (node_id: {self.node_id}, state: {self.state.value})")
    
    def stop(self):
        """Stop the cluster orchestrator."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
        
        # Cleanup ZeroMQ
        if self.zmq_socket:
            self.zmq_socket.close()
        if self.zmq_context:
            self.zmq_context.term()
        
        logger.info("Cluster orchestrator stopped")
    
    def _run_loop(self):
        """Main cluster management loop."""
        last_heartbeat = time.time()
        last_health_check = time.time()
        last_election_check = time.time()
        
        while self._running:
            try:
                now = time.time()
                
                # In standalone mode (single node), ensure we're leader
                if len(self.nodes) == 1 and not self.is_leader():
                    if (now - last_election_check) >= 1.0:  # Check every 1 second
                        logger.debug(f"Standalone mode: auto-electing node {self.node_id} as leader")
                        self._become_leader()
                        last_election_check = now
                
                # Send heartbeat if leader
                if self.is_leader() and (now - last_heartbeat) >= self.heartbeat_interval:
                    self._send_heartbeat()
                    last_heartbeat = now
                # Also update own heartbeat periodically even if not leader (for standalone mode)
                elif len(self.nodes) == 1 and (now - last_heartbeat) >= self.heartbeat_interval:
                    # In standalone mode, always update heartbeat
                    self._update_heartbeat(self.node_id)
                    last_heartbeat = now
                
                # Check health periodically
                if (now - last_health_check) >= 2.0:  # Check every 2 seconds
                    self._check_health()
                    last_health_check = now
                
                # Handle ZeroMQ messages
                if self.zmq_available and self.zmq_socket:
                    try:
                        self.zmq_socket.setsockopt(zmq.RCVTIMEO, 100)  # 100ms timeout
                        message = self.zmq_socket.recv_json(zmq.NOBLOCK)
                        self._handle_zmq_message(message)
                    except zmq.Again:
                        pass  # No message received
                    except Exception as e:
                        logger.error(f"Error handling ZeroMQ message: {e}")
                
                # Small sleep to prevent busy loop
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error in cluster loop: {e}")
                time.sleep(1.0)
    
    def _send_heartbeat(self):
        """Send heartbeat to all followers."""
        # In a real implementation, this would send messages to all followers
        # For now, we'll just update our own heartbeat
        self._update_heartbeat(self.node_id)
    
    def _handle_zmq_message(self, message: Dict[str, Any]):
        """Handle incoming ZeroMQ message."""
        msg_type = message.get("type")
        
        if msg_type == "heartbeat":
            node_id = message.get("node_id")
            self._update_heartbeat(node_id)
            self.zmq_socket.send_json({"status": "ok"})
        
        elif msg_type == "vote_request":
            # Handle vote request during election
            candidate_id = message.get("candidate_id")
            candidate_term = message.get("term")
            
            # Vote if we haven't voted for this term or vote for candidate
            with self._lock:
                if candidate_term > self.current_term:
                    self.current_term = candidate_term
                    self.voted_for = candidate_id
                    self.zmq_socket.send_json({"vote_granted": True})
                elif candidate_term == self.current_term and self.voted_for is None:
                    self.voted_for = candidate_id
                    self.zmq_socket.send_json({"vote_granted": True})
                else:
                    self.zmq_socket.send_json({"vote_granted": False})
        
        elif msg_type == "leader_announcement":
            # New leader announced
            leader_id = message.get("leader_id")
            leader_term = message.get("term")
            
            with self._lock:
                if leader_term >= self.current_term:
                    self.current_term = leader_term
                    self.leader_id = leader_id
                    self.state = NodeState.FOLLOWER
                    self.voted_for = None
                    logger.info(f"New leader announced: {leader_id} (term {leader_term})")
            
            self.zmq_socket.send_json({"status": "ok"})
        
        else:
            self.zmq_socket.send_json({"status": "unknown_message_type"})
    
    def get_cluster_status(self) -> Dict[str, Any]:
        """Get current cluster status."""
        with self._lock:
            return {
                "node_id": self.node_id,
                "state": self.state.value,
                "current_term": self.current_term,
                "leader_id": self.leader_id,
                "is_leader": self.is_leader(),
                "node_count": len(self.nodes),
                "nodes": {node_id: node.to_dict() for node_id, node in self.nodes.items()}
            }
