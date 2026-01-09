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


class JanetWebSocketServer:
    """WebSocket server for Janet mesh network"""
    
    def __init__(self, host: str = "localhost", port: int = 8765,
                 load_models: bool = True):
        self.host = host
        self.port = port
        self.connected_clients: Set[str] = set()
        
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
                self.session_manager.end_session(client_id)
    
    async def _handle_message(self, websocket: WebSocketServerProtocol, 
                            client_id: str, message: str):
        """Handle incoming message from client"""
        try:
            data = json.loads(message)
            msg_type = data.get("type")
            
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
                    "audio_format": response.get("audio_format", "wav")
                }))
            
            elif msg_type == "text_input":
                # Handle text input directly
                user_text = data.get("text", "")
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
                        "audio_format": "wav" if audio_base64 else None
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
        async with websockets.serve(self.handle_client, self.host, self.port):
            logger.info("Server started, waiting for connections...")
            await asyncio.Future()  # Run forever
    
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
