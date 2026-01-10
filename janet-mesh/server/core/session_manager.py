"""
Session Manager - Manages client sessions and their contexts
"""
import uuid
import time
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from .memory_manager import MemoryManager


@dataclass
class SessionContext:
    """Context for a client session"""
    client_id: str
    created_at: datetime
    last_activity: datetime
    memory_context: list
    preferences: Dict[str, Any]
    active: bool = True


class SessionManager:
    """Manages multiple client sessions"""
    
    def __init__(self, memory_manager: MemoryManager, 
                 session_timeout_minutes: int = 30):
        self.memory_manager = memory_manager
        self.session_timeout = timedelta(minutes=session_timeout_minutes)
        self.sessions: Dict[str, SessionContext] = {}
    
    def create_session(self, client_id: Optional[str] = None) -> str:
        """Create a new client session"""
        if client_id is None:
            client_id = str(uuid.uuid4())
        
        if client_id in self.sessions:
            # Reactivate existing session
            self.sessions[client_id].active = True
            self.sessions[client_id].last_activity = datetime.now()
            return client_id
        
        # Create new session
        memory_context = self.memory_manager.get_client_memory_context(client_id)
        
        session = SessionContext(
            client_id=client_id,
            created_at=datetime.now(),
            last_activity=datetime.now(),
            memory_context=memory_context,
            preferences={}
        )
        
        self.sessions[client_id] = session
        return client_id
    
    def get_session(self, client_id: str) -> Optional[SessionContext]:
        """Get session context for a client"""
        session = self.sessions.get(client_id)
        if session and session.active:
            # Update last activity
            session.last_activity = datetime.now()
            return session
        return None
    
    def update_session_activity(self, client_id: str):
        """Update last activity time for a session"""
        session = self.sessions.get(client_id)
        if session:
            session.last_activity = datetime.now()
    
    def end_session(self, client_id: str):
        """End a client session"""
        try:
            session = self.sessions.get(client_id)
            if session:
                session.active = False
                # Save memory context (skip during shutdown if database is unavailable)
                try:
                    for message in session.memory_context:
                        if message.get("role") and message.get("content"):
                            self.memory_manager.add_to_memory(
                                client_id,
                                message["role"],
                                message["content"],
                                message.get("metadata")
                            )
                except Exception as e:
                    # During shutdown, database operations might fail - that's okay
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.debug(f"Error saving memory during session end: {e}")
        except Exception as e:
            # Catch any other errors during shutdown
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Error ending session: {e}")
    
    def cleanup_inactive_sessions(self):
        """Remove sessions that have timed out"""
        now = datetime.now()
        inactive_clients = []
        
        for client_id, session in self.sessions.items():
            if not session.active:
                continue
            
            if now - session.last_activity > self.session_timeout:
                inactive_clients.append(client_id)
        
        for client_id in inactive_clients:
            self.end_session(client_id)
            del self.sessions[client_id]
    
    def get_active_sessions(self) -> Dict[str, SessionContext]:
        """Get all active sessions"""
        self.cleanup_inactive_sessions()
        return {cid: sess for cid, sess in self.sessions.items() if sess.active}
    
    def get_session_count(self) -> int:
        """Get number of active sessions"""
        return len(self.get_active_sessions())
    
    def set_preference(self, client_id: str, key: str, value: Any):
        """Set a preference for a client"""
        session = self.get_session(client_id)
        if session:
            session.preferences[key] = value
    
    def get_preference(self, client_id: str, key: str, default: Any = None) -> Any:
        """Get a preference for a client"""
        session = self.get_session(client_id)
        if session:
            return session.preferences.get(key, default)
        return default
