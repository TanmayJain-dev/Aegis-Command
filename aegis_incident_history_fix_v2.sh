#!/usr/bin/env bash
set -euo pipefail

echo "=============================================================="
echo " AEGIS — INCIDENT HISTORY FIX v2"
echo " Safe targeted frontend patch"
echo "=============================================================="

PAGE="frontend/src/app/page.tsx"

if [ ! -f "$PAGE" ]; then
    echo "ERROR: $PAGE not found"
    exit 1
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP=".aegis-history-v2-backup-$STAMP"

echo
echo "[1/6] Creating backup..."
mkdir -p "$BACKUP/frontend/src/app"
cp "$PAGE" "$BACKUP/frontend/src/app/page.tsx"
echo "Backup: $BACKUP"

echo
echo "[2/6] Inspecting current history implementation..."

sed -n '40,75p' "$PAGE"
echo
sed -n '470,535p' "$PAGE"
echo
sed -n '760,850p' "$PAGE"

echo
echo "[3/6] Applying targeted patch..."

python3 <<'PY'
from pathlib import Path
import re

p = Path("frontend/src/app/page.tsx")
s = p.read_text()

# ------------------------------------------------------------
# Existing state names detected from the previous script:
#
# historyOpen
# historyLoading
#
# Keep these names instead of introducing another competing
# incidentHistory state system.
# ------------------------------------------------------------

if "historyOpen" not in s:
    raise SystemExit("ERROR: Existing historyOpen state not found.")

if "historyLoading" not in s:
    raise SystemExit("ERROR: Existing historyLoading state not found.")

# ------------------------------------------------------------
# Find the existing history fetch function/block.
# We specifically search around the known endpoint.
# ------------------------------------------------------------

endpoint = 'fetch("/api/incidents/history?limit=200")'

pos = s.find(endpoint)

if pos == -1:
    raise SystemExit("ERROR: Existing history fetch not found.")

# Find the beginning of the function containing the fetch.
before = s[:pos]

candidates = [
    before.rfind("const loadHistory"),
    before.rfind("const fetchHistory"),
    before.rfind("const loadIncidentHistory"),
    before.rfind("const fetchIncidentHistory"),
    before.rfind("async function loadHistory"),
    before.rfind("async function fetchHistory"),
]

start = max(candidates)

if start == -1:
    # Search backward for nearest "const " declaration.
    m = list(re.finditer(r'\n\s*const\s+\w+\s*=\s*async', before))
    if not m:
        raise SystemExit(
            "ERROR: Could not identify the existing history loader function."
        )
    start = m[-1].start()

# Find the function's opening brace.
brace_start = s.find("{", start, pos)

if brace_start == -1:
    raise SystemExit("ERROR: Could not locate history loader opening brace.")

# Parse braces to locate the end of the containing function.
depth = 0
end = None
in_string = None
escape = False

for i in range(brace_start, len(s)):
    ch = s[i]

    if in_string:
        if escape:
            escape = False
        elif ch == "\\":
            escape = True
        elif ch == in_string:
            in_string = None
        continue

    if ch in ("'", '"', "`"):
        in_string = ch
        continue

    if ch == "{":
        depth += 1
    elif ch == "}":
        depth -= 1
        if depth == 0:
            end = i + 1
            break

if end is None:
    raise SystemExit("ERROR: Could not determine history loader boundary.")

old_block = s[start:end]

print("Existing history loader found:")
print(old_block[:1200])

# ------------------------------------------------------------
# Replace ONLY that loader.
# ------------------------------------------------------------

new_loader = r'''  const loadHistory = async () => {
    if (historyLoading) {
      return;
    }

    try {
      setHistoryLoading(true);

      console.log("[INCIDENT HISTORY] FETCH START");

      const response = await fetch(
        "/api/incidents/history?limit=200",
        {
          method: "GET",
          cache: "no-store",
        }
      );

      if (!response.ok) {
        throw new Error(
          `Incident history request failed: ${response.status}`
        );
      }

      const data = await response.json();

      console.log("[INCIDENT HISTORY] FETCH COMPLETE", {
        count: Array.isArray(data)
          ? data.length
          : Array.isArray(data?.incidents)
            ? data.incidents.length
            : Array.isArray(data?.history)
              ? data.history.length
              : 0,
      });

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
    } catch (error) {
      console.error("[INCIDENT HISTORY] FETCH ERROR", error);
    } finally {
      setHistoryLoading(false);
    }
  };

'''

