# Installation Guide

## Prerequisites

### Server Requirements
- Python 3.11 or higher
- 8GB+ RAM (16GB recommended for larger models)
- macOS, Linux, or Windows (WSL)
- Optional: GPU for faster inference

### Client Requirements
- iOS 16+ (for iOS client)
- Android 8+ (for Android client)
- macOS 13+ (for macOS client)

## Step 1: Install Python Dependencies

```bash
cd janet-mesh
pip install -r requirements.txt
```

## Step 2: Install Janet-seed (Recommended)

Janet Mesh uses Janet-seed with DeepSeek for LLM processing:

```bash
cd janet-mesh
git clone https://github.com/MzxzD/Janet-seed.git janet-seed
```

See [INSTALL_JANET_SEED.md](INSTALL_JANET_SEED.md) for detailed setup and DeepSeek configuration.

## Step 3: Setup Models

Run the model setup script:

```bash
./scripts/setup_models.sh
```

This will download:
- Whisper STT model (base, ~1.5GB)
- Piper TTS model (~500MB)
- Janet-seed will use DeepSeek via LiteLLM (configure in Janet-seed)
- Ollama LLM (fallback if Janet-seed unavailable)

### Manual Model Setup

#### Whisper
```bash
pip install openai-whisper
python -c "import whisper; whisper.load_model('base')"
```

#### TTS (Piper)
```bash
pip install piper-tts
# Models will be downloaded on first use
```

#### LLM (Janet-seed + DeepSeek)
```bash
# Install Janet-seed
git clone https://github.com/MzxzD/Janet-seed.git janet-seed

# Configure DeepSeek in Janet-seed's LiteLLM router
# See INSTALL_JANET_SEED.md for details
```

#### LLM (Ollama - Fallback)
```bash
# Install Ollama from https://ollama.ai
ollama pull llama2
# Used as fallback if Janet-seed is not available
```

## Step 4: Start the Server

### Option A: Direct Python

```bash
python server/run.py
```

Or with options:
```bash
python server/run.py --host 0.0.0.0 --port 8765 --service-name janet-brain
```

### Option B: Docker

```bash
docker-compose up brain
```

## Step 5: Start Swift Server (Optional)

The Swift server acts as a relay between clients and the Python server.

```bash
cd swift-server
swift build
swift run
```

## Step 6: Connect Clients

### iOS Client
1. Open the project in Xcode
2. Build and run on device or simulator
3. Enter server URL: `ws://<server-ip>:8080/ws`
4. Connect and start chatting

### Test Client (Python)
```bash
python scripts/test_client.py ws://localhost:8765
```

## Troubleshooting

### Models Not Loading
- Check available disk space (models require several GB)
- Verify internet connection for initial download
- Check model paths in configuration

### Janet-seed Not Found
- Ensure Janet-seed is cloned: `git clone https://github.com/MzxzD/Janet-seed.git janet-seed`
- Or set `JANET_SEED_PATH` environment variable
- Check that `janet-seed/src/core/janet_core.py` exists
- See [INSTALL_JANET_SEED.md](INSTALL_JANET_SEED.md) for troubleshooting

### Connection Issues
- Verify server is running: `curl http://localhost:8765/status`
- Check firewall settings
- Ensure clients are on same network

### Performance Issues
- Use smaller models (Whisper tiny instead of base)
- Enable GPU acceleration if available
- Reduce concurrent clients

## Next Steps

- See [README.md](README.md) for usage
- See [INSTALL_JANET_SEED.md](INSTALL_JANET_SEED.md) for Janet-seed and DeepSeek setup
- Check logs for detailed error messages

## Janet-seed Integration

Janet Mesh integrates with [Janet-seed](https://github.com/MzxzD/Janet-seed) to provide:
- **DeepSeek LLM** via LiteLLM router
- **Constitutional AI** following 16 axioms
- **Memory vault system** (Green/Blue/Red)
- **Delegation system** for task routing

The integration maintains multi-client support while leveraging Janet-seed's advanced capabilities.
