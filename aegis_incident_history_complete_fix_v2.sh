#!/usr/bin/env bash

set -euo pipefail

echo "=============================================================="
echo " AEGIS — INCIDENT HISTORY COMPLETE FIX v2"
echo "=============================================================="

PAGE="frontend/src/app/page.tsx"
MAIN="backend/main.py"
MEMORY="backend/incident_memory.py"

for f in "$PAGE" "$MAIN" "$MEMORY"; do
    [ -f "$f" ] || {
        echo "ERROR: Missing $f"
        exit 1
    }
done

STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP=".aegis-history-v2-backup-${STAMP}"

echo
echo "[1/9] Creating backup..."
mkdir -p "$BACKUP/frontend/src/app" "$BACKUP/backend"

cp "$PAGE" "$BACKUP/frontend/src/app/page.tsx"
cp "$MAIN" "$BACKUP/backend/main.py"
cp "$MEMORY" "$BACKUP/backend/incident_memory.py"

echo "Backup: $BACKUP"

echo
echo "[2/9] Upgrading incident memory..."

python3 <<'PY'
from pathlib import Path

p = Path("backend/incident_memory.py")
s = p.read_text()

if "import json" not in s:
    s = s.replace(
        "import sqlite3\n",
        "import sqlite3\nimport json\n",
        1
    )

# ------------------------------------------------------------
# Upgrade CREATE TABLE.
# ------------------------------------------------------------

