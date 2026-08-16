#!/usr/bin/env bash

set -e

echo "===================================================="
echo " AEGIS — INCIDENT + INTEL HISTORY FEATURE"
echo "===================================================="

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
BACKUP=".aegis-history-backup-${STAMP}"

echo
echo "[1/7] Creating backup..."

mkdir -p \
  "$BACKUP/frontend/src/app" \
  "$BACKUP/backend"

cp "$PAGE" "$BACKUP/frontend/src/app/page.tsx"
cp "$MAIN" "$BACKUP/backend/main.py"
cp "$MEMORY" "$BACKUP/backend/incident_memory.py"

echo "Backup: $BACKUP"

echo
echo "[2/7] Inspecting incident-memory API..."

grep -nE \
'def |sqlite|SELECT|CREATE TABLE|store_incident|find_previous' \
"$MEMORY" | head -80 || true

echo
echo "[3/7] Adding backend history endpoint..."

python3 <<'PY'
from pathlib import Path

p = Path("backend/main.py")
s = p.read_text()

if '@app.get("/api/incidents/history")' in s:
    print("History endpoint already exists.")
else:
    marker = '\n@app.websocket("/ws/threat-engine")'

    if marker not in s:
        raise SystemExit(
            "ERROR: Could not locate threat-engine websocket endpoint."
        )

    endpoint = r'''

@app.get("/api/incidents/history")
async def get_incident_history(
    limit: int = 100,
    threat_level: str | None = None
):
    """
    Return historical Aegis threat assessments.

    This endpoint intentionally reads through the existing
    IncidentMemory database rather than creating a second
    persistence layer.
    """
    try:
        import sqlite3

        db_path = getattr(
            incident_memory,
            "db_path",
            "incidents.db"
        )

        if hasattr(db_path, "__str__"):
            db_path = str(db_path)

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        query = """
            SELECT *
            FROM incidents
        """

        params = []

        if threat_level:
            query += " WHERE threat_level = ?"
            params.append(threat_level)

        query += " ORDER BY id DESC LIMIT ?"
        params.append(max(1, min(limit, 500)))

        rows = conn.execute(query, params).fetchall()
        conn.close()

        records = []

        for row in rows:
            record = dict(row)

            # Decode JSON fields where applicable.
            for key in (
                "telemetry",
                "assessment",
                "evidence",
                "payload"
            ):
                value = record.get(key)

                if isinstance(value, str):
                    try:
                        import json
                        record[key] = json.loads(value)
                    except Exception:
                        pass

            records.append(record)

        return {
            "count": len(records),
            "records": records
        }

    except Exception as e:
        print(f"[HISTORY ERROR] {e}")

        return {
            "count": 0,
            "records": [],
            "error": str(e)
        }

'''

    s = s.replace(marker, endpoint + marker, 1)
    p.write_text(s)

    print("History endpoint added.")
PY

echo
echo "[4/7] Adding intel-history endpoint..."

python3 <<'PY'
from pathlib import Path

p = Path("backend/main.py")
s = p.read_text()

if '@app.get("/api/intel/history")' in s:
    print("Intel history endpoint already exists.")
else:
    marker = '\n@app.get("/api/incidents/history")'

    if marker not in s:
        raise SystemExit(
            "ERROR: Incident history endpoint was not found."
        )

    endpoint = r'''

@app.get("/api/intel/history")
async def get_intel_history(limit: int = 100):
    """
    Return the currently loaded intelligence records.

    Uses the application's existing mock/locked intelligence
    dataset rather than introducing another data source.
    """
    try:
        import json
        from pathlib import Path

        candidates = [
            Path("intel_data.json"),
            Path("data/intel_data.json"),
            Path("mock_intel.json"),
            Path("data/mock_intel.json"),
        ]

        data = None

        for candidate in candidates:
            if candidate.exists():
                with candidate.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                break

        if data is None:
            # Fall back to common in-memory names used by the
            # existing application.
            for name in (
                "intel_database",
                "intel_data",
                "mock_intel_data",
                "reports"
            ):
                if name in globals():
                    data = globals()[name]
                    break

        if data is None:
            return {
                "count": 0,
                "records": [],
                "message": "No directly readable intel dataset found."
            }

        if isinstance(data, dict):
            data = list(data.values())

        return {
            "count": min(len(data), limit),
            "records": data[:max(1, min(limit, 500))]
        }

    except Exception as e:
        print(f"[INTEL HISTORY ERROR] {e}")

        return {
            "count": 0,
            "records": [],
            "error": str(e)
        }

'''

    s = s.replace(marker, endpoint + marker, 1)
    p.write_text(s)

    print("Intel history endpoint added.")
