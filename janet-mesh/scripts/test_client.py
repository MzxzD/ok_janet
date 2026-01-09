#!/usr/bin/env python3
"""
Simple test client for Janet Mesh Server
"""
import asyncio
import websockets
import json
import sys


async def test_client(uri: str):
    """Test client that sends text messages"""
    try:
        async with websockets.connect(uri) as websocket:
            print(f"Connected to {uri}")
            
            # Receive welcome message
            welcome = await websocket.recv()
            print(f"Server: {welcome}")
            
            # Send test messages
            test_messages = [
                "Hello, Janet!",
                "What is the weather like?",
                "Tell me a joke",
            ]
            
            for msg in test_messages:
                message = {
                    "type": "text_input",
                    "text": msg
                }
                print(f"\nSending: {msg}")
                await websocket.send(json.dumps(message))
                
                # Wait for response
                response = await websocket.recv()
                data = json.loads(response)
                print(f"Response: {data.get('text', 'No text in response')}")
                
                await asyncio.sleep(1)
            
            # Test ping
            ping_msg = {
                "type": "ping",
                "timestamp": "test"
            }
            await websocket.send(json.dumps(ping_msg))
            pong = await websocket.recv()
            print(f"\nPing/Pong: {pong}")
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    uri = sys.argv[1] if len(sys.argv) > 1 else "ws://localhost:8765"
    asyncio.run(test_client(uri))
