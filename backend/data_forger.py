#!/usr/bin/env python3
"""
Aegis Command - High-Fidelity Tactical Intelligence Data Forger.

Generates 1,250+ realistic, distinctive, professional military intelligence
records across Punjab and Jammu & Kashmir border sectors.

Includes diverse intelligence disciplines:
- SIGINT/COMINT (Encrypted radio bursts, frequency-hop chatter, cellular anomalies)
- ELINT/RADAR (Low-RCS micro-Doppler tracks, counter-UAS frequency sweeps, radar blips)
- OPTICS/FLIR (Long-range thermal imager sightings, NVG illumination, heat signatures)
- ACOUSTIC/SEISMIC (Geophone tunnel detection, fence fiber disturbance, rotor thrum)
- HUMINT (Informant tips, courier staging, contraband handover advisories)
- EW/JAMMING (Directional C-UAS jamming logs, GPS spoofing, C2 link degradation)
- PATROL/QRT (Joint BSF QRT cordons, riverine patrol craft, barrier inspections)

Preserves required canonical test records:
- INTEL-9999: Pickup truck payload intercept (Tarn Taran Border)
- INTEL-1603: Hexacopter ingress intercept (Pathankot Perimeter)
- INTEL-1437: BSF tactical patrol intercept (Akhnoor Post)
"""

import json
import math
import random
from datetime import datetime, timedelta
from pathlib import Path

# Strategic forward border sectors with precise coordinates
BORDER_SECTORS = {
    "Tarn Taran Border": {
        "coords": [31.4520, 74.9250],
        "posts": [
            "Drop Zone Alpha", "BOP Pul Kanjri", "BOP Daoke",
            "Khalra Axis", "Upper Bari Doab Siphon", "Post Bravo-2"
        ]
    },
    "Samba Sector (J&K)": {
        "coords": [32.5530, 75.1110],
        "posts": [
            "BOP Manguchak", "Post Alpha-9", "Chilyari Salient",
            "Basantar Riverbed", "Tarnah Nullah Forward Line", "BOP Regal"
        ]
    },
    "Pathankot Perimeter": {
        "coords": [32.2640, 75.6450],
        "posts": [
            "Airbase Approach Flank", "Chakki River Ravine", "Mamun Cantt Forward Sector",
            "Dhangu Hill Relay", "BOP Bamial", "Simbal Forward Ridge"
        ]
    },
    "Akhnoor Post": {
        "coords": [32.8680, 74.7350],
        "posts": [
            "Chenab Riverine Bend", "Pargwal Salient", "Jourian Forward Line",
            "Munawar Tawi Confluence", "BOP Gigrial", "Post Delta-4"
        ]
    },
    "Amritsar Outpost": {
        "coords": [31.6340, 74.8720],
        "posts": [
            "Attari-Wagah Axis", "Ranian Border Ditch", "Kakkar Forward Bunker",
            "Ramdas Sector", "BOP Roranwala Khurd", "Doda Observation Tower"
        ]
    },
    "Gurdaspur Sector": {
        "coords": [32.0330, 75.4010],
        "posts": [
            "Dera Baba Nanak Corridor", "Ravi River Island Post", "Kasowal Enclave",
            "Dorangla Forward Line", "BOP Shikhar", "Bhurj Forward Trench"
        ]
    },
    "Poonch LoC Salient": {
        "coords": [33.7710, 74.0980],
        "posts": [
            "Krishna Ghati Ridge", "Degwar Observation Post", "Betar Nullah Gap",
            "Chakan Da Bagh Forward Gate", "BOP Khari Karmara", "Gulpur Forward Bunkers"
        ]
    },
    "Rajouri Forward Sector": {
        "coords": [33.3800, 74.3100],
        "posts": [
            "Keri Sector Fence", "Bhimber Gali Watchtower", "Tarkundi Forward Post",
            "Manjakote Observation Point", "Nowshera Forward Line", "Sunderbani Ridge"
        ]
    }
}