old_table = '''            self.conn.execute("""
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

new_table = '''            self.conn.execute("""
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

if old_table in s:
    s = s.replace(old_table, new_table, 1)

# ------------------------------------------------------------
# Add migration after CREATE TABLE if not already present.
# ------------------------------------------------------------

if "telemetry_json" not in s or "PRAGMA table_info(incidents)" not in s:

    anchor = '''            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_incidents_class_time'''

    if anchor not in s:
        raise SystemExit(
            "ERROR: Could not locate incident table initialization."
        )

    migration = '''            # Backward-compatible SQLite migration.
            existing_columns = {
                row[1]
                for row in self.conn.execute(
                    "PRAGMA table_info(incidents)"
                ).fetchall()
            }

            for column in (
                "telemetry_json",
                "assessment_json",
                "evidence_json",
            ):
                if column not in existing_columns:
                    self.conn.execute(
                        f"ALTER TABLE incidents ADD COLUMN {column} TEXT"
                    )

'''

    s = s.replace(anchor, migration + anchor, 1)

# ------------------------------------------------------------
# Replace store_incident regardless of its previous version.
# ------------------------------------------------------------

start = s.find("    def store_incident(")
end = s.find("\n    def find_previous_incidents", start)

if start == -1 or end == -1:
    raise SystemExit(
        "ERROR: Could not locate store_incident()."
    )

store_method = '''    def store_incident(self, event, assessment, evidence=None):
        """Persist a complete AI-assessed threat event."""
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

s = s[:start] + store_method + s[end:]

# ------------------------------------------------------------
# Add get_history if absent.
# ------------------------------------------------------------

if "    def get_history(" not in s:

    marker = "\n    def find_previous_incidents"

    method = '''
    def get_history(self, limit=200, threat_level=None):
        """Return complete historical Aegis threat events."""
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

            cursor = self.conn.execute(
                "SELECT * FROM incidents LIMIT 0"
            )

            columns = [
                description[0]
                for description in cursor.description
            ]

            records = []

            for row in rows:
                record = dict(zip(columns, row))

                for source, target in (
                    ("telemetry_json", "telemetry"),
                    ("assessment_json", "assessment"),
                    ("evidence_json", "evidence"),
                ):
                    raw = record.pop(source, None)

                    if raw:
                        try:
                            record[target] = json.loads(raw)
                        except Exception:
                            record[target] = raw
                    else:
                        record[target] = (
                            [] if target == "evidence" else {}
                        )

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

    if marker not in s:
        raise SystemExit(
            "ERROR: Could not locate IncidentMemory method boundary."
        )

    s = s.replace(marker, method + marker, 1)

p.write_text(s)

print("Incident memory: OK")
PY

echo
echo "[3/9] Updating autonomous storage..."

python3 <<'PY'
from pathlib import Path

p = Path("backend/main.py")
s = p.read_text()

old = '''incident_memory.store_incident(
                    payload,
                    assessment_json
                )'''

new = '''incident_memory.store_incident(
                    payload,
                    assessment_json,
                    retrieved_reports
                )'''

if old in s:
    s = s.replace(old, new, 1)
elif "incident_memory.store_incident(" in s:
    # Handle already partially patched versions.
    start = s.find("incident_memory.store_incident(")
    end = s.find(")", start)

    block = s[start:end + 1]

    if "retrieved_reports" not in block:
        block_new = '''incident_memory.store_incident(
                    payload,
                    assessment_json,
                    retrieved_reports
                )'''

        s = s[:start] + block_new + s[end + 1:]
else:
    raise SystemExit(
        "ERROR: Could not locate incident storage call."
    )

p.write_text(s)

print("Autonomous storage: OK")
PY

echo
echo "[4/9] Replacing incident history endpoint safely..."

python3 <<'PY'
from pathlib import Path

p = Path("backend/main.py")
s = p.read_text()

# Find the decorator directly.
marker = '@app.get("/api/incidents/history")'
start = s.find(marker)

if start == -1:
    # Endpoint doesn't exist; insert it before health endpoint.
    health = '@app.get("/api/health")'
    insert_at = s.find(health)

    if insert_at == -1:
        raise SystemExit(
            "ERROR: Could not locate insertion point for history endpoint."
        )

    start = insert_at
    end = insert_at

else:
    # Find the next FastAPI decorator after the incident endpoint.
    next_pos = s.find("\n@app.", start + len(marker))

    if next_pos == -1:
        # Endpoint is last endpoint.
        end = len(s)
    else:
        end = next_pos

endpoint = '''@app.get("/api/incidents/history")
async def get_incident_history(
    limit: int = 200,
    threat_level: str | None = None,
):
    """Return complete historical Aegis threat assessments."""
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

print("History endpoint: OK")
PY

echo
echo "[5/9] Removing misplaced Tactical Summary button..."

python3 <<'PY'
from pathlib import Path
import re

p = Path("frontend/src/app/page.tsx")
s = p.read_text()

# Remove any button whose contents contain INCIDENT HISTORY.
pattern = re.compile(
    r'\s*<button\b[^>]*>\s*INCIDENT HISTORY\s*</button>',
    re.DOTALL
)

matches = list(pattern.finditer(s))

if matches:
    # Remove all existing occurrences.
    s = pattern.sub("", s)
    print(f"Removed {len(matches)} existing history button(s).")
else:
    print("No existing history button found.")

p.write_text(s)
PY

echo
echo "[6/9] Adding Incident History to dashboard header..."

python3 <<'PY'
from pathlib import Path

p = Path("frontend/src/app/page.tsx")
s = p.read_text()

button = '''<button
              onClick={loadIncidentHistory}
              className="px-3 py-2 text-[10px] font-bold tracking-widest border border-cyan-500/40 text-cyan-300 bg-cyan-950/20 hover:bg-cyan-950/50 hover:border-cyan-400 transition-all"
            >
              INCIDENT HISTORY
            </button>'''

if "onClick={loadIncidentHistory}" in s:
    print("Dashboard history button already exists.")
else:
    # Prefer the main dashboard top navigation/header.
    candidates = [
        '<header',
        '<main',
        'AEGIS COMMAND',
    ]

    # Find the first substantial header area containing the dashboard title.
    title_pos = s.find("AEGIS COMMAND")

    if title_pos == -1:
        raise SystemExit(
            "ERROR: Could not locate AEGIS dashboard header."
        )

    # Find nearest parent div before title.
    div_start = s.rfind("<div", 0, title_pos)

    if div_start == -1:
        raise SystemExit(
            "ERROR: Could not locate dashboard header container."
        )

    # Insert immediately before the title container.
    s = s[:div_start] + button + "\n            " + s[div_start:]

    print("Dashboard history button inserted.")

p.write_text(s)
PY

echo
echo "[7/9] Ensuring history data model supports rich records..."

python3 <<'PY'
from pathlib import Path

p = Path("frontend/src/app/page.tsx")
s = p.read_text()

old = '''  previous_incidents?: number;
};'''

new = '''  previous_incidents?: number;
  telemetry_json?: string;
  assessment_json?: string;
  evidence_json?: string;
  object_class?: string;
  latitude?: number;
  longitude?: number;
};'''

if old in s and "telemetry_json?: string" not in s:
    s = s.replace(old, new, 1)

p.write_text(s)

print("Frontend history model: OK")
PY

echo
echo "[8/9] Validating..."

python3 -m py_compile \
    backend/main.py \
    backend/incident_memory.py

echo "Python syntax: OK"

docker compose run --rm frontend npx tsc --noEmit

echo "TypeScript: OK"

echo
echo "[9/9] Final verification..."

echo
echo "---- HISTORY ENDPOINT ----"
grep -n -A5 '@app.get("/api/incidents/history")' backend/main.py || true

echo
echo "---- INCIDENT STORAGE ----"
grep -n -A5 "incident_memory.store_incident" backend/main.py || true

echo
echo "---- DASHBOARD BUTTON ----"
grep -n "INCIDENT HISTORY" frontend/src/app/page.tsx || true

echo
echo "=============================================================="
echo " SUCCESS"
echo "=============================================================="
echo
echo "Incident History is now a dashboard-level feature."
echo
echo "New incidents retain:"
echo "  * telemetry"
echo "  * GPS coordinates"
echo "  * speed"
echo "  * direction"
echo "  * confidence"
echo "  * AI threat level"
echo "  * AI score"
echo "  * AI reasoning"
echo "  * recommended action"
echo "  * previous incident count"
echo "  * retrieved intelligence evidence"
echo
echo "Backup:"
echo "  $BACKUP"
echo
echo "Restart:"
echo "  docker compose down"
echo "  docker compose up --build"
echo
