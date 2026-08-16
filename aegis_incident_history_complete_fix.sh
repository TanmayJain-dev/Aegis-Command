#!/usr/bin/env bash

set -euo pipefail

echo "=============================================================="
echo " AEGIS — COMPLETE INCIDENT HISTORY / INTEL HISTORY FIX"
echo "=============================================================="

PAGE="frontend/src/app/page.tsx"
MAIN="backend/main.py"
MEMORY="backend/incident_memory.py"

for f in "$PAGE" "$MAIN" "$MEMORY"; do
    if [ ! -f "$f" ]; then
        echo "ERROR: Missing $f"
        exit 1
    fi
done

STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP=".aegis-history-complete-backup-${STAMP}"

echo
echo "[1/8] Creating backup..."
mkdir -p "$BACKUP/frontend/src/app" "$BACKUP/backend"

cp "$PAGE" "$BACKUP/frontend/src/app/page.tsx"
cp "$MAIN" "$BACKUP/backend/main.py"
cp "$MEMORY" "$BACKUP/backend/incident_memory.py"

echo "Backup: $BACKUP"

echo
echo "[2/8] Rebuilding incident-memory persistence..."

python3 <<'PY'
from pathlib import Path

p = Path("backend/incident_memory.py")
s = p.read_text()

# ------------------------------------------------------------
# Add richer persistent columns to the existing table.
# SQLite migrations are intentionally lightweight.
# ------------------------------------------------------------

old_create = '''            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS incidents(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    object_class TEXT,
                    latitude REAL,
                    longitude REAL,
                    threat_level TEXT,
                    score INTEGER,
                    timestamp TEXT
                )
            """)'''

new_create = '''            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS incidents(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    object_class TEXT,
                    latitude REAL,
                    longitude REAL,
                    threat_level TEXT,
                    score INTEGER,
                    timestamp TEXT,
                    telemetry_json TEXT,
                    assessment_json TEXT,
                    evidence_json TEXT
                )
            """)'''

if old_create in s:
    s = s.replace(old_create, new_create, 1)
elif "telemetry_json TEXT" not in s:
    raise SystemExit(
        "ERROR: Could not locate incident table definition."
    )

# ------------------------------------------------------------
# Import json.
# ------------------------------------------------------------

if "import json" not in s.splitlines()[:10]:
    s = s.replace(
        "import sqlite3\n",
        "import sqlite3\nimport json\n",
        1
    )

# ------------------------------------------------------------
# Add migration after CREATE TABLE.
# ------------------------------------------------------------

marker = '''            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_incidents_class_time'''

if marker not in s:
    raise SystemExit(
        "ERROR: Could not locate incident index creation."
    )

migration = '''            # Lightweight SQLite migration for databases created
            # before rich incident history was introduced.
            existing_columns = {
                row[1]
                for row in self.conn.execute(
                    "PRAGMA table_info(incidents)"
                ).fetchall()
            }

            for column, column_type in (
                ("telemetry_json", "TEXT"),
                ("assessment_json", "TEXT"),
                ("evidence_json", "TEXT"),
            ):
                if column not in existing_columns:
                    self.conn.execute(
                        f"ALTER TABLE incidents ADD COLUMN {column} {column_type}"
                    )

'''

if "Lightweight SQLite migration" not in s:
    s = s.replace(marker, migration + marker, 1)

# ------------------------------------------------------------
# Replace store_incident.
# ------------------------------------------------------------

start = s.find("    def store_incident(")
end = s.find("\n    def find_previous_incidents", start)

if start == -1 or end == -1:
    raise SystemExit(
        "ERROR: Could not locate store_incident()."
    )

new_store = '''    def store_incident(self, event, assessment, evidence=None):
        """Persist a complete AI-assessed threat event.

        Repeated frames are deduplicated, while the first occurrence
        retains the telemetry, AI assessment, and retrieved evidence
        required for historical review.
        """
        with self.lock:
            if self._is_duplicate_locked(event):
                return False

            self.conn.execute("""
                INSERT INTO incidents
                (
                    object_class,
                    latitude,
                    longitude,
                    threat_level,
                    score,
                    timestamp,
                    telemetry_json,
                    assessment_json,
                    evidence_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.get("class"),
                event.get("latitude"),
                event.get("longitude"),
                assessment.get("threat_level"),
                assessment.get("score"),
                datetime.now(timezone.utc).isoformat(),
                json.dumps(event, ensure_ascii=False),
                json.dumps(assessment, ensure_ascii=False),
                json.dumps(evidence or [], ensure_ascii=False),
            ))

            self.conn.commit()
            return True

'''

