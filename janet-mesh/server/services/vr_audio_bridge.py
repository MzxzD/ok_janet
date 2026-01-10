"""
VR Audio Bridge - WebRTC data channel for real-time audio streaming
Bi-directional: Operator voice → Janet Mesh → TTS → VR client
Low-latency audio pipeline (target: <100ms)
"""
import logging
import asyncio
import base64
import json
from typing import Dict, Optional, Any, Callable
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    import aiortc
    from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, AudioStreamTrack
    from aiortc.contrib.media import MediaPlayer, MediaRelay
    WEBRTC_AVAILABLE = True
except ImportError:
    WEBRTC_AVAILABLE = False
    RTCPeerConnection = None
    RTCSessionDescription = None
    VideoStreamTrack = None
    AudioStreamTrack = None
    MediaPlayer = None
    MediaRelay = None


class VRAudioTrack(AudioStreamTrack):
    """Audio track for VR client streaming."""
    def __init__(self, audio_pipeline=None):
        super().__init__()
        self.audio_pipeline = audio_pipeline
        self.audio_queue = asyncio.Queue()
    
    async def recv(self):
        """Receive audio frame for streaming."""
        try:
            audio_data = await asyncio.wait_for(self.audio_queue.get(), timeout=0.1)
            return audio_data
        except asyncio.TimeoutError:
            # Return silence if no audio available
            import numpy as np
            silence = np.zeros((16000,), dtype=np.int16)  # 1 second of silence at 16kHz
            return silence


class VRAudioBridge:
    """
    WebRTC audio bridge for VR client.
    
    Provides:
    - Real-time audio streaming via WebRTC data channel
    - Bi-directional: Operator voice → Janet Mesh → TTS → VR client
    - Low-latency audio pipeline (target: <100ms)
    - Integration with existing audio_pipeline.py
    """
    
    def __init__(
        self,
        audio_pipeline=None,
        janet_adapter=None
    ):
        """
        Initialize VR Audio Bridge.
        
        Args:
            audio_pipeline: AudioPipeline instance for TTS
            janet_adapter: JanetAdapter instance for generating responses
        """
        self.audio_pipeline = audio_pipeline
        self.janet_adapter = janet_adapter
        self.webrtc_available = WEBRTC_AVAILABLE
        
        # WebRTC connections
        self.peer_connections: Dict[str, RTCPeerConnection] = {}
        self.audio_tracks: Dict[str, VRAudioTrack] = {}
        
        # Active VR sessions
        self.vr_sessions: Dict[str, Dict[str, Any]] = {}
    
    async def create_peer_connection(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Create WebRTC peer connection for VR client.
        
        Args:
            session_id: VR session identifier
            
        Returns:
            Dictionary with offer SDP and ICE candidates, or None if WebRTC unavailable
        """
        if not self.webrtc_available:
            logger.warning("WebRTC not available - VR audio bridge unavailable")
            return None
        
        try:
            # Create peer connection
            pc = RTCPeerConnection()
            
            # Create audio track
            audio_track = VRAudioTrack(self.audio_pipeline)
            pc.addTrack(audio_track)
            
            # Store connection and track
            self.peer_connections[session_id] = pc
            self.audio_tracks[session_id] = audio_track
            
            # Create offer
            offer = await pc.createOffer()
            await pc.setLocalDescription(offer)
            
            # Store session
            self.vr_sessions[session_id] = {
                "session_id": session_id,
                "created_at": datetime.utcnow().isoformat(),
                "status": "connecting"
            }
            
            logger.info(f"Created WebRTC peer connection for VR session: {session_id}")
            
            return {
                "sdp": pc.localDescription.sdp,
                "type": pc.localDescription.type,
                "session_id": session_id
            }
        
        except Exception as e:
            logger.error(f"Error creating peer connection: {e}")
            return None
    
    async def set_remote_description(
        self,
        session_id: str,
        sdp: str,
        sdp_type: str
    ) -> bool:
        """
        Set remote description (answer from VR client).
        
        Args:
            session_id: VR session identifier
            sdp: SDP string
            sdp_type: SDP type ("answer")
            
        Returns:
            True if successful
        """
        if session_id not in self.peer_connections:
            logger.error(f"Peer connection not found for session: {session_id}")
            return False
        
        try:
            pc = self.peer_connections[session_id]
            answer = RTCSessionDescription(sdp=sdp, type=sdp_type)
            await pc.setRemoteDescription(answer)
            
            logger.info(f"Set remote description for VR session: {session_id}")
            
            # Update session status
            if session_id in self.vr_sessions:
                self.vr_sessions[session_id]["status"] = "connected"
            
            return True
        
        except Exception as e:
            logger.error(f"Error setting remote description: {e}")
            return False
    
    async def stream_audio_to_vr(
        self,
        session_id: str,
        audio_data: bytes
    ):
        """
        Stream audio data to VR client.
        
        Args:
            session_id: VR session identifier
            audio_data: Audio bytes (WAV format)
        """
        if session_id not in self.audio_tracks:
            logger.warning(f"Audio track not found for session: {session_id}")
            return
        
        try:
            audio_track = self.audio_tracks[session_id]
            await audio_track.audio_queue.put(audio_data)
        except Exception as e:
            logger.error(f"Error streaming audio to VR: {e}")
    
    async def process_vr_audio_input(
        self,
        session_id: str,
        audio_data: bytes,
        client_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Process audio input from VR client (STT → LLM → TTS).
        
        Args:
            session_id: VR session identifier
            audio_data: Audio bytes from VR client
            client_id: Optional client identifier
            
        Returns:
            Response text or None
        """
        if not self.audio_pipeline or not self.janet_adapter:
            logger.warning("Audio pipeline or Janet adapter not available")
            return None
        
        try:
            # Use audio pipeline for STT
            response_dict = self.audio_pipeline.process_complete_audio(
                client_id or session_id,
                audio_data
            )
            
            user_text = response_dict.get("user_text", "")
            response_text = response_dict.get("text", "")
            
            # Generate response if not already generated
            if not response_text and self.janet_adapter and user_text:
                response_text = self.janet_adapter.generate_response(
                    client_id or session_id,
                    user_text
                )
            
            # Generate TTS audio
            if response_text and self.audio_pipeline:
                response_audio = self.audio_pipeline._text_to_speech(response_text)
                
                # Stream audio back to VR client
                await self.stream_audio_to_vr(session_id, response_audio)
            
            return response_text
        
        except Exception as e:
            logger.error(f"Error processing VR audio input: {e}")
            return None
    
    async def close_session(self, session_id: str):
        """Close VR session and clean up resources."""
        try:
            # Close peer connection
            if session_id in self.peer_connections:
                pc = self.peer_connections[session_id]
                await pc.close()
                del self.peer_connections[session_id]
            
            # Remove audio track
            if session_id in self.audio_tracks:
                del self.audio_tracks[session_id]
            
            # Remove session
            if session_id in self.vr_sessions:
                del self.vr_sessions[session_id]
            
            logger.info(f"Closed VR session: {session_id}")
        
        except Exception as e:
            logger.error(f"Error closing VR session: {e}")
    
    def is_available(self) -> bool:
        """Check if VR audio bridge is available."""
        return self.webrtc_available and WEBRTC_AVAILABLE
