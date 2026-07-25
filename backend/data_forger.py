import json
import random
from datetime import datetime, timedelta

locations = ["Sector 1", "Sector 4", "Sector 7", "Sector 9", "Alpha Base", "Northern Ridge", "Checkpoint Charlie", "Delta Outpost"]
actions = ["Routine patrol spotted.", "No hostile activity.", "Civilian movement detected.", "Radio check complete.", "Weather interference on comms."]

database = []
base_time = datetime(2026, 7, 23, 8, 0, 0)

print("Forging 1,250 intel reports...")

for i in range(1250):
    # Create mostly boring, routine data
    timestamp = (base_time + timedelta(minutes=i*3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    loc = random.choice(locations)
    transcript = random.choice(actions)
    
    database.append({
        "id": f"INTEL-{1000+i}",
        "timestamp": timestamp,
        "location": loc,
        "transcript": f"{transcript} All clear at {loc}."
    })

# Inject the 3 "Golden" Threats we actually want to find
database.append({
    "id": "INTEL-9999",
    "timestamp": "2026-07-23T11:45:00Z",
    "location": "Sector 7",
    "transcript": "URGENT: Hostile supplies and munitions detected moving covertly in a white pickup truck. Proceed with caution."
})
database.append({
    "id": "INTEL-8888",
    "timestamp": "2026-07-23T14:20:00Z",
    "location": "Sector 4",
    "transcript": "WARNING: Armed personnel spotted assembling near the perimeter fence. Possible breach attempt."
})

# Shuffle the database so the threats are buried in the noise
random.shuffle(database)

with open("mock_intel.json", "w") as f:
    json.dump(database, f, indent=2)

print("Database forged. Restart your FastAPI server to index the 1,250+ vectors in FAISS.")