s = s[:start] + new_store + s[end:]

# ------------------------------------------------------------
# Add history retrieval method.
# ------------------------------------------------------------

if "def get_history(" not in s:
    marker = "\n    def find_previous_incidents"

    method = '''
    def get_history(self, limit=200, threat_level=None):
        """Return complete historical threat assessments."""
        with self.lock:
            limit = max(1, min(int(limit), 500))

            if threat_level:
                rows = self.conn.execute(
                    """
                    SELECT *
                    FROM incidents
                    WHERE threat_level = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (threat_level, limit),
                ).fetchall()
            else:
                rows = self.conn.execute(
                    """
                    SELECT *
                    FROM incidents
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()

            columns = [
                description[0]
                for description in self.conn.execute(
                    "SELECT * FROM incidents LIMIT 0"
                ).description
            ]

            records = []

            for row in rows:
                record = dict(zip(columns, row))

                for source_key, output_key in (
                    ("telemetry_json", "telemetry"),
                    ("assessment_json", "assessment"),
                    ("evidence_json", "evidence"),
                ):
                    raw = record.pop(source_key, None)

                    if raw:
                        try:
                            record[output_key] = json.loads(raw)
                        except Exception:
                            record[output_key] = raw
                    else:
                        record[output_key] = (
                            [] if output_key == "evidence" else {}
                        )

                # Flatten commonly displayed assessment fields.
                assessment = record.get("assessment") or {}

                record["reasoning"] = assessment.get("reasoning")
                record["recommended_action"] = assessment.get(
                    "recommended_action"
                )
                record["previous_incidents"] = assessment.get(
                    "previous_incidents"
                )

                records.append(record)

            return records

'''

    s = s.replace(marker, method + marker, 1)

p.write_text(s)

print("Incident memory upgraded.")
PY

echo "Incident persistence upgraded."

echo
echo "[3/8] Updating autonomous engine to persist evidence..."

python3 <<'PY'
from pathlib import Path

p = Path("backend/main.py")
s = p.read_text()

old = '''                stored = incident_memory.store_incident(
                    payload,
                    assessment_json
                )'''

new = '''                stored = incident_memory.store_incident(
                    payload,
                    assessment_json,
                    retrieved_reports
                )'''

if old in s:
    s = s.replace(old, new, 1)
elif "retrieved_reports" not in s[s.find("incident_memory.store_incident"):s.find("incident_memory.store_incident")+500]:
    raise SystemExit(
        "ERROR: Could not locate incident_memory.store_incident() call."
    )

p.write_text(s)

print("Threat engine persistence updated.")
PY

echo
echo "[4/8] Replacing incident-history API..."

python3 <<'PY'
from pathlib import Path

p = Path("backend/main.py")
s = p.read_text()

start = s.find('@app.get("/api/incidents/history")')
end = s.find('\n@app.get("/api/intel/history")', start)

if start == -1:
    raise SystemExit(
        "ERROR: Incident history endpoint not found."
    )

if end == -1:
    raise SystemExit(
        "ERROR: Intel history endpoint boundary not found."
    )

endpoint = '''@app.get("/api/incidents/history")
async def get_incident_history(
    limit: int = 200,
    threat_level: str | None = None,
):
    """Return complete historical Aegis threat events."""
    try:
        records = incident_memory.get_history(
            limit=limit,
            threat_level=threat_level,
        )

        return {
            "status": "success",
            "count": len(records),
            "records": records,
        }

    except Exception as e:
        print(f"[HISTORY ERROR] {e}")

        return {
            "status": "error",
            "count": 0,
            "records": [],
            "error": str(e),
        }


'''

s = s[:start] + endpoint + s[end:]

p.write_text(s)

print("Incident history API replaced.")
PY

echo
echo "[5/8] Fixing dashboard placement..."

python3 <<'PY'
from pathlib import Path

p = Path("frontend/src/app/page.tsx")
s = p.read_text()

# ------------------------------------------------------------
# Remove the incorrectly inserted Incident History button
# from Tactical Summary / intel modal.
# ------------------------------------------------------------

bad_button = '''          <button
            onClick={loadIncidentHistory}
            className="px-3 py-2 text-xs font-mono border border-cyan-500/40 text-cyan-300 bg-black/60 hover:bg-cyan-950/40 transition"
          >
            INCIDENT HISTORY
          </button>
'''

if bad_button in s:
    s = s.replace(bad_button, "", 1)
    print("Removed misplaced history button.")
else:
    print("Misplaced history button not found; continuing.")

