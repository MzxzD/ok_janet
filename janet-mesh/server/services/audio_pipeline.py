"""
Audio Processing Pipeline - Handles STT, TTS, and audio processing
"""
import base64
import io
import wave
import numpy as np
from typing import Optional, Tuple, Dict, Any
import tempfile
import os


class AudioPipeline:
    """Processes audio through STT -> LLM -> TTS pipeline"""
    
    def __init__(self, stt_model: Any, tts_model: Any, janet_adapter: Any):
        self.stt_model = stt_model
        self.tts_model = tts_model
        self.janet_adapter = janet_adapter
        self.audio_buffer: Dict[str, list] = {}  # client_id -> audio chunks
    
    def process_audio_chunk(self, client_id: str, audio_data: bytes, 
                           sample_rate: int = 16000) -> Optional[Dict[str, Any]]:
        """
        Process an audio chunk. Returns response when utterance is complete.
        """
        # Buffer audio chunks
        if client_id not in self.audio_buffer:
            self.audio_buffer[client_id] = []
        
        self.audio_buffer[client_id].append(audio_data)
        
        # For now, process immediately. In production, use VAD (Voice Activity Detection)
        # to detect when user stops speaking
        return None
    
    def process_complete_audio(self, client_id: str, 
                               audio_data: bytes) -> Dict[str, Any]:
        """
        Process complete audio utterance and return response
        """
        # Clear buffer for this client
        if client_id in self.audio_buffer:
            del self.audio_buffer[client_id]
        
        # Convert audio bytes to format Whisper expects
        audio_array = self._bytes_to_audio(audio_data)
        
        # Run STT
        transcription = self._transcribe(audio_array)
        user_text = transcription.get("text", "").strip()
        
        if not user_text:
            return {
                "text": "",
                "audio": None,
                "error": "No speech detected"
            }
        
        # Get response from Janet
        response_text = self.janet_adapter.generate_response(client_id, user_text)
        
        # Generate TTS audio
        response_audio = self._text_to_speech(response_text)
        
        # Encode audio to base64
        audio_base64 = base64.b64encode(response_audio).decode('utf-8')
        
        return {
            "text": response_text,
            "user_text": user_text,
            "audio": audio_base64,
            "audio_format": "wav",
            "sample_rate": 22050
        }
    
    def _bytes_to_audio(self, audio_data: bytes) -> np.ndarray:
        """Convert audio bytes to numpy array"""
        # Try to read as WAV
        try:
            audio_io = io.BytesIO(audio_data)
            with wave.open(audio_io, 'rb') as wav_file:
                frames = wav_file.readframes(-1)
                sound_info = np.frombuffer(frames, dtype=np.int16)
                sample_rate = wav_file.getframerate()
                return sound_info.astype(np.float32) / 32768.0
        except:
            # Assume raw PCM
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            return audio_array.astype(np.float32) / 32768.0
    
    def _transcribe(self, audio_array: np.ndarray) -> Dict[str, Any]:
        """Transcribe audio using Whisper"""
        if self.stt_model is None:
            raise RuntimeError("STT model not loaded")
        
        # Save to temporary file for Whisper
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
            # Convert to int16 and save as WAV
            audio_int16 = (audio_array * 32768.0).astype(np.int16)
            with wave.open(tmp_file.name, 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(16000)  # 16kHz
                wav_file.writeframes(audio_int16.tobytes())
            
            # Transcribe
            result = self.stt_model.transcribe(tmp_file.name)
            
            # Clean up
            os.unlink(tmp_file.name)
            
            return result
    
    def _text_to_speech(self, text: str) -> bytes:
        """Convert text to speech audio"""
        if self.tts_model is None:
            raise RuntimeError("TTS model not loaded")
        
        # Check model type
        if hasattr(self.tts_model, "synthesize"):
            # Piper TTS
            audio_generator = self.tts_model.synthesize(text)
            audio_bytes = b''.join(audio_generator)
            return audio_bytes
        
        elif hasattr(self.tts_model, "tts"):
            # Coqui TTS
            audio_array = self.tts_model.tts(text)
            # Convert to bytes (WAV format)
            return self._audio_array_to_wav(audio_array)
        
        else:
            raise RuntimeError("Unknown TTS model type")
    
    def _audio_array_to_wav(self, audio_array: np.ndarray, 
                           sample_rate: int = 22050) -> bytes:
        """Convert numpy audio array to WAV bytes"""
        # Normalize to int16
        audio_int16 = (audio_array * 32768.0).astype(np.int16)
        
        # Create WAV file in memory
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_int16.tobytes())
        
        return wav_buffer.getvalue()
    
    def clear_buffer(self, client_id: str):
        """Clear audio buffer for a client"""
        if client_id in self.audio_buffer:
            del self.audio_buffer[client_id]
