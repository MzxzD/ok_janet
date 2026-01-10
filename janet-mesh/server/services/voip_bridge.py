"""
VoIP Bridge - Real-time phone calling with Janet via WebRTC
Uses existing WebRTC infrastructure from VR bridge with cluster-aware routing
Integrates with CallKit/PushKit for native iOS calling experience
"""
import logging
import asyncio
import base64
import json
import uuid
from typing import Dict, Optional, List, Any, Callable
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)

try:
    import aiortc
    from aiortc import RTCPeerConnection, RTCSessionDescription, AudioStreamTrack
    from aiortc.contrib.media import MediaPlayer, MediaRelay
    WEBRTC_AVAILABLE = True
except ImportError:
    WEBRTC_AVAILABLE = False
    RTCPeerConnection = None
    RTCSessionDescription = None
    AudioStreamTrack = None
    MediaPlayer = None
    MediaRelay = None


class CallState(Enum):
    """Call state enumeration."""
    IDLE = "idle"
    RINGING = "ringing"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ON_HOLD = "on_hold"
    ENDED = "ended"


class VoIPCall:
    """Represents an active VoIP call."""
    def __init__(
        self,
        call_id: str,
        client_id: str,
        direction: str,  # "incoming" or "outgoing"
        node_id: Optional[str] = None
    ):
        self.call_id = call_id
        self.client_id = client_id
        self.direction = direction
        self.node_id = node_id  # Node handling the call (for cluster routing)
        self.state = CallState.IDLE
        self.created_at = datetime.utcnow()
        self.connected_at: Optional[datetime] = None
        self.ended_at: Optional[datetime] = None
        self.peer_connection: Optional[RTCPeerConnection] = None
        self.audio_track: Optional[AudioStreamTrack] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "call_id": self.call_id,
            "client_id": self.client_id,
            "direction": self.direction,
            "node_id": self.node_id,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "connected_at": self.connected_at.isoformat() if self.connected_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None
        }


