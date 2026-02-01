import asyncio
import websockets
import json
import os
from datetime import datetime

# You will store your API key in GitHub Secrets later
API_KEY = os.environ.get("AISSTREAM_API_KEY")

async def connect_ais_stream():
    async with websockets.connect("wss://stream.aisstream.io/v0/stream") as websocket:
        subscribe_message = {
            "APIKey": API_KEY,
            "BoundingBoxes": [[[-90, -180], [90, 180]]], # Whole world
            "FilterMessageTypes": ["PositionReport"]
        }
        await websocket.send(json.dumps(subscribe_message))

        ships = {}
        # Listen for 10 seconds to grab a snapshot of currently moving ships
        end_time = datetime.now().timestamp() + 10 
        
        while datetime.now().timestamp() < end_time:
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=2)
                data = json.loads(message)
                mmsi = data['MetaData']['MMSI']
                # Store mostly recent position for each ship
                ships[mmsi] = data
            except:
                break
        
        # Save to file
        with open('public/ships.json', 'w') as f:
            json.dump(list(ships.values()), f)

if __name__ == "__main__":
    asyncio.run(connect_ais_stream())