# ------------------------------------------------------------
# Ensure incidentHistory state exists.
# ------------------------------------------------------------

if "const [incidentHistory" not in s:
    state_anchor = re.search(
        r'const\s+\[historyLoading[^\n]*\n',
        s
    )

    if state_anchor:
        insertion = (
            state_anchor.group(0)
            + '  const [incidentHistory, setIncidentHistory] = useState<any[]>([]);\n'
        )
        s = s[:state_anchor.start()] + insertion + s[state_anchor.end():]
    else:
        raise SystemExit("ERROR: Could not locate history state.")

# ------------------------------------------------------------
# Replace old loader.
# ------------------------------------------------------------

s = s[:start] + new_loader + s[end:]

# ------------------------------------------------------------
# Find existing history button and make sure it explicitly
# loads data ONLY on click.
# ------------------------------------------------------------

button_pattern = re.compile(
    r'<button\b[\s\S]*?</button>',
    re.I
)

buttons = list(button_pattern.finditer(s))

patched_button = False

for m in buttons:
    block = m.group(0)

    if "Incident History" in block or "INCIDENT HISTORY" in block:
        if "onClick" in block:
            block2 = re.sub(
                r'onClick=\{[^}]*\}',
                'onClick={async () => {\n'
                '              setHistoryOpen(true);\n'
                '              await loadHistory();\n'
                '            }}',
                block,
                count=1,
            )
        else:
            block2 = block.replace(
                "<button",
                "<button\n"
                "            onClick={async () => {\n"
                "              setHistoryOpen(true);\n"
                "              await loadHistory();\n"
                "            }}",
                1,
            )

        s = s[:m.start()] + block2 + s[m.end():]
        patched_button = True
        break

if not patched_button:
    print("WARNING: Could not automatically locate Incident History button.")
    print("The existing history panel will remain untouched.")

# ------------------------------------------------------------
# IMPORTANT:
# Remove accidental repeated history-loading effects.
# We only remove effects that directly contain the endpoint.
# ------------------------------------------------------------

effect_pattern = re.compile(
    r'\n\s*useEffect\(\(\)\s*=>\s*\{[\s\S]*?'
    r'api/incidents/history\?limit=200'
    r'[\s\S]*?\n\s*\},\s*\[[^\]]*\]\s*\);',
    re.M,
)

matches = list(effect_pattern.finditer(s))

for m in reversed(matches):
    block = m.group(0)

    # Don't remove our loadHistory function.
    if "const loadHistory" not in block:
        print("Removing repeated history useEffect.")
        s = s[:m.start()] + "\n" + s[m.end():]

p.write_text(s)

print("Targeted history patch complete.")
PY

echo
echo "[4/6] Checking history endpoint count..."

COUNT="$(grep -c 'api/incidents/history?limit=200' "$PAGE" || true)"

echo "Endpoint references: $COUNT"

if [ "$COUNT" -gt 2 ]; then
    echo "ERROR: Too many history endpoint references."
    grep -n 'api/incidents/history?limit=200' "$PAGE"
    echo
    echo "Restoring backup..."
    cp "$BACKUP/frontend/src/app/page.tsx" "$PAGE"
    exit 1
fi

echo
echo "[5/6] Running TypeScript validation..."

docker compose run --rm frontend npx tsc --noEmit

echo
echo "[6/6] Final checks..."

echo
echo "History loader:"
grep -n -A45 -B5 'const loadHistory' "$PAGE" || true

echo
echo "History endpoint:"
grep -n 'api/incidents/history' "$PAGE" || true

echo
echo "History button:"
grep -n -A8 -B4 -E 'Incident History|INCIDENT HISTORY' "$PAGE" || true

echo
echo "=============================================================="
echo " SUCCESS"
echo "=============================================================="
echo
echo "No manual changes required."
echo
echo "Backup:"
echo "  $BACKUP"
echo
echo "Next:"
echo "  docker compose down"
echo "  docker compose up --build"
echo