class VoIPBridge:
    """
    VoIP bridge for real-time phone calling with Janet.
    
    Features:
    - WebRTC audio streaming (reuses VR audio bridge infrastructure)
    - Cluster-aware call routing (uses cluster orchestrator)
    - STT/TTS integration for real-time conversation
    - Call state management
    - Integration with CallKit/PushKit (iOS side)
    """
    
    def __init__(
        self,
        audio_pipeline=None,
        janet_adapter=None,
        cluster_orchestrator=None,
        identity_manager=None
    ):
        """
        Initialize VoIP Bridge.
        
        Args:
            audio_pipeline: AudioPipeline instance for STT/TTS
            janet_adapter: JanetAdapter instance for generating responses
            cluster_orchestrator: ClusterOrchestrator instance (for routing)
            identity_manager: IdentityManager instance (for node selection)
        """
        self.audio_pipeline = audio_pipeline
        self.janet_adapter = janet_adapter
        self.cluster_orchestrator = cluster_orchestrator
        self.identity_manager = identity_manager
        self.webrtc_available = WEBRTC_AVAILABLE
        
        # Active calls
        self.active_calls: Dict[str, VoIPCall] = {}
        self.call_history: List[Dict[str, Any]] = []
        
        # Audio tracks per call
        self.call_audio_tracks: Dict[str, AudioStreamTrack] = {}
        
        # Callbacks
        self.on_incoming_call: Optional[Callable[[VoIPCall], None]] = None
        self.on_call_state_change: Optional[Callable[[str, CallState], None]] = None
    
    def is_available(self) -> bool:
        """Check if VoIP bridge is available."""
        return self.webrtc_available and WEBRTC_AVAILABLE
    
    async def handle_incoming_call(
        self,
        client_id: str,
        call_id: Optional[str] = None,
        device_info: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Handle incoming call request from client.
        
        Args:
            client_id: Client identifier
            call_id: Optional call identifier (generates if None)
            device_info: Optional device information (iOS, Android, etc.)
            
        Returns:
            WebRTC offer dictionary or None if unavailable
        """
        if not self.is_available():
            logger.warning("VoIP bridge not available - WebRTC not installed")
            return None
        
        call_id = call_id or str(uuid.uuid4())
        
        # Route call to best node (if in cluster mode)
        target_node_id = None
        if self.cluster_orchestrator and self.identity_manager:
            target_node_id = self.identity_manager.get_least_loaded_node()
            if self.identity_manager.is_prime_instance():
                # This node is handling the call
                target_node_id = self.identity_manager.node_id
            logger.info(f"Call routed to node: {target_node_id}")
        
        # Create call object
        call = VoIPCall(
            call_id=call_id,
            client_id=client_id,
            direction="incoming",
            node_id=target_node_id
        )
        call.state = CallState.RINGING
        self.active_calls[call_id] = call
        
        # Notify callback
        if self.on_incoming_call:
            try:
                self.on_incoming_call(call)
            except Exception as e:
                logger.error(f"Error in incoming call callback: {e}")
        
        # Create WebRTC peer connection
        try:
            pc = RTCPeerConnection()
            
            # Create audio track for Janet's voice (TTS output)
            audio_track = VoIPAudioTrack(self.audio_pipeline, call_id)
            pc.addTrack(audio_track)
            
            # Store connection and track
            call.peer_connection = pc
            call.audio_track = audio_track
            self.call_audio_tracks[call_id] = audio_track
            
            # Create offer
            offer = await pc.createOffer()
            await pc.setLocalDescription(offer)
            
            call.state = CallState.CONNECTING
            self._notify_call_state_change(call_id, CallState.CONNECTING)
            
            logger.info(f"Created VoIP call: {call_id} for client: {client_id}")
            
            return {
                "call_id": call_id,
                "sdp": pc.localDescription.sdp,
                "type": pc.localDescription.type,
                "node_id": target_node_id
            }
        
        except Exception as e:
            logger.error(f"Error creating VoIP peer connection: {e}")
            call.state = CallState.ENDED
            self._notify_call_state_change(call_id, CallState.ENDED)
            return None
    
    async def accept_call(
        self,
        call_id: str,
        answer_sdp: str,
        answer_type: str
    ) -> bool:
        """
        Accept call by setting remote description (answer from client).
        
        Args:
            call_id: Call identifier
            answer_sdp: Answer SDP from client
            answer_type: SDP type ("answer")
            
        Returns:
            True if successful
        """
        if call_id not in self.active_calls:
            logger.error(f"Call not found: {call_id}")
            return False
        
        call = self.active_calls[call_id]
        
        if not call.peer_connection:
            logger.error(f"No peer connection for call: {call_id}")
            return False
        
        try:
            answer = RTCSessionDescription(sdp=answer_sdp, type=answer_type)
            await call.peer_connection.setRemoteDescription(answer)
            
            call.state = CallState.CONNECTED
            call.connected_at = datetime.utcnow()
            self._notify_call_state_change(call_id, CallState.CONNECTED)
            
            logger.info(f"Call {call_id} connected")
            return True
        
        except Exception as e:
            logger.error(f"Error accepting call: {e}")
            call.state = CallState.ENDED
            self._notify_call_state_change(call_id, CallState.ENDED)
            return False
    
    async def process_call_audio(
        self,
        call_id: str,
        audio_data: bytes
    ) -> Optional[str]:
        """
        Process audio input from call (STT → LLM → TTS).
        
        Args:
            call_id: Call identifier
            audio_data: Audio bytes (WAV format)
            
        Returns:
            Response text or None
        """
        if call_id not in self.active_calls:
            logger.warning(f"Call not found: {call_id}")
            return None
        
        call = self.active_calls[call_id]
        if call.state != CallState.CONNECTED:
            logger.warning(f"Call {call_id} not in connected state: {call.state}")
            return None
        
        if not self.audio_pipeline or not self.janet_adapter:
            logger.warning("Audio pipeline or Janet adapter not available")
            return None
        
        try:
            # Process audio through pipeline
            response_dict = self.audio_pipeline.process_complete_audio(
                call.client_id,
                audio_data
            )
            
            user_text = response_dict.get("user_text", "")
            response_text = response_dict.get("text", "")
            
            # Generate response if not already generated
            if not response_text and user_text:
                response_text = self.janet_adapter.generate_response(
                    call.client_id,
                    user_text
                )
            
            # Generate TTS audio and stream to call
            if response_text and self.audio_pipeline:
                response_audio = self.audio_pipeline._text_to_speech(response_text)
                
                # Stream audio to call
                if call.audio_track:
                    await call.audio_track.queue_audio(response_audio)
            
            return response_text
        
        except Exception as e:
            logger.error(f"Error processing call audio: {e}")
            return None
    
    async def end_call(self, call_id: str, reason: Optional[str] = None):
        """End a call and clean up resources."""
        if call_id not in self.active_calls:
            return
        
        call = self.active_calls[call_id]
        
        try:
            # Close peer connection
            if call.peer_connection:
                await call.peer_connection.close()
            
            # Remove audio track
            if call_id in self.call_audio_tracks:
                del self.call_audio_tracks[call_id]
            
            # Update call state
            call.state = CallState.ENDED
            call.ended_at = datetime.utcnow()
            
            # Move to history
            self.call_history.append(call.to_dict())
            
            # Remove from active calls
            del self.active_calls[call_id]
            
            self._notify_call_state_change(call_id, CallState.ENDED)
            
            logger.info(f"Call {call_id} ended: {reason or 'normal'}")
        
        except Exception as e:
            logger.error(f"Error ending call: {e}")
    
    def get_call_status(self, call_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a call."""
        if call_id not in self.active_calls:
            return None
        
        call = self.active_calls[call_id]
        return call.to_dict()
    
    def _notify_call_state_change(self, call_id: str, state: CallState):
        """Notify callback of call state change."""
        if self.on_call_state_change:
            try:
                self.on_call_state_change(call_id, state)
            except Exception as e:
                logger.error(f"Error in call state change callback: {e}")


class VoIPAudioTrack(AudioStreamTrack):
    """Audio track for VoIP call streaming."""
    def __init__(self, audio_pipeline=None, call_id: str = ""):
        super().__init__()
        self.audio_pipeline = audio_pipeline
        self.call_id = call_id
        self.audio_queue = asyncio.Queue()
    
    async def queue_audio(self, audio_data: bytes):
        """Queue audio data for streaming."""
        try:
            await self.audio_queue.put(audio_data)
        except Exception as e:
            logger.error(f"Error queueing audio for call {self.call_id}: {e}")
    
    async def recv(self):
        """Receive audio frame for streaming."""
        try:
            audio_data = await asyncio.wait_for(self.audio_queue.get(), timeout=0.1)
            # Convert bytes to audio frame format
            # This is simplified - in production, convert to proper audio frame
            # For WebRTC, we need to return a proper audio frame object
            # This is a placeholder implementation
            return audio_data
        except asyncio.TimeoutError:
            # Return silence if no audio available
            try:
                import numpy as np
                silence = np.zeros((16000,), dtype=np.int16)  # 1 second of silence at 16kHz
                return silence
            except ImportError:
                # Fallback if numpy not available
                return b'\x00' * 32000  # 1 second of silence as bytes (16-bit, 16kHz, mono)
