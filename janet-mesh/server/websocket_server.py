"""
WebSocket Server - Main server that handles client connections
"""
import asyncio
import json
import base64
import websockets
from websockets.server import WebSocketServerProtocol
from typing import Dict, Set
import logging

from core.session_manager import SessionManager
from core.memory_manager import MemoryManager
from core.janet_adapter import JanetAdapter
from models.model_loader import ModelLoader
from services.audio_pipeline import AudioPipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress noisy websockets handshake errors (common for health checks, failed connections)
# These errors occur when connections are established but closed before handshake completes
class SuppressHandshakeErrors(logging.Filter):
    """Filter to suppress common WebSocket handshake errors"""
    def filter(self, record):
        msg = record.getMessage()
        # Suppress errors about invalid HTTP requests and handshake failures
        if any(phrase in msg for phrase in [
            "did not receive a valid HTTP request",
            "opening handshake failed",
            "connection closed while reading HTTP request",
            "stream ends after",
            "EOFError: connection closed while reading HTTP request line"
        ]):
            return False  # Don't log this
        return True  # Log everything else

# Apply filter to all websockets loggers
for logger_name in ["websockets", "websockets.server", "websockets.asyncio.server"]:
    ws_logger = logging.getLogger(logger_name)
    ws_logger.setLevel(logging.CRITICAL)  # Only show CRITICAL, suppress ERROR/WARNING/INFO
    ws_logger.addFilter(SuppressHandshakeErrors())

# Suppress noisy websockets handshake errors (common for health checks, failed connections)
websockets_logger = logging.getLogger("websockets.server")
websockets_logger.setLevel(logging.WARNING)  # Only show WARNING and above, not ERROR for handshake failures


