#!/usr/bin/env python3
"""
Standalone runner for the server (avoids relative import issues)
"""
import sys
import os

# Add server directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from websocket_server import JanetWebSocketServer
from discovery.service_advertiser import ServiceAdvertiser
import asyncio
import signal

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Janet Mesh Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind to")
    parser.add_argument("--no-models", action="store_true", 
                       help="Don't load models at startup")
    parser.add_argument("--no-advertise", action="store_true",
                       help="Don't advertise via Bonjour/mDNS")
    parser.add_argument("--service-name", default="janet-brain",
                       help="Service name for discovery")
    
    args = parser.parse_args()
    
    # Create server
    server = JanetWebSocketServer(
        host=args.host,
        port=args.port,
        load_models=not args.no_models
    )
    
    # Start service advertisement
    advertiser = None
    if not args.no_advertise:
        advertiser = ServiceAdvertiser(
            service_name=args.service_name,
            port=args.port
        )
        advertiser.advertise()
    
    # Handle shutdown
    def signal_handler(sig, frame):
        print("\nShutting down...")
        if advertiser:
            advertiser.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start server
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        pass
    finally:
        if advertiser:
            advertiser.stop()

if __name__ == "__main__":
    main()