TACTICAL_SCENARIOS = [
    # --- Category 1: UAV / Drone Incursions & Counter-UAS ---
    {
        "type": "UAV/C-UAS",
        "templates": [
            "[FLASH/ELINT] Micro-Doppler 3D radar blip registered at {post}. Unidentified rotary hexacopter operating at {alt}m AGL, heading {heading}. RCS ~0.02 m². Directional RF jamming deployed on 2.4/5.8 GHz bands.",
            "[PRIORITY/SIGINT] Intercepted C2 telemetry link on {freq} MHz near {post}. Drone telemetry packet indicates automated waypoint return toward grid {grid}. Payload release mechanism armed.",
            "[OPTICS/FLIR] Long-range cooled thermal imaging at {post} tracks a low-altitude quadcopter silhouette hovering near boundary pillar {pillar}. IR strobe flash observed.",
            "[ACOUSTIC/ALERT] Passive border acoustic sensor cluster at {post} detected dual-rotor acoustic resonance at {freq_khz} Hz. Estimated contact altitude 80m AGL crossing international ditch.",
            "[SURVEILLANCE/UAV] Heavy-lift multirotor detected carrying tethered cylindrical payload over {post}. Directional anti-drone rifle engaged; contact lost telemetry and initiated forced descent.",
            "[EW/LOG] Directional counter-UAS jammer at {post} successfully severed control link of unauthorized UAV. Target entered failsafe hover at coordinate {grid}."
        ]
    },
    # --- Category 2: Vehicle & Logistics Movements ---
    {
        "type": "VEHICLE/LOGISTICS",
        "templates": [
            "[INTERCEPT/SIGINT] Intercepted VHF burst ({freq} MHz): Target callsign '{callsign}' confirming 4x4 pickup staging along canal road near {post}. Headlights extinguished, engine idling.",
            "[OPTICS/FLIR] Forward thermal camera at {post} logs an unlighted modified pickup truck maneuvering through sugarcane field track toward milestone {pillar}. Engine thermal delta ΔT +{temp}C.",
            "[HUMINT/CORROBORATED] Ground intelligence source reports an unmarked logistics transport vehicle idling near {post} approach road. Suspected cross-border arms/contraband recovery team.",
            "[RADAR/GROUND] Ground surveillance radar at {post} tracks vehicle moving {speed} km/h along perimeter lateral road, stopping intermittently at culvert {pillar}.",
            "[TACTICAL/OBSERVATION] QRT patrol at {post} observes civilian tractor modified with false cargo compartment operating outside curfew hours near border perimeter ditch.",
            "[SEISMIC/TRIGGER] Ground geophone line along {post} perimeter tracks heavy axle vibration signature consistent with utility vehicle staging within 150m of zero line."
        ]
    },
    # --- Category 3: Personnel & Infiltration Probes ---
    {
        "type": "PERSONNEL/INCURSION",
        "templates": [
            "[PRIORITY/OPTICS] Cooled FLIR imager at {post} identifies {count} individuals crawling in low silhouette through tall elephant grass toward perimeter fence. Heat signature ΔT +{temp}C above background.",
            "[SEISMIC/FIBER] Smart-fence optical fiber vibration alert triggered at {post}, Section {sec}. Dynamic signature indicates manual climbing or wire tension manipulation.",
            "[SIGINT/BURST] Encrypted shortwave transmission ({freq} MHz) intercepted near {post}: '{callsign} requesting clearance at forward marker {pillar}. Fog cover optimal.'",
            "[PATROL/INTERCEPT] BSF {bn} Bn Quick Reaction Team at {post} challenges unidentified individual moving through riverine reeds. Subject retreated across zero line under cover of darkness.",
            "[OPTICS/NIGHT] Thermal pan-tilt-zoom camera at {post} captures 2 suspects with rucksacks probing culvert drainage grate near boundary pillar {pillar}.",
            "[HUMINT/SOURCE] High-reliability local source alerts command to 3-man reconnaissance team probing anti-intrusion obstacle belt in {post} vicinity."
        ]
    },
    # --- Category 4: Signal & Communications Intelligence ---
    {
        "type": "SIGINT/COMINT",
        "templates": [
            "[SIGINT/COMINT] Tactical radio direction-finder (DF) at {post} intercepted burst comms on {freq} MHz. Line of bearing: {heading}. Caller references code '{code}'.",
            "[ELINT/ALERT] Directional signal analyzer at {post} detects anomalous frequency-hopping spread spectrum (FHSS) transmission in the 433 MHz band lasting 4.2 seconds.",
            "[CELLULAR/ANOMALY] Cellular IMSI monitoring array at {post} identified burner subscriber identity connecting to forward foreign tower while physically located near domestic boundary.",
            "[SIGINT/TRANSCRIPTION] Intercepted push-to-talk channel near {post}: 'Drop complete at northern culvert marker. Package secured in waterproof container. Evacuate immediately.'",
            "[EW/SPECTRUM] Wideband spectrum surveillance at {post} recorded active L-band GPS jamming emissions originating from opposing tactical observation tower.",
            "[COMMS/DECRYPT] Low-power handheld radio intercept at {post}: Callers using colloquial dialect coordinating flash signaling toward friendly bank at 0245h."
        ]
    },
    # --- Category 5: Barrier, Subsurface & Physical Security ---
    {
        "type": "BARRIER/SEISMIC",
        "templates": [
            "[SEISMIC/SUBTERRANEAN] Underground geophone array at {post} logs rhythmic acoustic pulses at 18 Hz, depth ~4m. Possible cross-border subterranean tunnel excavation anomaly.",
            "[BARRIER/ALARM] Anti-cutting sensor alarm activated on perimeter fence sector {sec} at {post}. Physical inspection initiated by forward guard post.",
            "[THERMAL/BOUNDARY] Long-range thermal observation at {post} confirms unauthorized breach attempt through flood-damaged riverine concertina wire.",
            "[SENSOR/DIAGNOSTIC] Optical fiber intrusion detection system at {post} reports transient disturbance at grid {grid}. Wind/debris discounted by AI signal classifier.",
            "[INFRASTRUCTURE/ALERT] High-intensity perimeter floodlight circuit tripped at {post}, Tower {pillar}. Auxiliary power engaged; thermal cameras prioritized."
        ]
    },
    # --- Category 6: Routine Tactical Operations & Countermeasures ---
    {
        "type": "ROUTINE/PATROL",
        "templates": [
            "[ROUTINE/PATROL] BSF {bn} Bn completed scheduled tactical patrol sweep along {post} perimeter track. Optical-thermal barrier intact, zero fence disturbances noted.",
            "[RIVERINE/PATROL] Water Wing fast patrol boat completed reconnaissance sweep of riverine boundary near {post}. River currents normal, sandbars clear of staging.",
            "[TACTICAL/CHECK] Forward bunker relief completed at {post}. Night-vision thermal scopes calibrated against reference target. Perimeter illumination 100% operational.",
            "[C-UAS/READINESS] Joint counter-UAS directional jammer and acoustic radar calibration test executed at {post}. System status fully mission capable (FMC).",
            "[WEATHER/TACTICAL] Operational meteorological log at {post}: Dense ground fog reducing visual range to <30m. Thermal FLIR and millimeter-wave radar prioritized.",
            "[DEFENSE/READINESS] Coordinated searchlight sweep and drone mitigation drill conducted at {post} with Army liaison team. Response time: 48 seconds."
        ]
    }
]

