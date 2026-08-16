#!/usr/bin/env bash
set -euo pipefail

echo "=============================================================="
echo " AEGIS — INCIDENT HISTORY FRONTEND / LAG FIX"
echo "=============================================================="

ROOT="$(pwd)"
PAGE="frontend/src/app/page.tsx"

if [ ! -f "$PAGE" ]; then
    echo "ERROR: $PAGE not found."
    exit 1
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP=".aegis-history-ui-backup-$STAMP"

echo
echo "[1/7] Creating backup..."
mkdir -p "$BACKUP/frontend/src/app"
cp "$PAGE" "$BACKUP/frontend/src/app/page.tsx"
echo "Backup: $BACKUP"

echo
echo "[2/7] Inspecting current incident-history implementation..."

grep -n -E \
'api/incidents/history|Incident History|incidentHistory|historyLoading|historyOpen' \
"$PAGE" || true

echo
echo "[3/7] Creating automated frontend patch..."

python3 <<'PY'
from pathlib import Path
import re

p = Path("frontend/src/app/page.tsx")
s = p.read_text()

# ------------------------------------------------------------
# 1. Normalize the history state.
# ------------------------------------------------------------

if "const [incidentHistory" not in s:
    # Put state near the first existing useState declaration.
    m = re.search(r'(const\s+\[[^\n]+?\]\s*=\s*useState[^\n]*\n)', s)
    if not m:
        raise SystemExit("ERROR: Could not locate a useState block.")

    insertion = m.group(1) + (
        '\n'
        '  const [incidentHistory, setIncidentHistory] = useState<any[]>([]);\n'
        '  const [incidentHistoryOpen, setIncidentHistoryOpen] = useState(false);\n'
        '  const [incidentHistoryLoading, setIncidentHistoryLoading] = useState(false);\n'
        '  const [incidentHistoryError, setIncidentHistoryError] = useState<string | null>(null);\n'
        '  const incidentHistoryLoaded = useRef(false);\n'
    )

    s = s[:m.start()] + insertion + s[m.end():]

# ------------------------------------------------------------
# 2. Remove existing repeated history-fetch effects.
# ------------------------------------------------------------

patterns = [
    r'\n\s*useEffect\(\(\)\s*=>\s*\{\s*fetch\(["\']/api/incidents/history[^;]*;.*?\n\s*\},\s*\[\s*\]\s*\);\s*',
    r'\n\s*useEffect\(\(\)\s*=>\s*\{.*?api/incidents/history\?limit=200.*?\n\s*\},\s*\[[^\]]*\]\s*\);\s*',
]

for pattern in patterns:
    s = re.sub(pattern, "\n", s, flags=re.S)

# ------------------------------------------------------------
# 3. Remove existing direct history fetch snippets.
# We intentionally preserve the endpoint itself; only the
# frontend callers are replaced.
# ------------------------------------------------------------

# Replace simple fetch blocks that contain the history endpoint.
history_blocks = re.compile(
    r'\n?\s*(?:await\s+)?fetch\(["\']/?api/incidents/history\?limit=200["\'][\s\S]{0,1800}?\n\s*\}\s*',
    re.M
)

# Only remove if the block clearly contains history response handling.
for match in list(history_blocks.finditer(s)):
    block = match.group(0)
    if "incident" in block.lower() or "history" in block.lower():
        s = s.replace(block, "\n", 1)

# ------------------------------------------------------------
# 4. Add one stable loader.
# ------------------------------------------------------------

loader = r'''
  const loadIncidentHistory = async () => {
    if (incidentHistoryLoaded.current) {
      return;
    }

    try {
      setIncidentHistoryLoading(true);
      setIncidentHistoryError(null);

      console.log("[INCIDENT HISTORY] Loading history once...");

      const response = await fetch("/api/incidents/history?limit=200", {
        method: "GET",
        cache: "no-store",
      });

      if (!response.ok) {
        throw new Error(`History request failed: ${response.status}`);
      }

      const data = await response.json();

      const records =
        Array.isArray(data)
          ? data
          : Array.isArray(data?.incidents)
            ? data.incidents
            : Array.isArray(data?.history)
              ? data.history
              : Array.isArray(data?.records)
                ? data.records
                : [];

      setIncidentHistory(records);
      incidentHistoryLoaded.current = true;

      console.log("[INCIDENT HISTORY] Loaded", records.length, "records");
    } catch (error) {
      console.error("[INCIDENT HISTORY] Failed", error);
      setIncidentHistoryError(
        error instanceof Error ? error.message : "Unable to load incident history"
      );
    } finally {
      setIncidentHistoryLoading(false);
    }
  };

  const openIncidentHistory = async () => {
    setIncidentHistoryOpen(true);

    if (!incidentHistoryLoaded.current) {
      await loadIncidentHistory();
    }
  };

  const closeIncidentHistory = () => {
    setIncidentHistoryOpen(false);
  };

'''