PY

echo
echo "[5/7] Adding frontend history state + UI..."

python3 <<'PY'
from pathlib import Path

p = Path("frontend/src/app/page.tsx")
s = p.read_text()

# ------------------------------------------------------------
# Add types/state immediately before the main component.
# ------------------------------------------------------------

if "type AegisHistoryRecord" not in s:

    marker = "export default function"

    idx = s.find(marker)

    if idx == -1:
        raise SystemExit(
            "ERROR: Could not locate main React component."
        )

    types = r'''
type AegisHistoryRecord = {
  id?: number | string;
  incident_id?: string;
  timestamp?: string;
  created_at?: string;
  threat_level?: string;
  score?: number;
  threat_class?: string;
  class?: string;
  telemetry?: any;
  assessment?: any;
  evidence?: any[];
  payload?: any;
  reasoning?: string;
  recommended_action?: string;
  previous_incidents?: number;
};

'''

    s = s[:idx] + types + s[idx:]

# ------------------------------------------------------------
# Add state.
# ------------------------------------------------------------

if "const [historyRecords" not in s:

    marker = "export default function"

    idx = s.find(marker)

    brace = s.find("{", idx)

    state = r'''

  const [historyRecords, setHistoryRecords] =
    useState<AegisHistoryRecord[]>([]);

  const [historyOpen, setHistoryOpen] =
    useState(false);

  const [historyLoading, setHistoryLoading] =
    useState(false);

  const [selectedHistory, setSelectedHistory] =
    useState<AegisHistoryRecord | null>(null);

  const [historySearch, setHistorySearch] =
    useState("");

'''

    s = s[:brace + 1] + state + s[brace + 1:]

# ------------------------------------------------------------
# Add loader.
# ------------------------------------------------------------

if "loadIncidentHistory" not in s:

    marker = "  const handleSearch"

    idx = s.find(marker)

    if idx == -1:
        # Try another stable function marker.
        marker = "  const handleTimeUpdate"
        idx = s.find(marker)

    if idx == -1:
        raise SystemExit(
            "ERROR: Could not locate frontend function insertion point."
        )

    loader = r'''  const loadIncidentHistory = async () => {
    setHistoryLoading(true);

    try {
      const response = await fetch("/api/incidents/history?limit=200");

      if (!response.ok) {
        throw new Error(`History request failed: ${response.status}`);
      }

      const data = await response.json();

      setHistoryRecords(
        Array.isArray(data.records)
          ? data.records
          : []
      );

      setHistoryOpen(true);

    } catch (error) {
      console.error("[HISTORY] Failed to load incidents", error);
      setHistoryRecords([]);
      setHistoryOpen(true);
    } finally {
      setHistoryLoading(false);
    }
  };

'''

    s = s[:idx] + loader + s[idx:]

# ------------------------------------------------------------
# Add button near dashboard controls.
# We deliberately use a recognizable label instead of
# attempting to rewrite an unknown existing toolbar.
# ------------------------------------------------------------

if "loadIncidentHistory()" not in s:

    # Find a likely controls area.
    candidates = [
        '<button',
        '<header',
        '<main'
    ]

    inserted = False

    for marker in candidates:
        idx = s.find(marker)

        if idx != -1:
            button = r'''
          <button
            onClick={loadIncidentHistory}
            className="px-3 py-2 text-xs font-mono border border-cyan-500/40 text-cyan-300 bg-black/60 hover:bg-cyan-950/40 transition"
          >
            INCIDENT HISTORY
          </button>
'''

            s = s[:idx] + button + s[idx:]
            inserted = True
            break

    if not inserted:
        print("WARNING: Could not find toolbar insertion point.")

# ------------------------------------------------------------
# Add history modal before final return.
# ------------------------------------------------------------

