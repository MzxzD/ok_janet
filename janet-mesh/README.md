# Janet Mesh Network

A fully offline, local network cluster where Janet-seed runs as a central brain server, with multiple client devices (Mac, iPhone, Linux, Android) connecting via local WiFi. All STT, TTS, and LLM models run locally with no external API dependencies.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│ iOS Client  │────▶│ Swift Server │────▶│Python Server│
└─────────────┘     │  (Vapor)     │     │ (Janet-seed)│
                    └──────────────┘     └─────────────┘
┌─────────────┐           │                      │
│Android Client│──────────┘                      │
└─────────────┘                                  │
                                                 ▼
                                    ┌─────────────────────┐
                                    │  Models (Local)     │
                                    │  - Whisper (STT)    │
                                    │  - TTS (Piper)      │
                                    │  - LLM (Janet-seed) │
                                    │    → DeepSeek/LiteLLM│
                                    │    → Ollama (fallback)│
                                    └─────────────────────┘
```

## Features

- **Fully Offline**: No external API calls
- **Multi-Client Support**: Multiple devices with isolated memory contexts
- **Service Discovery**: Automatic device discovery via Bonjour/mDNS
- **Distributed Processing**: Optional STT/TTS nodes
- **Cross-Platform**: iOS, Android, macOS, Linux clients

## Quick Start

### 1. Setup Python Server

```bash
cd janet-mesh
pip install -r requirements.txt

# Install Janet-seed (for DeepSeek LLM)
git clone https://github.com/MzxzD/Janet-seed.git janet-seed
# See INSTALL_JANET_SEED.md for DeepSeek configuration

python scripts/setup_models.sh
python server/run.py
```

### 2. Setup Swift Server (Optional Relay)

```bash
cd swift-server
swift build
swift run
```

### 3. Connect Client

- iOS: Open the SwiftUI app and connect to `ws://<server-ip>:8080/ws`
- Or use the Python server directly: `ws://<server-ip>:8765`

## Configuration

### Server Options

```bash
python server/run.py --help
```

Options:
- `--host`: Host to bind to (default: 0.0.0.0)
- `--port`: Port to bind to (default: 8765)
- `--no-models`: Don't load models at startup
- `--no-advertise`: Don't advertise via Bonjour
- `--service-name`: Service name for discovery

### Model Configuration

**LLM Backend**: By default, Janet Mesh uses Janet-seed with DeepSeek (via LiteLLM). If Janet-seed is not available, it falls back to Ollama.

- **Janet-seed + DeepSeek** (default): See [INSTALL_JANET_SEED.md](INSTALL_JANET_SEED.md)
- **Ollama** (fallback): Install from https://ollama.ai and run `ollama pull llama2`

**Other Models**: Automatically downloaded on first use. To pre-download:

```bash
./scripts/setup_models.sh
```

## Docker Deployment

### Brain Server

```bash
docker-compose up brain
```

### All Services

```bash
docker-compose up
```

## Development

### Project Structure

```
janet-mesh/
├── server/              # Python server
│   ├── core/           # Janet-seed integration
│   ├── models/         # Model management
│   ├── services/       # STT, TTS services
│   └── discovery/      # Service discovery
├── swift-server/       # Vapor WebSocket relay
├── clients/            # Client applications
│   ├── ios/           # SwiftUI iOS app
│   ├── android/       # Android app
│   └── mac/           # macOS app
├── docker/             # Docker configurations
└── scripts/            # Utility scripts
```

## Protocol

### WebSocket Messages

**Client → Server:**
```json
{
  "type": "audio_chunk",
  "audio": "<base64-encoded-audio>"
}
```

```json
{
  "type": "text_input",
  "text": "Hello, Janet!"
}
```

**Server → Client:**
```json
{
  "type": "response",
  "text": "Hello! How can I help?",
  "user_text": "Hello, Janet!",
  "audio": "<base64-encoded-audio>",
  "audio_format": "wav"
}
```

## Requirements

### Server
- Python 3.11+
- 8GB+ RAM (16GB recommended)
- GPU optional but recommended

### Models
- Whisper base: ~1.5GB
- TTS model: ~500MB
- LLM: 
  - **Janet-seed + DeepSeek** (recommended): Via LiteLLM (API or local)
  - **Ollama** (fallback): Llama 2 (4-13GB) or other models

## License

[Your License Here]

## Contributing

[Contributing Guidelines]