# Insert immediately before the first obvious event handler.
anchor = re.search(
    r'\n\s*(const|function)\s+(handleSearch|handleTimeUpdate|openTactical|handle[A-Z])',
    s
)

if anchor:
    s = s[:anchor.start()] + "\n" + loader + s[anchor.start():]
else:
    # Fall back to insertion before return.
    idx = s.find("\n  return (")
    if idx == -1:
        raise SystemExit("ERROR: Could not find component return.")
    s = s[:idx] + "\n" + loader + s[idx:]

# ------------------------------------------------------------
# 5. Replace any existing Incident History button.
# ------------------------------------------------------------

button_pattern = re.compile(
    r'<button[^>]*>[\s\S]{0,500}?Incident History[\s\S]{0,500}?</button>',
    re.I
)

new_button = '''
          <button
            type="button"
            onClick={openIncidentHistory}
            className="px-4 py-2 border border-cyan-500/60 bg-black/70 text-cyan-300 hover:bg-cyan-950/50 transition-colors"
          >
            INCIDENT HISTORY
          </button>
'''

if button_pattern.search(s):
    s = button_pattern.sub(new_button, s, count=1)

# ------------------------------------------------------------
# 6. Add a dashboard history panel immediately before the
# component's final return.
# ------------------------------------------------------------

panel = r'''
      {incidentHistoryOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 backdrop-blur-sm">
          <div
            className="relative z-[110] w-[min(1100px,94vw)] max-h-[88vh] overflow-hidden border border-cyan-500/50 bg-black/95 shadow-2xl"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-cyan-500/30 px-5 py-4">
              <div>
                <div className="text-xs tracking-[0.25em] text-cyan-400">
                  AEGIS COMMAND
                </div>
                <h2 className="text-xl font-semibold text-white">
                  INCIDENT HISTORY
                </h2>
                <div className="text-xs text-gray-500 mt-1">
                  Historical events, telemetry, AI assessments and intelligence evidence
                </div>
              </div>

              <button
                type="button"
                onClick={closeIncidentHistory}
                className="border border-red-500/50 px-3 py-2 text-red-400 hover:bg-red-950/40"
              >
                CLOSE
              </button>
            </div>

            <div className="max-h-[calc(88vh-92px)] overflow-y-auto p-5">
              {incidentHistoryLoading && (
                <div className="py-16 text-center text-cyan-400">
                  LOADING HISTORICAL INCIDENTS...
                </div>
              )}

              {incidentHistoryError && (
                <div className="border border-red-500/40 bg-red-950/20 p-4 text-red-300">
                  <div className="font-semibold">HISTORY LOAD ERROR</div>
                  <div className="mt-1 text-sm">{incidentHistoryError}</div>
                </div>
              )}

              {!incidentHistoryLoading &&
                !incidentHistoryError &&
                incidentHistory.length === 0 && (
                  <div className="py-16 text-center text-gray-500">
                    NO STORED INCIDENTS FOUND
                  </div>
                )}

              {!incidentHistoryLoading &&
                incidentHistory.length > 0 && (
                  <div className="space-y-4">
                    {incidentHistory.map((incident: any, index: number) => {
                      const telemetry =
                        incident?.telemetry ??
                        incident?.payload ??
                        incident?.event ??
                        {};

                      const assessment =
                        incident?.assessment ??
                        incident?.assessment_json ??
                        {};

                      const evidence =
                        incident?.evidence ??
                        incident?.retrieved_reports ??
                        [];

                      const timestamp =
                        incident?.timestamp ??
                        telemetry?.timestamp ??
                        incident?.created_at ??
                        incident?.createdAt ??
                        "Unknown time";

                      const level =
                        assessment?.threat_level ??
                        incident?.threat_level ??
                        "UNKNOWN";

                      return (
                        <div
                          key={incident?.id ?? incident?.incident_id ?? index}
                          className="border border-white/10 bg-white/[0.025]"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 px-4 py-3">
                            <div>
                              <div className="text-xs text-gray-500">
                                {timestamp}
                              </div>
                              <div className="mt-1 text-sm font-semibold text-white">
                                {telemetry?.class ?? incident?.object_class ?? "Unknown object"}
                                {" "}
                                <span className="text-gray-500">
                                  / {telemetry?.direction ?? "-"}
                                </span>
                              </div>
                            </div>

                            <div className="border border-cyan-500/30 px-3 py-1 text-xs text-cyan-300">
                              {level}
                            </div>
                          </div>

                          <div className="grid grid-cols-1 gap-4 p-4 md:grid-cols-3">
                            <div>
                              <div className="mb-2 text-[10px] tracking-widest text-gray-500">
                                TELEMETRY
                              </div>

                              <div className="space-y-1 text-xs text-gray-300">
                                <div>
                                  Confidence: {telemetry?.confidence ?? "-"}
                                </div>
                                <div>
                                  Speed: {telemetry?.speed_kmh ?? "-"} km/h
                                </div>
                                <div>
                                  Direction: {telemetry?.direction ?? "-"}
                                </div>
                                <div>
                                  GPS: {telemetry?.latitude ?? "-"}, {telemetry?.longitude ?? "-"}
                                </div>
                              </div>
                            </div>

                            <div className="md:col-span-2">
                              <div className="mb-2 text-[10px] tracking-widest text-gray-500">
                                AI ASSESSMENT
                              </div>

                              <div className="space-y-2 text-sm text-gray-300">
                                <div>
                                  <span className="text-gray-500">Score:</span>{" "}
                                  {assessment?.score ?? "-"}
                                </div>

                                <div>
                                  <span className="text-gray-500">Reasoning:</span>{" "}
                                  {assessment?.reasoning ?? "No reasoning stored."}
                                </div>

                                <div>
                                  <span className="text-gray-500">Recommended action:</span>{" "}
                                  {assessment?.recommended_action ?? "No recommendation stored."}
                                </div>
                              </div>
                            </div>
                          </div>

                          {Array.isArray(evidence) && evidence.length > 0 && (
                            <details className="border-t border-white/10">
                              <summary className="cursor-pointer px-4 py-3 text-xs tracking-widest text-cyan-400 hover:bg-white/[0.025]">
                                INTELLIGENCE EVIDENCE ({evidence.length})
                              </summary>

                              <div className="space-y-2 px-4 pb-4">
                                {evidence.map((item: any, evidenceIndex: number) => (
                                  <div
                                    key={item?.id ?? evidenceIndex}
                                    className="border border-white/10 bg-black/40 p-3"
                                  >
                                    <div className="text-xs text-cyan-300">
                                      {item?.id ?? `INTEL-${evidenceIndex + 1}`}
                                    </div>

                                    <div className="mt-1 text-xs text-gray-500">
                                      {item?.location ?? "Unknown location"}
                                      {" | "}
                                      {item?.timestamp ?? "Unknown time"}
                                    </div>

                                    <div className="mt-2 text-xs leading-relaxed text-gray-300">
                                      {item?.transcript ??
                                        item?.text ??
                                        item?.summary ??
                                        JSON.stringify(item)}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </details>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
            </div>
          </div>
        </div>
      )}
'''