if "{historyOpen && (" not in s:

    return_idx = s.rfind("return (")

    if return_idx == -1:
        raise SystemExit(
            "ERROR: Could not locate final React return."
        )

    modal = r'''
      {historyOpen && (
        <div className="fixed inset-0 z-[10000] bg-black/85 backdrop-blur-sm flex items-center justify-center p-4">

          <div className="relative z-[10001] w-full max-w-6xl max-h-[90vh] bg-slate-950 border border-cyan-500/40 shadow-2xl overflow-hidden flex flex-col">

            <div className="flex items-center justify-between px-5 py-4 border-b border-cyan-500/20">
              <div>
                <div className="text-cyan-300 font-mono text-sm tracking-widest">
                  AEGIS // INCIDENT HISTORY
                </div>
                <div className="text-slate-500 text-xs font-mono mt-1">
                  Historical threat assessments and intelligence records
                </div>
              </div>

              <button
                onClick={() => {
                  setHistoryOpen(false);
                  setSelectedHistory(null);
                }}
                className="text-slate-400 hover:text-white text-xl px-3"
              >
                ×
              </button>
            </div>

            <div className="px-5 py-3 border-b border-slate-800">
              <input
                value={historySearch}
                onChange={(e) => setHistorySearch(e.target.value)}
                placeholder="Search class, threat level, reasoning, location..."
                className="w-full bg-black border border-slate-700 px-3 py-2 text-xs font-mono text-white outline-none focus:border-cyan-500"
              />
            </div>

            <div className="flex-1 overflow-auto">

              {historyLoading ? (
                <div className="p-10 text-center text-cyan-300 font-mono text-sm">
                  LOADING HISTORICAL INTELLIGENCE...
                </div>
              ) : selectedHistory ? (

                <div className="p-6 space-y-5">

                  <button
                    onClick={() => setSelectedHistory(null)}
                    className="text-xs font-mono text-cyan-400 hover:text-white"
                  >
                    ← BACK TO HISTORY
                  </button>

                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">

                    <div className="border border-slate-800 bg-black p-3">
                      <div className="text-[10px] text-slate-500 font-mono">
                        THREAT LEVEL
                      </div>
                      <div className="text-lg font-mono text-red-300 mt-1">
                        {selectedHistory.threat_level ||
                          selectedHistory.assessment?.threat_level ||
                          "UNKNOWN"}
                      </div>
                    </div>

                    <div className="border border-slate-800 bg-black p-3">
                      <div className="text-[10px] text-slate-500 font-mono">
                        SCORE
                      </div>
                      <div className="text-lg font-mono text-white mt-1">
                        {selectedHistory.score ??
                          selectedHistory.assessment?.score ??
                          "—"}
                      </div>
                    </div>

                    <div className="border border-slate-800 bg-black p-3">
                      <div className="text-[10px] text-slate-500 font-mono">
                        CLASS
                      </div>
                      <div className="text-lg font-mono text-cyan-300 mt-1">
                        {selectedHistory.threat_class ||
                          selectedHistory.class ||
                          selectedHistory.telemetry?.class ||
                          "UNKNOWN"}
                      </div>
                    </div>

                    <div className="border border-slate-800 bg-black p-3">
                      <div className="text-[10px] text-slate-500 font-mono">
                        PREVIOUS
                      </div>
                      <div className="text-lg font-mono text-white mt-1">
                        {selectedHistory.previous_incidents ??
                          selectedHistory.assessment?.previous_incidents ??
                          "—"}
                      </div>
                    </div>

                  </div>

                  <div className="border border-slate-800 bg-black p-4">
                    <div className="text-xs text-cyan-300 font-mono mb-2">
                      AI ASSESSMENT
                    </div>

                    <div className="text-sm text-white leading-relaxed">
                      {selectedHistory.reasoning ||
                        selectedHistory.assessment?.reasoning ||
                        "No AI reasoning recorded."}
                    </div>

                    <div className="mt-4 text-xs text-slate-400 font-mono">
                      RECOMMENDED ACTION
                    </div>

                    <div className="mt-1 text-sm text-slate-200">
                      {selectedHistory.recommended_action ||
                        selectedHistory.assessment?.recommended_action ||
                        "No recommendation recorded."}
                    </div>
                  </div>

                  <div className="border border-slate-800 bg-black p-4">
                    <div className="text-xs text-cyan-300 font-mono mb-3">
                      EVENT TELEMETRY
                    </div>

                    <pre className="text-[11px] text-slate-300 whitespace-pre-wrap overflow-auto">
                      {JSON.stringify(
                        selectedHistory.telemetry ||
                        selectedHistory.payload ||
                        {},
                        null,
                        2
                      )}
                    </pre>
                  </div>

                  {Array.isArray(selectedHistory.evidence) &&
                    selectedHistory.evidence.length > 0 && (

                    <div className="border border-slate-800 bg-black p-4">

                      <div className="text-xs text-cyan-300 font-mono mb-3">
                        RETRIEVED INTELLIGENCE
                      </div>

                      <div className="space-y-3">

                        {selectedHistory.evidence.map(
                          (item: any, index: number) => (

                            <div
                              key={item.id || index}
                              className="border border-slate-800 p-3"
                            >
                              <div className="flex justify-between gap-4">

                                <span className="text-xs text-cyan-300 font-mono">
                                  {item.id || `INTEL-${index + 1}`}
                                </span>

                                <span className="text-[10px] text-slate-500 font-mono">
                                  {item.timestamp || ""}
                                </span>

                              </div>

                              <div className="text-xs text-slate-400 mt-2">
                                {item.location || "Unknown location"}
                              </div>

                              <div className="text-sm text-slate-200 mt-2 leading-relaxed">
                                {item.transcript ||
                                  item.summary ||
                                  item.text ||
                                  "No transcript available."}
                              </div>

                            </div>

                          )
                        )}

                      </div>

                    </div>
                  )}

                  <div className="border border-slate-800 bg-black p-4">
                    <div className="text-xs text-cyan-300 font-mono mb-3">
                      RAW ASSESSMENT RECORD
                    </div>

                    <pre className="text-[10px] text-slate-400 whitespace-pre-wrap overflow-auto">
                      {JSON.stringify(
                        selectedHistory.assessment || {},
                        null,
                        2
                      )}
                    </pre>
                  </div>

                </div>

              ) : (

                <div className="divide-y divide-slate-900">

                  {historyRecords
                    .filter((record) => {
                      const q = historySearch.toLowerCase();

                      if (!q) return true;

                      return JSON.stringify(record)
                        .toLowerCase()
                        .includes(q);
                    })
                    .map((record, index) => (

                      <button
                        key={record.id || record.incident_id || index}
                        onClick={() => setSelectedHistory(record)}
                        className="w-full text-left px-5 py-4 hover:bg-cyan-950/20 transition"
                      >

                        <div className="flex items-center justify-between gap-4">

                          <div className="flex items-center gap-4">

                            <div className="text-xs text-cyan-400 font-mono">
                              {record.incident_id ||
                                `INC-${record.id || index + 1}`}
                            </div>

                            <div className="text-xs text-white font-mono">
                              {record.threat_class ||
                                record.class ||
                                record.telemetry?.class ||
                                "UNKNOWN"}
                            </div>

                            <div className="text-xs text-slate-400">
                              {record.threat_level ||
                                record.assessment?.threat_level ||
                                "UNKNOWN"}
                            </div>

                          </div>

                          <div className="text-[10px] text-slate-500 font-mono">
                            {record.timestamp ||
                              record.created_at ||
                              ""}
                          </div>

                        </div>

                        <div className="mt-2 text-xs text-slate-400 truncate">
                          {record.reasoning ||
                            record.assessment?.reasoning ||
                            "No AI summary available."}
                        </div>

                      </button>

                    ))}

                  {historyRecords.length === 0 && (
                    <div className="p-10 text-center text-slate-500 font-mono text-xs">
                      NO HISTORICAL INCIDENTS FOUND
                    </div>
                  )}

                </div>

              )}

            </div>

          </div>

        </div>
      )}

'''

    s = s[:return_idx] + modal + s[return_idx:]

p.write_text(s)

print("Frontend history UI patch applied.")
PY

echo
echo "[6/7] Validating Python..."

python3 -m py_compile \
  backend/main.py \
  backend/incident_memory.py

echo "Python syntax: OK"

echo
echo "[7/7] Validating TypeScript..."

docker compose run --rm frontend npx tsc --noEmit

echo
echo "===================================================="
echo " SUCCESS"
echo "===================================================="
echo
echo "Incident History has been added."
echo
echo "Backup:"
echo "  $BACKUP"
echo
echo "Run:"
echo "  docker compose up --build"
echo
echo "Then open the dashboard and use:"
echo "  INCIDENT HISTORY"
echo
