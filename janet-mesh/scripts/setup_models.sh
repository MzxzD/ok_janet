#!/bin/bash

# Setup script to download and prepare models

set -e

echo "📦 Setting up models for Janet Mesh..."

MODELS_DIR="./models"
mkdir -p "$MODELS_DIR"

# Download Whisper model
echo "Downloading Whisper model (base)..."
python -c "import whisper; whisper.load_model('base')" || {
    echo "Installing Whisper..."
    pip install openai-whisper
    python -c "import whisper; whisper.load_model('base')"
}

# Download TTS model (Piper)
echo "Downloading Piper TTS model..."
pip install piper-tts || true
python -c "from piper.download import ensure_voice_exists; ensure_voice_exists('en_US-lessac-medium', ['$MODELS_DIR/piper'])" || {
    echo "Piper TTS setup failed. Using fallback."
}

# Setup Ollama (if available)
if command -v ollama &> /dev/null; then
    echo "Setting up Ollama..."
    ollama pull llama2 || echo "Ollama model pull failed"
else
    echo "Ollama not installed. Install from https://ollama.ai"
fi

echo "✅ Model setup complete!"
echo "Models directory: $MODELS_DIR"