CALLSIGNS = ["SULTAN-6", "EAGLE-EYE", "VIPER-3", "BAJRA-4", "COBRA-9", "FALCON-1", "SHAHBAZ", "CHETAK-2"]
TACTICAL_CODES = ["OMEGA-7", "RED-FOX", "CRESCENT", "WATERFALL", "DARK-SKY", "BLUE-HERON", "ZERO-LINE"]


def forge_database(count: int = 1250) -> list:
    """Generate high-fidelity tactical intelligence reports."""
    random.seed(42)  # Deterministic generation
    base_time = datetime(2026, 8, 15, 18, 0, 0)
    database = []

    # 1. Canonical Golden Threat Records (Strictly preserved for tests and scenarios)
    database.append({
        "id": "INTEL-9999",
        "timestamp": "2026-08-15T23:45:00Z",
        "location": "Tarn Taran Border",
        "lat": 31.4520,
        "lng": 74.9250,
        "transcript": "URGENT INTERCEPT: Unidentified pickup truck confirmed waiting at drop zone Alpha. Awaiting hexacopter payload of narcotics/arms from across the IB."
    })

    database.append({
        "id": "INTEL-1603",
        "timestamp": "2026-08-15T21:14:00Z",
        "location": "Pathankot Perimeter",
        "lat": 32.2609,
        "lng": 75.6469,
        "transcript": "Unscheduled hexacopter ingress detected at 400ft AGL crossing forward line. RF signal jamming protocol initiated."
    })

    database.append({
        "id": "INTEL-1437",
        "timestamp": "2026-08-15T22:30:00Z",
        "location": "Akhnoor Post",
        "lat": 32.8645,
        "lng": 74.7333,
        "transcript": "Routine BSF tactical patrol completed. Night vision thermal imaging active along forward perimeter fence."
    })

    # 2. Procedural Authentic Tactical Reports
    num_to_generate = count - len(database)

    for i in range(num_to_generate):
        intel_id = f"INTEL-{1000 + i}"
        # Skip if ID clashes with reserved
        if intel_id in ("INTEL-1603", "INTEL-1437", "INTEL-9999"):
            intel_id = f"INTEL-{2000 + i}"

        # Temporal progression: 3-5 minute intervals over multi-day operations
        delta_minutes = i * 2.8 + random.uniform(0, 1.5)
        timestamp = (base_time + timedelta(minutes=delta_minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Location selection
        loc_name = random.choice(list(BORDER_SECTORS.keys()))
        sector_info = BORDER_SECTORS[loc_name]
        base_lat, base_lng = sector_info["coords"]
        post_name = random.choice(sector_info["posts"])

        # Small micro-variance around outpost coordinates (~200m - 800m realistic spread)
        lat = round(base_lat + random.uniform(-0.007, 0.007), 4)
        lng = round(base_lng + random.uniform(-0.007, 0.007), 4)

        # Scenario selection
        scenario = random.choice(TACTICAL_SCENARIOS)
        template = random.choice(scenario["templates"])

        # Tactical parameters
        alt = random.choice([60, 80, 110, 140, 180, 220, 350, 420])
        freq = round(random.choice([142.85, 148.20, 433.92, 446.10, 868.30, 915.00, 2412.0]), 2)
        freq_khz = random.randint(140, 260)
        heading = random.choice(["NE (045°)", "E (090°)", "SE (135°)", "SW (225°)", "NW (315°)", "N (000°)"])
        pillar = f"BP-{random.randint(102, 198)}/{random.randint(1, 9)}"
        sec = f"S-{random.randint(1, 16)}"
        bn = random.choice([72, 88, 114, 137, 168, 182])
        grid = f"GR-{random.randint(10, 99)}x{random.randint(10, 99)}"
        temp = round(random.uniform(2.8, 6.4), 1)
        speed = random.randint(35, 75)
        count_people = random.choice([1, 2, 3, 4])
        callsign = random.choice(CALLSIGNS)
        code = random.choice(TACTICAL_CODES)

        transcript = template.format(
            post=post_name,
            alt=alt,
            freq=freq,
            freq_khz=freq_khz,
            heading=heading,
            pillar=pillar,
            sec=sec,
            bn=bn,
            grid=grid,
            temp=temp,
            speed=speed,
            count=count_people,
            callsign=callsign,
            code=code
        )

        database.append({
            "id": intel_id,
            "timestamp": timestamp,
            "location": loc_name,
            "lat": lat,
            "lng": lng,
            "transcript": transcript
        })

    # Shuffle for realistic non-linear intelligence feed, but preserve index lookup
    random.shuffle(database)
    return database


def main():
    root = Path(__file__).resolve().parent.parent
    backend_dir = root / "backend"
    frontend_public_data = root / "frontend" / "public" / "data"
    frontend_src_data = root / "frontend" / "src" / "data"

    data = forge_database(1250)

    # 1. Save to backend/mock_intel.json
    backend_file = backend_dir / "mock_intel.json"
    with backend_file.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"[SUCCESS] Forged {len(data)} authentic tactical intelligence records -> {backend_file}")

    # 2. Save copy for frontend direct lookup
    frontend_public_data.mkdir(parents=True, exist_ok=True)
    with (frontend_public_data / "mock_intel.json").open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"[SUCCESS] Mirrored records to {frontend_public_data / 'mock_intel.json'}")

    frontend_src_data.mkdir(parents=True, exist_ok=True)
    with (frontend_src_data / "mock_intel.json").open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"[SUCCESS] Mirrored records to {frontend_src_data / 'mock_intel.json'}")


if __name__ == "__main__":
    main()
