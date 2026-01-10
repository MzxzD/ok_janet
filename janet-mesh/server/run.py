#!/usr/bin/env python3
"""
Standalone runner for the server (avoids relative import issues)
"""
import sys
import os
import warnings

# Suppress harmless weak reference warnings during shutdown
warnings.filterwarnings("ignore", category=RuntimeWarning, message=".*weakref.*")

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
    
    # Handle shutdown gracefully
    import threading
    shutdown_flag = threading.Event()
    server_task_ref = {'task': None}
    loop_ref = {'loop': None}
    
    def signal_handler(sig, frame):
        if not shutdown_flag.is_set():
            shutdown_flag.set()
            print("\nShutting down...")
            if advertiser:
                advertiser.stop()
            # Force shutdown by cancelling the server task
            loop = loop_ref.get('loop')
            if loop and not loop.is_closed():
                # Cancel server task
                task = server_task_ref.get('task')
                if task and not task.done():
                    loop.call_soon_threadsafe(task.cancel)
                # Also set the shutdown event in the server
                try:
                    loop.call_soon_threadsafe(server.shutdown)
                except:
                    pass
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start server with shutdown handling
    async def run_with_shutdown():
        loop = asyncio.get_running_loop()
        loop_ref['loop'] = loop
        
        # Start the server
        server_task = asyncio.create_task(server.start())
        server_task_ref['task'] = server_task
        
        # Create a task that monitors the shutdown flag
        async def monitor_shutdown():
            while not shutdown_flag.is_set():
                await asyncio.sleep(0.1)
            # Cancel server task if still running
            if server_task and not server_task.done():
                server_task.cancel()
            server.shutdown()
        
        monitor_task = asyncio.create_task(monitor_shutdown())
        
        try:
            # Wait for either task to complete
            done, pending = await asyncio.wait(
                [server_task, monitor_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            # Cancel any pending tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        except asyncio.CancelledError:
            # Server was cancelled - that's fine
            pass
        except KeyboardInterrupt:
            # Force immediate shutdown
            if server_task and not server_task.done():
                server_task.cancel()
            server.shutdown()
            raise
    
    # Start server
    try:
        asyncio.run(run_with_shutdown())
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        # Suppress errors during shutdown
        if not shutdown_flag.is_set():
            print(f"Error: {e}")
    finally:
        if advertiser:
            advertiser.stop()
        print("Server stopped.")

if __name__ == "__main__":
    main()