# ------------------------------------------------------------
# Add the button to the main dashboard header.
# The header is uniquely identifiable by AEGIS COMMAND.
# ------------------------------------------------------------

button = '''          <button
            onClick={loadIncidentHistory}
            className="px-3 py-2 text-[10px] font-bold tracking-widest border border-cyan-500/40 text-cyan-300 bg-cyan-950/20 hover:bg-cyan-950/50 hover:border-cyan-400 transition-all"
          >
            INCIDENT HISTORY
          </button>
'''

header_marker = '''          <div className="flex items-center gap-6 text-xs border border-slate-800 bg-slate-900/50 px-4 py-2 rounded">'''

if "onClick={loadIncidentHistory}" not in s:
    if header_marker not in s:
        raise SystemExit(
            "ERROR: Dashboard header insertion point not found."
        )

    s = s.replace(
        header_marker,
        button + header_marker,
        1
    )

    print("Incident History moved to dashboard.")
else:
    print("Dashboard history button already present.")

p.write_text(s)
PY

echo
echo "[6/8] Improving history presentation..."

python3 <<'PY'
from pathlib import Path

p = Path("frontend/src/app/page.tsx")
s = p.read_text()

# ------------------------------------------------------------
# Add explicit location / telemetry information to the
# history detail view.
# ------------------------------------------------------------

needle = '''                  <div className="border border-slate-800 bg-black p-4">
                    <div className="text-xs text-cyan-300 font-mono mb-3">
                      EVENT TELEMETRY
                    </div>'''

replacement = '''                  <div className="border border-slate-800 bg-black p-4">
                    <div className="text-xs text-cyan-300 font-mono mb-3">
                      EVENT TELEMETRY
                    </div>

                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">

                      <div className="border border-slate-800 p-3">
                        <div className="text-[9px] text-slate-500 font-mono">
                          LATITUDE
                        </div>
                        <div className="text-xs text-white font-mono mt-1">
                          {selectedHistory.latitude ??
                            selectedHistory.telemetry?.latitude ??
                            "—"}
                        </div>
                      </div>

                      <div className="border border-slate-800 p-3">
                        <div className="text-[9px] text-slate-500 font-mono">
                          LONGITUDE
                        </div>
                        <div className="text-xs text-white font-mono mt-1">
                          {selectedHistory.longitude ??
                            selectedHistory.telemetry?.longitude ??
                            "—"}
                        </div>
                      </div>

                      <div className="border border-slate-800 p-3">
                        <div className="text-[9px] text-slate-500 font-mono">
                          SPEED
                        </div>
                        <div className="text-xs text-white font-mono mt-1">
                          {selectedHistory.telemetry?.speed_kmh ?? "—"} km/h
                        </div>
                      </div>

                      <div className="border border-slate-800 p-3">
                        <div className="text-[9px] text-slate-500 font-mono">
                          DIRECTION
                        </div>
                        <div className="text-xs text-white font-mono mt-1">
                          {selectedHistory.telemetry?.direction ?? "—"}
                        </div>
                      </div>

                    </div>'''

if needle in s and "LATITUDE" not in s[s.find(needle):s.find(needle)+3000]:
    s = s.replace(needle, replacement, 1)
    print("Telemetry summary added.")
else:
    print("Telemetry summary already present or insertion point missing.")

p.write_text(s)
PY

echo
echo "[7/8] Validating source..."

python3 -m py_compile \
    backend/main.py \
    backend/incident_memory.py

echo "Python syntax: OK"

docker compose run --rm frontend npx tsc --noEmit

echo "TypeScript: OK"

echo
echo "[8/8] Verifying final placement..."

echo
echo "History button occurrences:"
grep -n "INCIDENT HISTORY" "$PAGE" || true

echo
echo "History endpoint:"
grep -n '/api/incidents/history' "$MAIN" || true

echo
echo "Incident storage:"
grep -n "store_incident" "$MAIN" "$MEMORY" || true

echo
echo "=============================================================="
echo " SUCCESS"
echo "=============================================================="
echo
echo "Incident History is now a DASHBOARD function."
echo
echo "It will show:"
echo "  - historical incidents"
echo "  - timestamp"
echo "  - object class"
echo "  - GPS coordinates"
echo "  - speed"
echo "  - direction"
echo "  - confidence / telemetry"
echo "  - threat level"
echo "  - threat score"
echo "  - AI reasoning"
echo "  - recommended action"
echo "  - previous incident count"
echo "  - retrieved intelligence evidence"
echo
echo "Backup:"
echo "  $BACKUP"
echo
echo "Next:"
echo "  docker compose down"
echo "  docker compose up --build"
echo
