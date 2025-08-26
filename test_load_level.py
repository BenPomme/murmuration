#!/usr/bin/env python3
"""Debug level loading issue."""

import asyncio
import json
import websockets

async def test_load():
    uri = "ws://localhost:8765"
    
    async with websockets.connect(uri) as websocket:
        print(f"✅ Connected to {uri}")
        
        # Send load level command
        message = json.dumps({
            "type": "load_level",
            "level": "W1-1"
        })
        await websocket.send(message)
        print("📤 Sent load_level command")
        
        # Wait for multiple responses
        for i in range(5):
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                data = json.loads(response)
                print(f"\n📥 Response {i+1}:")
                print(f"   Type: {data.get('type')}")
                if data.get('type') == 'state_update':
                    state = data.get('data', {})
                    print(f"   Tick: {state.get('tick')}")
                    print(f"   Level: {state.get('level')}")
                    print(f"   Population: {state.get('population')}")
                    print(f"   Agents: {len(state.get('agents', []))}")
            except asyncio.TimeoutError:
                print(f"   (no response within 2 seconds)")
            except Exception as e:
                print(f"   Error: {e}")
                break

if __name__ == "__main__":
    asyncio.run(test_load())