import asyncio
import websockets
import json
import os
from datetime import datetime, timezone

API_KEY = os.environ.get("AISSTREAM_API_KEY")

# Configuration: How long to listen (in seconds)
# Increased to 2 minutes for better data quality
LISTEN_DURATION = 360 

def get_ship_description(code):
    code = int(code) if code else 0
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
        print(f"Listening for {LISTEN_DURATION} seconds...")
        end_time = datetime.now().timestamp() + LISTEN_DURATION
        
        while datetime.now().timestamp() < end_time:
            try:
                # Wait for message
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                data = json.loads(response)
                
                # Check if data is valid
                if 'MetaData' not in data: continue
                
                mmsi = data['MetaData']['MMSI']

                # Initialize if new
                if mmsi not in ships:
                    ships[mmsi] = {
                        "mmsi": mmsi,
                        "name": "Unknown",
                        "type_text": "Other",
                        "type_code": 0,
                        "lat": None, "lon": None,
                        "speed": 0, "heading": 0,
                        "dest": "N/A", "len": 0, "width": 0
                    }

                # --- FIX 1: ALWAYS CHECK METADATA FOR NAME ---
                # AISStream often sends the name here even in Position reports
                if 'ShipName' in data['MetaData']:
                    clean_name = data['MetaData']['ShipName'].strip()
                    if clean_name:
                        ships[mmsi]['name'] = clean_name

                # --- Process Specific Message Types ---
                if data['MessageType'] == 'PositionReport':
                    msg = data['Message']['PositionReport']
                    ships[mmsi]['lat'] = msg['Latitude']
                    ships[mmsi]['lon'] = msg['Longitude']
                    ships[mmsi]['speed'] = msg.get('Sog', 0)
                    ships[mmsi]['heading'] = msg.get('TrueHeading', 0)

                elif data['MessageType'] == 'ShipStaticData':
                    msg = data['Message']['ShipStaticData']
                    # Static data is the authority on Name/Type/Dest
                    if 'Name' in msg and msg['Name']: 
                        ships[mmsi]['name'] = msg['Name'].strip()
                    if 'Type' in msg: 
                        ships[mmsi]['type_code'] = msg['Type']
                        ships[mmsi]['type_text'] = get_ship_description(msg['Type'])
                    if 'Destination' in msg: 
                        ships[mmsi]['dest'] = msg['Destination'].strip()
                    if 'Dimension' in msg:
                        dim = msg['Dimension']
                        ships[mmsi]['len'] = dim.get('A', 0) + dim.get('B', 0)
                        ships[mmsi]['width'] = dim.get('C', 0) + dim.get('D', 0)

            except asyncio.TimeoutError:
                continue # Just keep looping if stream is quiet for a moment
            except Exception as e:
                continue

        # Filter: Only save ships where we actually received a GPS location
        clean_ships = [s for s in ships.values() if s['lat'] is not None]
        
        # Sort by Name so the list looks nice in the search bar
        clean_ships.sort(key=lambda x: x['name'])

        final_data = {
            "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "ship_count": len(clean_ships),
            "ships": clean_ships
        }
        
        print(f"Collected {len(clean_ships)} ships.")
        
        os.makedirs('public', exist_ok=True)
        with open('public/ships.json', 'w') as f:
            json.dump(final_data, f)

if __name__ == "__main__":
    asyncio.run(connect_ais_stream())
