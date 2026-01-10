"""
WebSocket Server - Main server that handles client connections
"""
import asyncio
import json
import base64
import io
import websockets
from websockets.server import WebSocketServerProtocol
from typing import Dict, Set, Any
import logging

from core.session_manager import SessionManager
from core.memory_manager import MemoryManager
from core.janet_adapter import JanetAdapter
from models.model_loader import ModelLoader
from services.audio_pipeline import AudioPipeline
# Import PlexBridge lazily to avoid path conflicts during startup
# PlexBridge = None  # Will be imported in __init__ if needed

# Soul Bridge imports
try:
    import sys
    from pathlib import Path
    # Add janet-seed to path for bridge imports
    janet_seed_path = Path(__file__).parent.parent / "janet-seed" / "src"
    if janet_seed_path.exists():
        sys.path.insert(0, str(janet_seed_path))
    from bridge import SoulBridge, MemoryTransfer, StateReconciliation, TransferResult
    BRIDGE_AVAILABLE = True
except ImportError:
    BRIDGE_AVAILABLE = False
    SoulBridge = None
    MemoryTransfer = None
    StateReconciliation = None
    TransferResult = None

# Cluster imports
try:
    from cluster import ClusterOrchestrator, SharedMemoryPool, IdentityManager
    CLUSTER_AVAILABLE = True
except ImportError:
    CLUSTER_AVAILABLE = False
    ClusterOrchestrator = None
    SharedMemoryPool = None
    IdentityManager = None

# VR Audio Bridge imports
try:
    from services.vr_audio_bridge import VRAudioBridge
    VR_BRIDGE_AVAILABLE = True
except ImportError:
    VR_BRIDGE_AVAILABLE = False
    VRAudioBridge = None

# VoIP Bridge imports
try:
    from services.voip_bridge import VoIPBridge
    VOIP_BRIDGE_AVAILABLE = True
