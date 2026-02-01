import asyncio
import websockets
import json
import os
from datetime import datetime, timezone, timedelta

API_KEY = os.environ.get("AISSTREAM_API_KEY")
LISTEN_DURATION = 240 # 4 Minutes

# Helpers
def get_flag(mmsi):
    try:
        mid = int(str(mmsi)[:3])
        if 201 <= mid <= 279: return "Europe"
        if 303 <= mid <= 374: return "N. America"
        if 401 <= mid <= 478: return "Asia"
        if 501 <= mid <= 578: return "Oceania"
        if 601 <= mid <= 679: return "Africa"
        if 701 <= mid <= 775: return "S. America"
        return "International"
    except: return "Unknown"

def get_ship_desc(code):
    code = int(code) if code else 0
    if 30 == code: return "Fishing"
    if 31 <= code <= 32: return "Tug/Towing"
    if 36 == code: return "Sailing"
    if 37 == code: return "Pleasure Craft"
    if 52 == code: return "Tug"
    if 60 <= code <= 69: return "Passenger"
    if 70 <= code <= 79: return "Cargo"
    if 80 <= code <= 89: return "Tanker"
    return "Other"

async def connect_ais_stream():
    # --- STEP 1: LOAD EXISTING DATA (PERSISTENCE) ---
    ships = {}
    file_path = 'public/ships.json'
    
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as f:
                old_data = json.load(f)
                # Convert list back to dictionary for fast updates
                for s in old_data.get('ships', []):
                    ships[s['mmsi']] = s
            print(f"Loaded {len(ships)} existing ships from database.")
        except:
            print("No existing database found or file corrupt. Starting fresh.")

    # --- STEP 2: CONNECT AND UPDATE ---
    async with websockets.connect("wss://stream.aisstream.io/v0/stream") as websocket:
        subscribe_message = {
            "APIKey": API_KEY,
            "BoundingBoxes": [[[-90, -180], [90, 180]]],
            "FilterMessageTypes": ["PositionReport", "ShipStaticData"]
        }
        await websocket.send(json.dumps(subscribe_message))

        print(f"Listening for {LISTEN_DURATION} seconds...")
        end_time = datetime.now().timestamp() + LISTEN_DURATION
        
        while datetime.now().timestamp() < end_time:
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                data = json.loads(response)
                if 'MetaData' not in data: continue
                
                mmsi = data['MetaData']['MMSI']
                current_time_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

                # If new ship, initialize skeleton
                if mmsi not in ships:
                    ships[mmsi] = {
                        "mmsi": mmsi, "name": "Unknown", "type": "Other",
                        "lat": None, "lon": None, "speed": 0, "heading": 0, "course": 0,
                        "dest": "N/A", "eta": "N/A", "draught": 0,
                        "len": 0, "width": 0, "imo": 0, "callsign": "N/A",
                        "flag": get_flag(mmsi),
                        "last_seen": current_time_iso 
                    }
                
                # Update "Last Seen"
                ships[mmsi]['last_seen'] = current_time_iso

                # --- MERGE NEW DATA ---
                # Check MetaData for Name
                if 'ShipName' in data['MetaData']:
                    raw_name = data['MetaData']['ShipName'].strip()
                    if raw_name and len(raw_name) > 1:
                        ships[mmsi]['name'] = raw_name

                if data['MessageType'] == 'PositionReport':
                    msg = data['Message']['PositionReport']
                    ships[mmsi]['lat'] = msg['Latitude']
                    ships[mmsi]['lon'] = msg['Longitude']
                    ships[mmsi]['speed'] = msg.get('Sog', 0)
                    ships[mmsi]['heading'] = msg.get('TrueHeading', 0)
                    ships[mmsi]['course'] = msg.get('Cog', 0)

                elif data['MessageType'] == 'ShipStaticData':
                    msg = data['Message']['ShipStaticData']
                    if 'Name' in msg:
                        n = msg['Name'].strip()
                        if n and len(n) > 1: ships[mmsi]['name'] = n
                    if 'Type' in msg: ships[mmsi]['type'] = get_ship_desc(msg['Type'])
                    if 'Destination' in msg: ships[mmsi]['dest'] = msg['Destination'].strip()
                    if 'ImoNumber' in msg: ships[mmsi]['imo'] = msg['ImoNumber']
                    if 'CallSign' in msg: ships[mmsi]['callsign'] = msg['CallSign'].strip()
                    if 'MaximumStaticDraught' in msg: ships[mmsi]['draught'] = msg['MaximumStaticDraught']
                    if 'Dimension' in msg:
                        dim = msg['Dimension']
                        ships[mmsi]['len'] = dim.get('A', 0) + dim.get('B', 0)
                        ships[mmsi]['width'] = dim.get('C', 0) + dim.get('D', 0)
                    if 'Eta' in msg:
                        eta = msg['Eta']
                        ships[mmsi]['eta'] = f"{eta.get('Month',0)}/{eta.get('Day',0)} {eta.get('Hour',0)}:{eta.get('Minute',0)}"

            except: continue

    # --- STEP 3: CLEANUP (Remove ships older than 24 hours) ---
    clean_ships = []
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
    
    for s in ships.values():
        # Only keep if valid lat/lon
        if s['lat'] is None: continue
        
        # Check time
        try:
            # Handle ISO format parsing
            last_seen = datetime.fromisoformat(s.get('last_seen', datetime.now(timezone.utc).isoformat()))
            # Make sure it's timezone aware for comparison
            if last_seen.tzinfo is None:
                last_seen = last_seen.replace(tzinfo=timezone.utc)
            
            if last_seen > cutoff_time:
                clean_ships.append(s)
        except:
            # If date parsing fails, keep it to be safe
            clean_ships.append(s)

    # Sort
    clean_ships.sort(key=lambda x: (x['name'] == "Unknown", x['name']))

    final_data = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "total_ships": len(clean_ships),
        "ships": clean_ships
    }
    
    print(f"Saving {len(clean_ships)} ships to database.")
    
    os.makedirs('public', exist_ok=True)
    with open('public/ships.json', 'w') as f:
        json.dump(final_data, f)

if __name__ == "__main__":
    asyncio.run(connect_ais_stream())
