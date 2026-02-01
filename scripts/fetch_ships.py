import asyncio
import websockets
import json
import os
from datetime import datetime

API_KEY = os.environ.get("AISSTREAM_API_KEY")

# Helper to convert AIS ship type codes to human-readable text
def get_ship_type(code):
    code = int(code) if code else 0
    if 20 <= code <= 29: return "Wing in Ground"
    if 30 <= code <= 30: return "Fishing"
    if 31 <= code <= 32: return "Tug/Towing"
    if 36 <= code <= 36: return "Sailing"
    if 37 <= code <= 37: return "Pleasure Craft"
    if 40 <= code <= 49: return "High Speed Craft"
    if 52 <= code <= 52: return "Tug"
    if 60 <= code <= 69: return "Passenger"
    if 70 <= code <= 79: return "Cargo"
    if 80 <= code <= 89: return "Tanker"
    return "Other"

async def connect_ais_stream():
    async with websockets.connect("wss://stream.aisstream.io/v0/stream") as websocket:
        subscribe_message = {
            "APIKey": API_KEY,
            "BoundingBoxes": [[[-90, -180], [90, 180]]],
            # We filter for PositionReports (movement) and StaticData (names/types)
            "FilterMessageTypes": ["PositionReport", "ShipStaticData"]
        }
        await websocket.send(json.dumps(subscribe_message))

        ships = {}
        # Run for 20 seconds to catch more data
        end_time = datetime.now().timestamp() + 20
        
        while datetime.now().timestamp() < end_time:
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=2)
                data = json.loads(response)
                
                mmsi = data['MetaData']['MMSI']
                
                # Initialize ship entry if not exists
                if mmsi not in ships:
                    ships[mmsi] = {"mmsi": mmsi, "lat": None, "lon": None, "name": "Unknown", "type": "Other"}

                # Update Name/Type if available in MetaData (AISStream often provides this!)
                if 'ShipName' in data['MetaData']:
                    ships[mmsi]['name'] = data['MetaData']['ShipName'].strip()

                # Parse specific message types
                if data['MessageType'] == 'PositionReport':
                    ships[mmsi]['lat'] = data['Message']['PositionReport']['Latitude']
                    ships[mmsi]['lon'] = data['Message']['PositionReport']['Longitude']
                elif data['MessageType'] == 'ShipStaticData':
                    if 'Name' in data['Message']['ShipStaticData']:
                         ships[mmsi]['name'] = data['Message']['ShipStaticData']['Name'].strip()
                    if 'Type' in data['Message']['ShipStaticData']:
                         ships[mmsi]['type'] = get_ship_type(data['Message']['ShipStaticData']['Type'])
            except:
                continue
        
        # Filter out ships that never got a location (lat/lon)
        clean_ships = [s for s in ships.values() if s['lat'] is not None]
        
        with open('public/ships.json', 'w') as f:
            json.dump(clean_ships, f)

if __name__ == "__main__":
    asyncio.run(connect_ais_stream())