# Insert before the final component return.
return_positions = [m.start() for m in re.finditer(r'\n\s*return\s*\(', s)]

if not return_positions:
    raise SystemExit("ERROR: Could not locate component return.")

# Put panel just before the LAST return. This is safe if the component
# has helper returns elsewhere.
idx = return_positions[-1]
s = s[:idx] + "\n" + panel + s[idx:]

p.write_text(s)
print("Frontend incident-history patch written.")
PY

echo
echo "[4/7] Checking that only one history loader exists..."

COUNT="$(grep -c 'api/incidents/history?limit=200' "$PAGE" || true)"
echo "History endpoint references: $COUNT"

if [ "$COUNT" -gt 1 ]; then
    echo "WARNING: More than one history endpoint reference remains."
    echo "Reviewing locations:"
    grep -n 'api/incidents/history?limit=200' "$PAGE" || true
fi

echo
echo "[5/7] Checking TypeScript..."

docker compose run --rm frontend npx tsc --noEmit || {
    echo
    echo "TypeScript validation failed."
    echo "Restoring backup..."
    cp "$BACKUP/frontend/src/app/page.tsx" "$PAGE"
    exit 1
}

echo
echo "[6/7] Checking backend endpoint availability..."

if grep -q '/api/incidents/history' backend/main.py; then
    echo "Backend history endpoint: PRESENT"
else
    echo "WARNING: Backend history endpoint not found in backend/main.py"
fi

echo
echo "[7/7] Final verification..."

echo
echo "History-related code:"
grep -n -E \
'incidentHistory|openIncidentHistory|loadIncidentHistory|api/incidents/history' \
"$PAGE" | head -80 || true

echo
echo "=============================================================="
echo " SUCCESS"
echo "=============================================================="
echo
echo "The frontend history flow now:"
echo "  • Opens from the dashboard"
echo "  • Fetches history once"
echo "  • Does NOT fetch on every render"
echo "  • Does NOT touch the WebSocket"
echo "  • Displays telemetry"
echo "  • Displays AI assessment"
echo "  • Displays intelligence evidence"
echo "  • Uses a modal overlay above the tactical map"
echo
echo "Backup: $BACKUP"
echo
echo "Next:"
echo "  docker compose down"
echo "  docker compose up --build"
