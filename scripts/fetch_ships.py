import asyncio
import websockets
import json
import os
from datetime import datetime, timezone

API_KEY = os.environ.get("AISSTREAM_API_KEY")

def get_ship_description(code):
    code = int(code) if code else 0
    # Specific granular mapping
    if 30 == code: return "Fishing"
    if 31 <= code <= 32: return "Tug/Towing"
    if 33 == code: return "Dredger"
    if 34 == code: return "Dive Vessel"
    if 35 == code: return "Military Ops"
    if 36 == code: return "Sailing"
    if 37 == code: return "Pleasure Craft"
    if 52 == code: return "Tug"
    if 60 <= code <= 69: return "Passenger"
    if 70 <= code <= 79: return "Cargo"
    if 80 <= code <= 89: return "Tanker"
    if 90 <= code <= 99: return "Other"
    return "Unknown/Other"

async def connect_ais_stream():
    async with websockets.connect("wss://stream.aisstream.io/v0/stream") as websocket:
        subscribe_message = {
            "APIKey": API_KEY,
            "BoundingBoxes": [[[-90, -180], [90, 180]]],
            "FilterMessageTypes": ["PositionReport", "ShipStaticData"]
        }
        await websocket.send(json.dumps(subscribe_message))

        ships = {}
        end_time = datetime.now().timestamp() + 25
        
        while datetime.now().timestamp() < end_time:
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=2)
                data = json.loads(response)
                mmsi = data['MetaData']['MMSI']

                if mmsi not in ships:
                    ships[mmsi] = {
                        "mmsi": mmsi,
                        "name": "Unknown",
                        "type_text": "Other",
                        "type_code": 0,    # <--- NEW: Raw Code
                        "lat": None, "lon": None,
                        "speed": 0, "heading": 0,
                        "dest": "N/A", "len": 0, "width": 0
                    }

                if data['MessageType'] == 'PositionReport':
                    msg = data['Message']['PositionReport']
                    ships[mmsi]['lat'] = msg['Latitude']
                    ships[mmsi]['lon'] = msg['Longitude']
                    ships[mmsi]['speed'] = msg.get('Sog', 0)
                    ships[mmsi]['heading'] = msg.get('TrueHeading', 0)

                elif data['MessageType'] == 'ShipStaticData':
                    msg = data['Message']['ShipStaticData']
                    if 'Name' in msg: ships[mmsi]['name'] = msg['Name'].strip()
                    if 'Type' in msg: 
                        ships[mmsi]['type_code'] = msg['Type'] # Save the raw number
                        ships[mmsi]['type_text'] = get_ship_description(msg['Type'])
                    if 'Destination' in msg: ships[mmsi]['dest'] = msg['Destination'].strip()
                    if 'Dimension' in msg:
                        dim = msg['Dimension']
                        ships[mmsi]['len'] = dim.get('A', 0) + dim.get('B', 0)
                        ships[mmsi]['width'] = dim.get('C', 0) + dim.get('D', 0)

            except:
                continue
        
        clean_ships = [s for s in ships.values() if s['lat'] is not None]
        
        # Create the final data object with timestamp
        final_data = {
            "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "ships": clean_ships
        }
        
        os.makedirs('public', exist_ok=True)
        with open('public/ships.json', 'w') as f:
            json.dump(final_data, f)

if __name__ == "__main__":
    asyncio.run(connect_ais_stream())