except ImportError:
    VOIP_BRIDGE_AVAILABLE = False
    VoIPBridge = None

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
        
        # Initialize Soul Bridge for transfer between souls
        self.soul_bridge = None
        self.memory_transfer = None
        self.state_reconciliation = None
        if BRIDGE_AVAILABLE:
            try:
                self.soul_bridge = SoulBridge(
                    networked_memory_manager=self.memory_manager
                )
                self.memory_transfer = MemoryTransfer(
                    networked_memory_manager=self.memory_manager
                )
                self.state_reconciliation = StateReconciliation()
                logger.info("Soul Bridge initialized for Double-Soul transfer")
            except Exception as e:
                logger.warning(f"Soul Bridge initialization failed: {e}")
                logger.info("Server will continue without Double-Soul transfer capability")
        
        # Initialize Cluster Orchestrator (optional)
        self.cluster_orchestrator = None
        self.shared_memory = None
        self.identity_manager = None
        if CLUSTER_AVAILABLE:
            try:
                self.shared_memory = SharedMemoryPool(use_redis=False)  # Use in-memory fallback by default
                self.cluster_orchestrator = ClusterOrchestrator()
                self.identity_manager = IdentityManager(
                    cluster_orchestrator=self.cluster_orchestrator,
                    shared_memory=self.shared_memory,
                    node_id=self.cluster_orchestrator.node_id
                )
                # Initialize identity
                self.identity_manager.initialize_identity()
                logger.info("Cluster orchestrator initialized (standalone mode)")
            except Exception as e:
                logger.warning(f"Cluster orchestrator initialization failed: {e}")
                logger.info("Server will continue without clustering capability")
        
        # Initialize VR Audio Bridge
        self.vr_audio_bridge = None
        if VR_BRIDGE_AVAILABLE:
            try:
                self.vr_audio_bridge = VRAudioBridge(
                    audio_pipeline=None,  # Will be set after audio_pipeline initialization
                    janet_adapter=None  # Will be set after janet_adapter initialization
                )
                logger.info("VR Audio Bridge initialized")
            except Exception as e:
                logger.warning(f"VR Audio Bridge initialization failed: {e}")
        
        # Initialize Plex Bridge (lazy import to avoid path conflicts)
        self.plex_bridge = None
        try:
            # Import here instead of module level to avoid early sys.path modification
            from core.plex_bridge import PlexBridge
            self.plex_bridge = PlexBridge()
            if self.plex_bridge.is_available():
                logger.info("Plex Bridge initialized and connected")
            else:
                logger.info("Plex Bridge initialized (not yet configured)")
        except Exception as e:
            logger.warning(f"Plex Bridge initialization failed: {e}")
            logger.info("Server will continue without Plex integration")
        
        # Initialize VoIP Bridge
        self.voip_bridge = None
        if VOIP_BRIDGE_AVAILABLE:
            try:
                self.voip_bridge = VoIPBridge(
                    audio_pipeline=None,  # Will be set after audio_pipeline initialization
                    janet_adapter=None,  # Will be set after janet_adapter initialization
                    cluster_orchestrator=self.cluster_orchestrator,
                    identity_manager=self.identity_manager
                )
                logger.info("VoIP Bridge initialized")
            except Exception as e:
                logger.warning(f"VoIP Bridge initialization failed: {e}")
        
        # Initialize Janet adapter (moved after memory manager initialization)
        
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
            self.janet_adapter = JanetAdapter(
                self.llm_model,
                self.memory_manager,
                self.session_manager,
                identity_manager=self.identity_manager,
                cluster_mode=bool(self.cluster_orchestrator)
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
        
        # Update VR bridge with audio pipeline and adapter (if available)
        if self.vr_audio_bridge:
            self.vr_audio_bridge.audio_pipeline = self.audio_pipeline
            self.vr_audio_bridge.janet_adapter = self.janet_adapter
            logger.info("VR Audio Bridge updated with audio pipeline and Janet adapter")
        
        # Update VoIP bridge with audio pipeline and adapter (if available)
        if self.voip_bridge:
            self.voip_bridge.audio_pipeline = self.audio_pipeline
            self.voip_bridge.janet_adapter = self.janet_adapter
            logger.info("VoIP Bridge updated with audio pipeline and Janet adapter")
        
        # Start cluster orchestrator if available
        if self.cluster_orchestrator:
            try:
                self.cluster_orchestrator.start()
                logger.info("Cluster orchestrator started")
            except Exception as e:
                logger.warning(f"Failed to start cluster orchestrator: {e}")
    
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
                except websockets.exceptions.ConnectionClosed:
                    # Connection closed during message handling - break out of loop
                    logger.info(f"Connection closed during message handling for client {client_id}")
                    break
                except Exception as e:
                    logger.error(f"Error handling message: {e}", exc_info=True)
                    # Try to send error, but if connection is closed, that's okay
                    try:
                        if not websocket.closed:
                            await websocket.send(json.dumps({
                                "type": "error",
                                "message": str(e)
                            }))
                    except (websockets.exceptions.ConnectionClosed, Exception) as send_err:
                        logger.debug(f"Could not send error message (connection may be closed): {send_err}")
                        break  # Break out of message loop if we can't send
        
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client disconnected: {client_id}")
        except Exception as e:
            logger.error(f"Connection error: {e}", exc_info=True)
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
            
            elif msg_type == "transfer_context":
                # Handle Double-Soul conversation transfer
                await self._handle_transfer_context(websocket, client_id, data)
            
            elif msg_type == "vr_connect":
                # Handle VR client connection
                await self._handle_vr_connect(websocket, client_id, data)
            
            elif msg_type == "vr_audio":
                # Handle VR audio input
                await self._handle_vr_audio(websocket, client_id, data)
            
            elif msg_type == "cluster_status":
                # Get cluster status
                await self._handle_cluster_status(websocket, client_id, data)
            
            elif msg_type == "plex_command":
                # Handle Plex playback commands
                await self._handle_plex_command(websocket, client_id, data)
            
            elif msg_type == "plex_search":
                # Handle Plex media search
                await self._handle_plex_search(websocket, client_id, data)
            
            elif msg_type == "file_upload":
                # Handle file/image upload for analysis
                await self._handle_file_upload(websocket, client_id, data)
            
            elif msg_type == "voip_call":
                # Handle VOIP call initiation
                await self._handle_voip_call(websocket, client_id, data)
            
            elif msg_type == "voip_answer":
                # Handle VOIP call answer (WebRTC answer)
                await self._handle_voip_answer(websocket, client_id, data)
            
            elif msg_type == "voip_audio":
                # Handle VOIP audio input
                await self._handle_voip_audio(websocket, client_id, data)
            
            elif msg_type == "voip_end":
                # Handle VOIP call termination
                await self._handle_voip_end(websocket, client_id, data)
            
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
    
    async def _handle_transfer_context(
        self,
        websocket: WebSocketServerProtocol,
        client_id: str,
        data: Dict
    ):
        """
        Handle Double-Soul conversation transfer request.
        
        Message format:
        {
            "type": "transfer_context",
            "source_soul": "networked" | "constitutional",
            "target_soul": "networked" | "constitutional",
            "conversation_uuid": "optional-existing-uuid",
            "include_vaults": ["green", "red"],  // never "blue"
            "auto_consent": false  // if true, skip consent gate
        }
        """
        if not BRIDGE_AVAILABLE or not self.soul_bridge:
            await websocket.send(json.dumps({
                "type": "transfer_error",
                "message": "Soul Bridge not available"
            }))
            return
        
        try:
            source_soul = data.get("source_soul", "networked")
            target_soul = data.get("target_soul", "constitutional")
            conversation_uuid = data.get("conversation_uuid")
            include_vaults = data.get("include_vaults", ["green"])
            auto_consent = data.get("auto_consent", False)
            
            # Validate soul types
            if source_soul not in ["networked", "constitutional"]:
                await websocket.send(json.dumps({
                    "type": "transfer_error",
                    "message": f"Invalid source_soul: {source_soul}. Must be 'networked' or 'constitutional'"
                }))
                return
            
            if target_soul not in ["networked", "constitutional"]:
                await websocket.send(json.dumps({
                    "type": "transfer_error",
                    "message": f"Invalid target_soul: {target_soul}. Must be 'networked' or 'constitutional'"
                }))
                return
            
            # Create consent callback
            async def request_consent(transfer_request):
                """Request consent via TTS prompt and wait for user response."""
                if auto_consent:
                    return True
                
                # Generate TTS prompt: "Soul sync requested. Proceed?"
                consent_prompt = "Soul sync requested. Proceed?"
                
                # Send consent request to client
                await websocket.send(json.dumps({
                    "type": "consent_request",
                    "conversation_uuid": transfer_request.conversation_uuid,
                    "prompt": consent_prompt,
                    "prompt_audio": None,  # Will be generated if TTS available
                    "requires_response": True
                }))
                
                # Generate TTS audio if available
                if self.audio_pipeline and self.audio_pipeline.tts_model:
                    try:
                        audio_bytes = self.audio_pipeline._text_to_speech(consent_prompt)
                        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
                        await websocket.send(json.dumps({
                            "type": "consent_request_audio",
                            "conversation_uuid": transfer_request.conversation_uuid,
                            "audio": audio_base64,
                            "audio_format": "wav"
                        }))
                    except Exception as e:
                        logger.warning(f"Failed to generate TTS for consent prompt: {e}")
                
                # Wait for consent response (with timeout)
                # Client should send: {"type": "consent_response", "conversation_uuid": "...", "granted": true/false}
                # For now, we'll use a simple timeout and assume consent if no response
                # In production, implement proper async waiting
                import asyncio
                try:
                    # Wait up to 30 seconds for consent response
                    # This is a simplified implementation - in production, use a proper message queue
                    await asyncio.sleep(0.1)  # Small delay to allow message processing
                    # For now, auto-consent after prompt (operator can implement proper waiting)
                    return True
                except asyncio.TimeoutError:
                    logger.warning(f"Consent request timed out for {transfer_request.conversation_uuid}")
                    return False
            
            # Create transfer request
            self.soul_bridge.consent_callback = request_consent
            transfer_request = await self.soul_bridge.request_transfer(
                source_soul=source_soul,
                target_soul=target_soul,
                conversation_uuid=conversation_uuid,
                client_id=client_id,
                include_vaults=include_vaults
            )
            
            if not transfer_request.consent_granted:
                await websocket.send(json.dumps({
                    "type": "transfer_denied",
                    "conversation_uuid": transfer_request.conversation_uuid,
                    "reason": "Consent not granted"
                }))
                return
            
            # Perform transfer
            if source_soul == "networked" and target_soul == "constitutional":
                # Export from networked (Janet Mesh) to constitutional (Janet-seed)
                exported_context = self.memory_transfer.export_conversation_context(
                    source_memory_manager=self.memory_manager,
                    client_id=client_id,
                    include_vaults=include_vaults,
                    conversation_uuid=transfer_request.conversation_uuid,
                    red_vault_unlocked=False  # TODO: Check if Red Vault is unlocked
                )
                
                # Import into constitutional soul (requires Janet-seed memory manager)
                # For now, we'll return the exported context for the client to handle
                # TODO: Implement full import if Janet-seed memory manager is available
                transfer_result = TransferResult(
                    success=True,
                    conversation_uuid=transfer_request.conversation_uuid,
                    messages_transferred=len(exported_context.get("messages", [])),
                    vaults_transferred=[v for v in include_vaults if v in exported_context.get("vaults", {})],
                    metadata={"exported_context": exported_context}
                )
            
            elif source_soul == "constitutional" and target_soul == "networked":
                # Import from constitutional (Janet-seed) to networked (Janet Mesh)
                # Requires exported context from Janet-seed
                exported_context = data.get("exported_context")
                if not exported_context:
                    await websocket.send(json.dumps({
                        "type": "transfer_error",
                        "message": "exported_context required for constitutional -> networked transfer"
                    }))
                    return
                
                transfer_result = self.memory_transfer.import_conversation_context(
                    target_memory_manager=self.memory_manager,
                    exported_context=exported_context,
                    conversation_uuid=transfer_request.conversation_uuid,
                    client_id=client_id
                )
            
            else:
                await websocket.send(json.dumps({
                    "type": "transfer_error",
                    "message": f"Transfer direction not yet implemented: {source_soul} -> {target_soul}"
                }))
                return
            
            # Record transfer result
            self.soul_bridge.record_transfer_result(transfer_result)
            
            # Send transfer result to client
            await websocket.send(json.dumps({
                "type": "transfer_result",
                "conversation_uuid": transfer_result.conversation_uuid,
                "success": transfer_result.success,
                "messages_transferred": transfer_result.messages_transferred,
                "vaults_transferred": transfer_result.vaults_transferred,
                "error": transfer_result.error,
                "metadata": transfer_result.metadata
            }))
            
        except Exception as e:
            logger.error(f"Error handling transfer_context: {e}")
            await websocket.send(json.dumps({
                "type": "transfer_error",
                "message": str(e)
            }))
    
    async def _handle_vr_connect(
        self,
        websocket: WebSocketServerProtocol,
        client_id: str,
        data: Dict
    ):
        """Handle VR client connection request."""
        if not self.vr_audio_bridge or not self.vr_audio_bridge.is_available():
            await websocket.send(json.dumps({
                "type": "vr_error",
                "message": "VR Audio Bridge not available"
            }))
            return
        
        try:
            session_id = data.get("session_id") or client_id
            
            # Create WebRTC peer connection
            offer_result = await self.vr_audio_bridge.create_peer_connection(session_id)
            
            if offer_result:
                await websocket.send(json.dumps({
                    "type": "vr_offer",
                    "session_id": session_id,
                    "sdp": offer_result["sdp"],
                    "sdp_type": offer_result["type"]
                }))
            else:
                await websocket.send(json.dumps({
                    "type": "vr_error",
                    "message": "Failed to create peer connection"
                }))
        
        except Exception as e:
            logger.error(f"Error handling vr_connect: {e}")
            await websocket.send(json.dumps({
                "type": "vr_error",
                "message": str(e)
            }))
    
    async def _handle_vr_audio(
        self,
        websocket: WebSocketServerProtocol,
        client_id: str,
        data: Dict
    ):
        """Handle VR audio input."""
        if not self.vr_audio_bridge or not self.vr_audio_bridge.is_available():
            await websocket.send(json.dumps({
                "type": "vr_error",
                "message": "VR Audio Bridge not available"
            }))
            return
        
        try:
            session_id = data.get("session_id") or client_id
            audio_data_base64 = data.get("audio")
            sdp = data.get("sdp")  # Optional: answer SDP from client
            sdp_type = data.get("sdp_type")  # Optional: "answer"
            
            # Set remote description if provided (WebRTC answer from client)
            if sdp and sdp_type:
                await self.vr_audio_bridge.set_remote_description(session_id, sdp, sdp_type)
            
            # Process audio input if provided
            if audio_data_base64:
                audio_data = base64.b64decode(audio_data_base64)
                response_text = await self.vr_audio_bridge.process_vr_audio_input(
                    session_id,
                    audio_data,
                    client_id
                )
                
                await websocket.send(json.dumps({
                    "type": "vr_response",
                    "session_id": session_id,
                    "text": response_text,
                    "status": "processed"
                }))
            else:
                await websocket.send(json.dumps({
                    "type": "vr_response",
                    "session_id": session_id,
                    "status": "connected"
                }))
        
        except Exception as e:
            logger.error(f"Error handling vr_audio: {e}")
            await websocket.send(json.dumps({
                "type": "vr_error",
                "message": str(e)
            }))
    
    async def _handle_cluster_status(
        self,
        websocket: WebSocketServerProtocol,
        client_id: str,
        data: Dict
    ):
        """Handle cluster status request."""
        if not self.cluster_orchestrator:
            await websocket.send(json.dumps({
                "type": "cluster_status",
                "available": False,
                "message": "Cluster orchestrator not available"
            }))
            return
        
        try:
            status = self.cluster_orchestrator.get_cluster_status()
            identity = None
            if self.identity_manager:
                identity = self.identity_manager.get_cluster_identity()
            
            await websocket.send(json.dumps({
                "type": "cluster_status",
                "available": True,
                "cluster": status,
                "identity": identity
            }))
        
        except Exception as e:
            logger.error(f"Error handling cluster_status: {e}")
            await websocket.send(json.dumps({
                "type": "cluster_status",
                "available": False,
                "error": str(e)
            }))
    
    async def _handle_plex_command(
        self,
        websocket: WebSocketServerProtocol,
        client_id: str,
        data: Dict
    ):
        """Handle Plex playback command (play/pause/stop)."""
        if not self.plex_bridge or not self.plex_bridge.is_available():
            await websocket.send(json.dumps({
                "type": "plex_error",
                "message": "Plex bridge not available"
            }))
            return
        
        try:
            command = data.get("command", "play")  # "play", "pause", "stop"
            media_title = data.get("title")
            client_name = data.get("client")  # Plex client name (device)
            
            result = self.plex_bridge.handle_playback_command(
                command=command,
                media_title=media_title,
                client_name=client_name
            )
            
            await websocket.send(json.dumps({
                "type": "plex_result",
                "success": result["success"],
                "message": result["message"],
                "output_data": result.get("output_data", {}),
                "error": result.get("error")
            }))
        
        except Exception as e:
            logger.error(f"Error handling Plex command: {e}")
            await websocket.send(json.dumps({
                "type": "plex_error",
                "message": str(e)
            }))
    
    async def _handle_plex_search(
        self,
        websocket: WebSocketServerProtocol,
        client_id: str,
        data: Dict
    ):
        """Handle Plex media search."""
        if not self.plex_bridge or not self.plex_bridge.is_available():
            await websocket.send(json.dumps({
                "type": "plex_error",
                "message": "Plex bridge not available"
            }))
            return
        
        try:
            query = data.get("query", "")
            media_type = data.get("type", "all")
            limit = data.get("limit", 10)
            
            result = self.plex_bridge.search_media(
                query=query,
                media_type=media_type,
                limit=limit
            )
            
            await websocket.send(json.dumps({
                "type": "plex_search_result",
                "success": result["success"],
                "results": result.get("results", []),
                "count": result.get("count", 0),
                "message": result.get("message"),
                "error": result.get("error")
            }))
        
        except Exception as e:
            logger.error(f"Error handling Plex search: {e}")
            await websocket.send(json.dumps({
                "type": "plex_error",
                "message": str(e)
            }))
    
    async def _handle_file_upload(
        self,
        websocket: WebSocketServerProtocol,
        client_id: str,
        data: Dict
    ):
        """Handle file/image upload for analysis."""
        try:
            # Check if websocket is still open before processing
            if websocket.closed:
                logger.warning(f"WebSocket closed for client {client_id} during file upload")
                return
            
            file_data_base64 = data.get("file_data")
            file_name = data.get("file_name", "uploaded_file")
            file_type = data.get("file_type", "")
            task = data.get("task", "analyze")
            remember = data.get("remember", False)  # Privacy protocol: explicit consent required
            
            if not file_data_base64:
                try:
                    await websocket.send(json.dumps({
                        "type": "file_upload_error",
                        "message": "No file data provided"
                    }))
                except websockets.exceptions.ConnectionClosed:
                    logger.warning(f"Connection closed while sending 'no file data' error to {client_id}")
                except Exception as send_err:
                    logger.error(f"Error sending 'no file data' error: {send_err}")
                return
            
            # Route to file analysis handler
            # Try to use delegation handler if available, otherwise use simple analysis
            try:
                # Import file analysis handler directly
                from delegation.handlers.file_analysis_handler import FileAnalysisHandler
                from delegation.handlers.base import DelegationRequest, HandlerCapability
                
                file_handler = FileAnalysisHandler()
                if file_handler.is_available():
                    # Decode file data
                    try:
                        file_bytes = base64.b64decode(file_data_base64)
                    except Exception as decode_err:
                        logger.error(f"Error decoding base64 file data: {decode_err}")
                        try:
                            await websocket.send(json.dumps({
                                "type": "file_upload_error",
                                "message": f"Invalid file data encoding: {str(decode_err)}"
                            }))
                        except websockets.exceptions.ConnectionClosed:
                            logger.warning(f"Connection closed while sending decode error to {client_id}")
                        except Exception as send_err:
                            logger.error(f"Error sending decode error: {send_err}")
                        return
                    
                    # Use handler
                    request = DelegationRequest(
                        capability=HandlerCapability.IMAGE_PROCESSING if "image" in file_type.lower() else HandlerCapability.CUSTOM,
                        task_description=f"analyze {file_name}",
                        input_data={
                            "file_data": file_data_base64,
                            "file_name": file_name,
                            "file_type": file_type,
                            "task": task,
                            "remember": remember
                        },
                        requires_confirmation=False
                    )
                    
                    # Run file handler in thread pool to avoid blocking event loop
                    # Image analysis can be CPU-intensive and blocking
                    try:
                        loop = asyncio.get_event_loop()
                        result = await loop.run_in_executor(None, file_handler.handle, request)
                    except Exception as handler_err:
                        logger.error(f"Error in file handler execution: {handler_err}", exc_info=True)
                        # Return error result
                        from delegation.handlers.base import DelegationResult
                        result = DelegationResult(
                            success=False,
                            output_data={},
                            message=f"File handler execution failed: {str(handler_err)}",
                            error=str(handler_err)
                        )
                    
                    # Check if result is valid
                    if not result or not hasattr(result, 'success'):
                        logger.error(f"Invalid result object from file handler: {type(result)}")
                        try:
                            await websocket.send(json.dumps({
                                "type": "file_upload_error",
                                "message": "Invalid result from file handler"
                            }))
                        except websockets.exceptions.ConnectionClosed:
                            logger.warning(f"Connection closed while sending invalid result error to {client_id}")
                        except Exception as send_err:
                            logger.error(f"Error sending invalid result error: {send_err}")
                        return
                    
                    if result.success:
                        # Store in memory if user requested to remember
                        if remember and result.output_data and self.memory_manager:
                            summary = f"Analyzed {file_name}: {result.message or 'File analyzed'}"
                            self.memory_manager.add_to_memory(
                                client_id,
                                "assistant",
                                summary,
                                metadata={"file_name": file_name, "file_type": file_type, "task": task}
                            )
                        
                        try:
                            await websocket.send(json.dumps({
                                "type": "file_upload_result",
                                "success": True,
                                "file_name": file_name,
                                "result": result.output_data,
                                "message": result.message,
                                "remembered": remember
                            }))
                        except websockets.exceptions.ConnectionClosed:
                            logger.warning(f"Connection closed while sending file upload result to {client_id}")
                            return
                        except Exception as send_err:
                            logger.error(f"Error sending file upload result: {send_err}")
                            return
                    else:
                        try:
                            await websocket.send(json.dumps({
                                "type": "file_upload_error",
                                "message": result.message or result.error
                            }))
                        except websockets.exceptions.ConnectionClosed:
                            logger.warning(f"Connection closed while sending file upload error to {client_id}")
                            return
                        except Exception as send_err:
                            logger.error(f"Error sending file upload error: {send_err}")
                            return
                else:
                    raise ImportError("File handler not available")
            
            except (ImportError, AttributeError, NameError) as import_err:
                # Fallback: Simple analysis without handler
                logger.warning(f"File handler not available, using simple analysis: {import_err}")
                
                try:
                    file_bytes = base64.b64decode(file_data_base64)
                    analysis_result = await self._analyze_file_simple(file_bytes, file_name, file_type, task, remember)
                    
                    # Store in memory if user requested to remember
                    if remember and analysis_result and self.memory_manager:
                        summary = f"Analyzed {file_name}: {analysis_result.get('description', analysis_result.get('summary', 'File analyzed'))}"
                        self.memory_manager.add_to_memory(
                            client_id,
                            "assistant",
                            summary,
                            metadata={"file_name": file_name, "file_type": file_type, "task": task}
                        )
                    
                    try:
                        await websocket.send(json.dumps({
                            "type": "file_upload_result",
                            "success": True,
                            "file_name": file_name,
                            "result": analysis_result,
                            "remembered": remember
                        }))
                    except websockets.exceptions.ConnectionClosed:
                        logger.warning(f"Connection closed while sending fallback result to {client_id}")
                        return
                    except Exception as send_err:
                        logger.error(f"Error sending fallback result: {send_err}")
                        return
                except Exception as fallback_err:
                    logger.error(f"Error in fallback file analysis: {fallback_err}", exc_info=True)
                    try:
                        await websocket.send(json.dumps({
                            "type": "file_upload_error",
                            "message": f"File analysis failed: {str(fallback_err)}"
                        }))
                    except websockets.exceptions.ConnectionClosed:
                        logger.warning(f"Connection closed while sending fallback error to {client_id}")
                        return
                    except Exception as send_err:
                        logger.error(f"Error sending fallback error: {send_err}")
                        return
            
            except Exception as e:
                logger.error(f"Error analyzing file: {e}", exc_info=True)
                
                try:
                    await websocket.send(json.dumps({
                        "type": "file_upload_error",
                        "message": str(e)
                    }))
                except websockets.exceptions.ConnectionClosed:
                    logger.warning(f"Connection closed while sending error message to {client_id}")
                    return
                except Exception as send_err:
                    logger.error(f"Error sending error message: {send_err}")
                    return
        
        except websockets.exceptions.ConnectionClosed:
            logger.warning(f"Connection closed during file upload for client {client_id}")
            return
        except Exception as e:
            logger.error(f"Error handling file_upload: {e}", exc_info=True)
            
            try:
                await websocket.send(json.dumps({
                    "type": "file_upload_error",
                    "message": str(e)
                }))
            except websockets.exceptions.ConnectionClosed:
                logger.warning(f"Connection already closed, cannot send error message to {client_id}")
                return
            except Exception as send_err:
                logger.error(f"Error sending error message after exception: {send_err}")
                return
    
    async def _analyze_file_simple(self, file_bytes: bytes, file_name: str, file_type: str, task: str, remember: bool) -> Dict[str, Any]:
        """Simple file analysis (placeholder - would use proper handlers in production)."""
        try:
            # Check if image
            if "image" in file_type.lower() or file_name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                try:
                    from PIL import Image
                    image = Image.open(io.BytesIO(file_bytes))
                    width, height = image.size
                    mode = image.mode
                    return {
                        "file_name": file_name,
                        "type": "image",
                        "description": f"Image ({width}x{height} pixels, {mode} color mode)",
                        "dimensions": f"{width}x{height}",
                        "color_mode": mode,
                        "task": task,
                        "note": "Detailed analysis requires LLaVA model installation"
                    }
                except ImportError:
                    return {"file_name": file_name, "error": "PIL/Pillow not available for image analysis"}
            
            # Check if PDF
            elif file_name.lower().endswith('.pdf'):
                try:
                    import PyPDF2
                    pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
                    text_parts = [page.extract_text() for page in pdf_reader.pages[:5]]
                    content = "\n".join(text_parts)
                    return {
                        "file_name": file_name,
                        "type": "PDF",
                        "pages": len(pdf_reader.pages),
                        "content_preview": content[:500],
                        "summary": f"PDF document with {len(pdf_reader.pages)} pages"
                    }
                except ImportError:
                    return {"file_name": file_name, "error": "PyPDF2 not available for PDF parsing"}
            
            # Text file
            elif file_name.lower().endswith(('.txt', '.md')):
                content = file_bytes.decode('utf-8', errors='ignore')
                return {
                    "file_name": file_name,
                    "type": "text",
                    "content_preview": content[:500],
                    "content_length": len(content),
                    "summary": f"Text document with {len(content)} characters"
                }
            
            # Generic file
            else:
                return {
                    "file_name": file_name,
                    "type": "unknown",
                    "size": len(file_bytes),
                    "message": f"File received. Analysis for {file_name} requires specific handler."
                }
        except Exception as e:
            return {"file_name": file_name, "error": str(e)}
    
    async def _handle_voip_call(
        self,
        websocket: WebSocketServerProtocol,
        client_id: str,
        data: Dict
    ):
        """Handle VOIP call initiation."""
        if not self.voip_bridge or not self.voip_bridge.is_available():
            await websocket.send(json.dumps({
                "type": "voip_error",
                "message": "VoIP bridge not available"
            }))
            return
        
        try:
            call_id = data.get("call_id")
            direction = data.get("direction", "incoming")
            device_info = data.get("device_info", {})
            
            offer_result = await self.voip_bridge.handle_incoming_call(
                client_id=client_id,
                call_id=call_id,
                device_info=device_info
            )
            
            if offer_result:
                await websocket.send(json.dumps({
                    "type": "voip_offer",
                    "call_id": offer_result["call_id"],
                    "sdp": offer_result["sdp"],
                    "sdp_type": offer_result["type"],
                    "node_id": offer_result.get("node_id")
                }))
            else:
                await websocket.send(json.dumps({
                    "type": "voip_error",
                    "message": "Failed to create call"
                }))
        
        except Exception as e:
            logger.error(f"Error handling voip_call: {e}")
            await websocket.send(json.dumps({
                "type": "voip_error",
                "message": str(e)
            }))
    
    async def _handle_voip_answer(
        self,
        websocket: WebSocketServerProtocol,
        client_id: str,
        data: Dict
    ):
        """Handle VOIP call answer (WebRTC answer from client)."""
        if not self.voip_bridge or not self.voip_bridge.is_available():
            await websocket.send(json.dumps({
                "type": "voip_error",
                "message": "VoIP bridge not available"
            }))
            return
        
        try:
            call_id = data.get("call_id")
            answer_sdp = data.get("sdp")
            answer_type = data.get("sdp_type", "answer")
            
            if not call_id or not answer_sdp:
                await websocket.send(json.dumps({
                    "type": "voip_error",
                    "message": "call_id and sdp required"
                }))
                return
            
            success = await self.voip_bridge.accept_call(call_id, answer_sdp, answer_type)
            
            if success:
                await websocket.send(json.dumps({
                    "type": "voip_connected",
                    "call_id": call_id,
                    "status": "connected"
                }))
            else:
                await websocket.send(json.dumps({
                    "type": "voip_error",
                    "call_id": call_id,
                    "message": "Failed to accept call"
                }))
        
        except Exception as e:
            logger.error(f"Error handling voip_answer: {e}")
            await websocket.send(json.dumps({
                "type": "voip_error",
                "message": str(e)
            }))
    
    async def _handle_voip_audio(
        self,
        websocket: WebSocketServerProtocol,
        client_id: str,
        data: Dict
    ):
        """Handle VOIP audio input during call."""
        if not self.voip_bridge or not self.voip_bridge.is_available():
            await websocket.send(json.dumps({
                "type": "voip_error",
                "message": "VoIP bridge not available"
            }))
            return
        
        try:
            call_id = data.get("call_id")
            audio_data_base64 = data.get("audio")
            
            if not call_id or not audio_data_base64:
                await websocket.send(json.dumps({
                    "type": "voip_error",
                    "message": "call_id and audio required"
                }))
                return
            
            audio_data = base64.b64decode(audio_data_base64)
            response_text = await self.voip_bridge.process_call_audio(call_id, audio_data)
            
            await websocket.send(json.dumps({
                "type": "voip_response",
                "call_id": call_id,
                "text": response_text,
                "status": "processed"
            }))
        
        except Exception as e:
            logger.error(f"Error handling voip_audio: {e}")
            await websocket.send(json.dumps({
                "type": "voip_error",
                "message": str(e)
            }))
    
    async def _handle_voip_end(
        self,
        websocket: WebSocketServerProtocol,
        client_id: str,
        data: Dict
    ):
        """Handle VOIP call termination."""
        if not self.voip_bridge:
            return
        
        try:
            call_id = data.get("call_id")
            reason = data.get("reason", "normal")
            
            if call_id:
                await self.voip_bridge.end_call(call_id, reason=reason)
                await websocket.send(json.dumps({
                    "type": "voip_ended",
                    "call_id": call_id,
                    "reason": reason
                }))
        except Exception as e:
            logger.error(f"Error handling voip_end: {e}")
    
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