class JanetWebSocketServer:
    """WebSocket server for Janet mesh network"""
    
    def __init__(self, host: str = "localhost", port: int = 8765,
                 load_models: bool = True):
        self.host = host
        self.port = port
        self.connected_clients: Set[str] = set()
        self._shutdown_event = None
        self._server = None
        
        # Initialize components
        self.memory_manager = MemoryManager()
        self.session_manager = SessionManager(self.memory_manager)
        self.model_loader = ModelLoader()
        
        # Load models if requested
        if load_models:
            try:
                self.model_loader.load_all_models()
                self.stt_model = self.model_loader.stt_model
                self.tts_model = self.model_loader.tts_model
                self.llm_model = self.model_loader.llm_model
            except Exception as e:
                logger.warning(f"Some models failed to load: {e}")
                logger.info("Server will continue with available models. Text-only mode will work.")
                # Keep models that loaded successfully
                if not hasattr(self, 'stt_model'):
                    self.stt_model = None
                if not hasattr(self, 'tts_model'):
                    self.tts_model = None
                if not hasattr(self, 'llm_model'):
                    self.llm_model = None
        else:
            self.stt_model = None
            self.tts_model = None
            self.llm_model = None
        
        # Initialize Janet adapter
        if self.llm_model:
            # #region agent log
            log_path = "/Users/mzxzd/Documents/Development/ok JANET/.cursor/debug.log"
            try:
                import json
                import os
                with open(log_path, 'a') as f:
                    f.write(json.dumps({
                        "sessionId": "debug-session",
                        "runId": "init",
                        "hypothesisId": "LLM_CHECK",
                        "location": "websocket_server.py:__init__",
                        "message": "LLM model loaded, initializing adapter",
                        "data": {
                            "llm_type": self.llm_model.get("type") if isinstance(self.llm_model, dict) else type(self.llm_model).__name__,
                            "has_brain": "brain" in self.llm_model if isinstance(self.llm_model, dict) else False,
                            "model_name": self.llm_model.get("model_name") if isinstance(self.llm_model, dict) else None,
                            "brain_available": hasattr(self.llm_model.get("brain", None), "is_available") if isinstance(self.llm_model, dict) and "brain" in self.llm_model else False
                        },
                        "timestamp": int(os.path.getmtime(__file__) * 1000) if os.path.exists(__file__) else 0
                    }) + "\n")
            except: pass
            # #endregion
            self.janet_adapter = JanetAdapter(
                self.llm_model,
                self.memory_manager,
                self.session_manager
            )
        else:
            self.janet_adapter = None
        
        # Initialize audio pipeline
        if self.stt_model and self.tts_model and self.janet_adapter:
            self.audio_pipeline = AudioPipeline(
                self.stt_model,
                self.tts_model,
                self.janet_adapter
            )
        else:
            self.audio_pipeline = None
    
    async def handle_client(self, websocket: WebSocketServerProtocol, path: str):
        """Handle a new client connection"""
        client_id = None
        try:
            # Get client_id from query string or generate one
            if "?" in path:
                params = path.split("?")[1]
                client_id = params.split("=")[1] if "client_id=" in params else None
            
            if not client_id:
                client_id = self.session_manager.create_session()
            
            self.connected_clients.add(client_id)
            logger.info(f"Client connected: {client_id}")
            
            # Send welcome message
            await websocket.send(json.dumps({
                "type": "connected",
                "client_id": client_id,
                "status": "ready" if self.audio_pipeline else "models_loading"
            }))
            
            # Handle messages
            async for message in websocket:
                try:
                    await self._handle_message(websocket, client_id, message)
                except Exception as e:
                    logger.error(f"Error handling message: {e}")
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": str(e)
                    }))
        
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client disconnected: {client_id}")
        except Exception as e:
            logger.error(f"Connection error: {e}")
        finally:
            if client_id:
                self.connected_clients.discard(client_id)
                try:
                    self.session_manager.end_session(client_id)
                except Exception as e:
                    # During shutdown, memory operations might fail - that's okay
                    logger.debug(f"Error ending session during cleanup: {e}")
    
    async def _handle_message(self, websocket: WebSocketServerProtocol, 
                            client_id: str, message: str):
        """Handle incoming message from client"""
        try:
            data = json.loads(message)
            msg_type = data.get("type")
            
            # Allow client to override client_id if provided (for reconnection scenarios)
            if "client_id" in data:
                provided_client_id = data.get("client_id")
                if provided_client_id and provided_client_id in self.connected_clients:
                    client_id = provided_client_id
                    logger.info(f"Using provided client_id: {client_id}")
            
            if msg_type == "audio_chunk":
                # Handle audio chunk
                audio_data = base64.b64decode(data.get("audio", ""))
                response = self.audio_pipeline.process_complete_audio(
                    client_id, audio_data
                )
                
                await websocket.send(json.dumps({
                    "type": "response",
                    "text": response.get("text", ""),
                    "user_text": response.get("user_text", ""),
                    "audio": response.get("audio", ""),
                    "audio_format": response.get("audio_format", "wav"),
                    "client_id": client_id  # Echo back client_id so client can store it
                }))
            
            elif msg_type == "text_input":
                # Handle text input directly
                user_text = data.get("text", "")
                logger.info(f"Processing text input for client {client_id}: {user_text[:50]}...")
                
                if self.janet_adapter:
                    response_text = self.janet_adapter.generate_response(
                        client_id, user_text
                    )
                    
                    # Generate TTS if available
                    if self.audio_pipeline:
                        response_audio = self.audio_pipeline._text_to_speech(response_text)
                        audio_base64 = base64.b64encode(response_audio).decode('utf-8')
                    else:
                        audio_base64 = None
                    
                    await websocket.send(json.dumps({
                        "type": "response",
                        "text": response_text,
                        "user_text": user_text,
                        "audio": audio_base64,
                        "audio_format": "wav" if audio_base64 else None,
                        "client_id": client_id  # Echo back client_id so client can store it
                    }))
                else:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": "Janet adapter not initialized"
                    }))
            
            elif msg_type == "ping":
                # Heartbeat
                await websocket.send(json.dumps({
                    "type": "pong",
                    "timestamp": data.get("timestamp")
                }))
            
            elif msg_type == "get_context":
                # Get client context
                if self.janet_adapter:
                    context = self.janet_adapter.get_client_context(client_id)
                    await websocket.send(json.dumps({
                        "type": "context",
                        "data": context
                    }))
            
            else:
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}"
                }))
        
        except json.JSONDecodeError:
            await websocket.send(json.dumps({
                "type": "error",
                "message": "Invalid JSON"
            }))
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await websocket.send(json.dumps({
                "type": "error",
                "message": str(e)
            }))
    
    async def start(self):
        """Start the WebSocket server"""
        logger.info(f"Starting Janet WebSocket server on {self.host}:{self.port}")
        
        # Initialize shutdown event in the event loop context
        self._shutdown_event = asyncio.Event()
        
        # Custom process_request (can be used for request inspection if needed)
        async def process_request(path, request_headers):
            """Process incoming HTTP requests before handshake"""
            # Return None to proceed with normal WebSocket handshake
            return None
        
        
        # Create a wrapper to ensure correct signature and handle errors gracefully
        # Handle both old and new websockets API signatures
        async def handler(websocket, path=None):
            # Handle case where path might be passed as second arg or as attribute
            if path is None:
                # Try to get path from websocket if available
                if hasattr(websocket, 'path'):
                    path = websocket.path
                else:
                    path = "/"
            
            client_addr = None
            try:
                client_addr = websocket.remote_address
                await self.handle_client(websocket, path)
            except websockets.exceptions.InvalidMessage:
                # Invalid handshake - common for health checks or wrong protocol
                logger.debug(f"Invalid WebSocket handshake from {client_addr} (path: {path})")
            except websockets.exceptions.ConnectionClosed:
                # Normal connection close - don't log as error
                logger.debug(f"Connection closed from {client_addr}")
            except websockets.exceptions.InvalidState:
                # Connection in invalid state - common during rapid connect/disconnect
                logger.debug(f"Invalid connection state from {client_addr}")
            except Exception as e:
                # Other errors - log at debug level unless it's unexpected
                if "EOFError" not in str(type(e).__name__):
                    logger.debug(f"Connection error from {client_addr}: {e}")
        
        # Configure server with better error handling
        # The websockets library logs handshake errors internally, so we suppress them
        async with websockets.serve(
            handler, 
            self.host, 
            self.port,
            process_request=process_request
        ) as server:
            self._server = server
            logger.info("Server started, waiting for connections...")
            # Wait for shutdown event instead of running forever
            try:
                await self._shutdown_event.wait()
            except asyncio.CancelledError:
                # Task was cancelled - that's fine, we're shutting down
                logger.info("Server shutdown requested")
                raise
    
    def shutdown(self):
        """Gracefully shutdown the server"""
        if self._shutdown_event:
            try:
                self._shutdown_event.set()
            except RuntimeError:
                # Event loop might be closed - that's okay during shutdown
                pass
    
    def get_status(self) -> Dict:
        """Get server status"""
        return {
            "connected_clients": len(self.connected_clients),
            "active_sessions": self.session_manager.get_session_count(),
            "models_loaded": {
                "stt": self.stt_model is not None,
                "tts": self.tts_model is not None,
                "llm": self.llm_model is not None
            }
        }


if __name__ == "__main__":
    server = JanetWebSocketServer(host="0.0.0.0", port=8765)
    asyncio.run(server.start())
