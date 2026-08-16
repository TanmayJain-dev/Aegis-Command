import json
import random
from datetime import datetime, timedelta

# Real-world sensitive border regions (Punjab / J&K)
COORDINATE_MAP = {
    "Samba Sector (J&K)": [32.5530, 75.1110],
    "Tarn Taran Border": [31.4520, 74.9250],
    "Amritsar Outpost": [31.6340, 74.8720],
    "Pathankot Perimeter": [32.2640, 75.6450],
    "Akhnoor Post": [32.8680, 74.7350],
    "Gurdaspur Sector": [32.0330, 75.4010]
}

actions = ["Routine BSF patrol completed.", "Civilian tractor movement logged.", "No drone activity detected.", "Comms check secure.", "Fog reducing optical visibility."]

database = []
base_time = datetime(2026, 8, 15, 20, 0, 0) # Night ops

for i in range(1250):
    timestamp = (base_time + timedelta(minutes=i*3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    loc = random.choice(list(COORDINATE_MAP.keys()))
    coords = COORDINATE_MAP[loc]
    
    database.append({
        "id": f"INTEL-{1000+i}",
        "timestamp": timestamp,
        "location": loc,
        "lat": coords[0] + (random.uniform(-0.005, 0.005)), 
        "lng": coords[1] + (random.uniform(-0.005, 0.005)),
        "transcript": f"{random.choice(actions)} All clear at {loc}."
    })

# THE "GOLDEN" THREAT (With Exact Coordinates to Trigger the Map)
database.append({
    "id": "INTEL-9999",
    "timestamp": "2026-08-15T23:45:00Z",
    "location": "Tarn Taran Border",
    "lat": 31.4520, "lng": 74.9250,
    "transcript": "URGENT INTERCEPT: Unidentified pickup truck confirmed waiting at drop zone Alpha. Awaiting hexacopter payload of narcotics/arms from across the IB."
})

random.shuffle(database)

with open("mock_intel.json", "w") as f:
    json.dump(database, f, indent=2)

print("[SUCCESS] Indian Border Security Database forged with real coordinates.")
