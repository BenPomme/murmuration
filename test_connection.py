#!/usr/bin/env python3
"""Test WebSocket connection to simulation server."""

import asyncio
import json
import websockets

async def test_connection():
    uri = "ws://localhost:8765"
    
    try:
        async with websockets.connect(uri) as websocket:
            print(f"✅ Connected to {uri}")
            
            # Send load level command
            message = json.dumps({
                "type": "load_level",
                "level": "W1-1"
            })
            await websocket.send(message)
            print("📤 Sent load_level command")
            
            # Wait for response
            response = await websocket.recv()
            data = json.loads(response)
            print(f"📥 Received response: {data['type']}")
            
            if data.get("type") == "state_update":
                print(f"   - Level: {data['data'].get('level')}")
                print(f"   - Population: {data['data'].get('population')}")
                print(f"   - Tick: {data['data'].get('tick')}")
                
            # Test speed control
            speed_msg = json.dumps({
                "type": "set_speed",
                "speed": 2
            })
            await websocket.send(speed_msg)
            print("📤 Set speed to 2x")
            
            # Listen for a few updates
            for i in range(3):
                response = await websocket.recv()
                data = json.loads(response)
                if data.get("type") == "state_update":
                    print(f"📊 Update {i+1}: Tick={data['data']['tick']}, Population={data['data']['population']}")
                    
            print("✅ Test completed successfully!")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())