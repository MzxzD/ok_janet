# Quick Start Guide

Get Janet Mesh running in 5 minutes!

## 1. Install Dependencies

```bash
pip install -r requirements.txt
```

## 2. Start Server

```bash
python server/run.py
```

The server will:
- Load models (first time may take a few minutes)
- Start WebSocket server on port 8765
- Advertise via Bonjour/mDNS

## 3. Test Connection

In another terminal:

```bash
python scripts/test_client.py
```

You should see:
```
Connected to ws://localhost:8765
Server: {"type": "connected", "client_id": "...", "status": "ready"}
Sending: Hello, Janet!
Response: [Janet's response]
```

## 4. Connect iOS Client

1. Open `clients/ios/` in Xcode
2. Build and run
3. Enter server URL: `ws://<your-ip>:8765`
4. Start chatting!

## Server Options

```bash
# Don't load models at startup (faster startup)
python server/run.py --no-models

# Custom port
python server/run.py --port 9000

# Don't advertise via Bonjour
python server/run.py --no-advertise
```

## Troubleshooting

**Server won't start?**
- Check Python version: `python --version` (need 3.11+)
- Check port availability: `lsof -i :8765`

**Models not loading?**
- First run downloads models (can take 10+ minutes)
- Check disk space (need ~5GB free)
- Check internet connection

**Can't connect from client?**
- Ensure server is running: `curl http://localhost:8765/status`
- Check firewall settings
- Verify same network

## Next Steps

- See [README.md](README.md) for full documentation
- See [INSTALL.md](INSTALL.md) for detailed setup
- Customize models in `server/models/model_loader.py`
