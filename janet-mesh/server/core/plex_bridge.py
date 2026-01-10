"""
Plex Bridge - WebSocket-to-Plex bridge service for mesh network playback control
Routes playback commands from iOS/Android clients through Plex handler
"""
import logging
from typing import Dict, Optional, Any
import json

logger = logging.getLogger(__name__)

try:
    from pathlib import Path
    import sys
    # Add janet-seed to path for handler imports
    janet_seed_path = Path(__file__).parent.parent.parent / "janet-seed" / "src"
    if janet_seed_path.exists() and str(janet_seed_path) not in sys.path:
        sys.path.insert(0, str(janet_seed_path))
    
    # Try importing delegation handlers with better error handling
    try:
        from delegation.handlers.plex_handler import PlexDelegationHandler
        from delegation.handlers.base import DelegationRequest, HandlerCapability
        PLEX_BRIDGE_AVAILABLE = True
    except (ImportError, NameError, SyntaxError) as e:
        logger.warning(f"Failed to import Plex delegation handler: {e}")
        PLEX_BRIDGE_AVAILABLE = False
        PlexDelegationHandler = None
        DelegationRequest = None
        HandlerCapability = None
except Exception as e:
    logger.warning(f"Failed to set up Plex bridge imports: {e}")
    PLEX_BRIDGE_AVAILABLE = False
    PlexDelegationHandler = None
    DelegationRequest = None
    HandlerCapability = None


class PlexBridge:
    """
    WebSocket-to-Plex bridge service.
    
    Routes playback commands from mesh clients (iOS, Android) through Plex handler.
    Example: "Play Blade Runner on living room TV" → Plex API call
    """
    
    def __init__(
        self,
        plex_handler: Optional[PlexDelegationHandler] = None,
        config_path: Optional[Path] = None
    ):
        """
        Initialize Plex Bridge.
        
        Args:
            plex_handler: PlexDelegationHandler instance (optional, will load from config if None)
            config_path: Path to config directory containing plex_config.json
        """
        self.plex_handler = plex_handler
        self.config_path = config_path or Path(__file__).parent.parent.parent / "janet-seed" / "config"
        self.config = None
        
        # Load Plex handler from config if not provided
        if not self.plex_handler:
            self._load_plex_handler()
    
    def _load_plex_handler(self):
        """Load Plex handler from configuration file."""
        if not PLEX_BRIDGE_AVAILABLE:
            logger.warning("Plex bridge not available - plexapi or handler not found")
            return
        
        try:
            config_file = self.config_path / "plex_config.json"
            if not config_file.exists():
                logger.debug("Plex config file not found - Plex bridge unavailable")
                return
            
            with open(config_file, 'r') as f:
                self.config = json.load(f)
            
            plex_server_url = self.config.get("plex_server_url")
            plex_token = self.config.get("plex_token")
            allow_history = self.config.get("allow_history_tracking", False)
            
            if plex_server_url and plex_token:
                self.plex_handler = PlexDelegationHandler(
                    plex_server_url=plex_server_url,
                    plex_token=plex_token,
                    allow_history_tracking=allow_history
                )
                
                if self.plex_handler.is_available():
                    logger.info(f"Plex bridge initialized: {plex_server_url}")
                else:
                    logger.warning("Plex handler created but not available (connection failed)")
                    self.plex_handler = None
            else:
                logger.warning("Plex config incomplete - missing server URL or token")
        
        except Exception as e:
            logger.error(f"Failed to load Plex handler: {e}")
            self.plex_handler = None
    
    def handle_playback_command(
        self,
        command: str,
        media_title: Optional[str] = None,
        client_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Handle playback command from mesh client.
        
        Args:
            command: Playback command ("play", "pause", "stop")
            media_title: Optional media title to play
            client_name: Optional Plex client name (device name)
            
        Returns:
            Dictionary with result status and message
        """
        if not self.plex_handler or not self.plex_handler.is_available():
            return {
                "success": False,
                "message": "Plex handler not available",
                "error": "Plex integration not configured or connection failed"
            }
        
        try:
            # Create delegation request
            if not HandlerCapability:
                return {
                    "success": False,
                    "message": "HandlerCapability not available",
                    "error": "Import error"
                }
            
            request = DelegationRequest(
                capability=HandlerCapability.MEDIA_CONTROL,
                task_description=f"{command} {media_title or ''} on {client_name or 'default client'}",
                input_data={
                    "action": command,
                    "title": media_title,
                    "client": client_name
                },
                requires_confirmation=False  # Already confirmed by mesh client
            )
            
            # Handle request
            result = self.plex_handler.handle(request)
            
            return {
                "success": result.success,
                "message": result.message,
                "output_data": result.output_data,
                "error": result.error,
                "metadata": result.metadata
            }
        
        except Exception as e:
            logger.error(f"Error handling playback command: {e}")
            return {
                "success": False,
                "message": f"Playback command failed: {str(e)}",
                "error": str(e)
            }
    
    def search_media(
        self,
        query: str,
        media_type: str = "all",
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Search Plex library for media.
        
        Args:
            query: Search query (title, actor, genre, etc.)
            media_type: Type of media ("movie", "show", "all")
            limit: Maximum number of results
            
        Returns:
            Dictionary with search results
        """
        if not self.plex_handler or not self.plex_handler.is_available():
            return {
                "success": False,
                "results": [],
                "message": "Plex handler not available",
                "error": "Plex integration not configured"
            }
        
        try:
            request = DelegationRequest(
                capability=HandlerCapability.MEDIA_CONTROL,
                task_description=f"search {query}",
                input_data={
                    "query": query,
                    "type": media_type,
                    "limit": limit
                },
                requires_confirmation=False
            )
            
            result = self.plex_handler.handle(request)
            
            return {
                "success": result.success,
                "results": result.output_data.get("results", []),
                "count": result.output_data.get("count", 0),
                "message": result.message,
                "error": result.error
            }
        
        except Exception as e:
            logger.error(f"Error searching media: {e}")
            return {
                "success": False,
                "results": [],
                "message": f"Search failed: {str(e)}",
                "error": str(e)
            }
    
    def get_library_stats(self) -> Dict[str, Any]:
        """
        Get Plex library statistics.
        
        Returns:
            Dictionary with library statistics
        """
        if not self.plex_handler or not self.plex_handler.is_available():
            return {
                "success": False,
                "stats": {},
                "message": "Plex handler not available",
                "error": "Plex integration not configured"
            }
        
        try:
            request = DelegationRequest(
                capability=HandlerCapability.MEDIA_CONTROL,
                task_description="get library stats",
                input_data={},
                requires_confirmation=False
            )
            
            result = self.plex_handler.handle(request)
            
            return {
                "success": result.success,
                "stats": result.output_data,
                "message": result.message,
                "error": result.error
            }
        
        except Exception as e:
            logger.error(f"Error getting library stats: {e}")
            return {
                "success": False,
                "stats": {},
                "message": f"Stats failed: {str(e)}",
                "error": str(e)
            }
    
    def is_available(self) -> bool:
        """Check if Plex bridge is available and ready."""
        return (
            PLEX_BRIDGE_AVAILABLE and
            self.plex_handler is not None and
            self.plex_handler.is_available()
        )
