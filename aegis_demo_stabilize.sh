#!/usr/bin/env bash
set -euo pipefail

PAGE="frontend/src/app/page.tsx"
BACKUP=".aegis-demo-stability-$(date +%Y%m%d_%H%M%S)"

echo "=============================================="
echo " AEGIS — DEMO STABILITY PATCH"
echo "=============================================="

mkdir -p "$BACKUP/frontend/src/app"
cp "$PAGE" "$BACKUP/frontend/src/app/page.tsx"

echo "[1/4] Backup created: $BACKUP"

python3 - <<'PY'
from pathlib import Path
import re

p = Path("frontend/src/app/page.tsx")
s = p.read_text()

# Disable the history loader so accidental clicks cannot trigger
# repeated API requests during the live demo.
s = re.sub(
    r'  const loadIncidentHistory = async \(\) => \{.*?\n  \};\n\n',
    '''  const loadIncidentHistory = () => {
    console.warn("[HISTORY] Incident history temporarily disabled for demo stability.");
    return;
  };

''',
    s,
    flags=re.S,
)

p.write_text(s)
PY

echo "[2/4] Disabled unstable history request path."

echo "[3/4] TypeScript validation..."
docker compose run --rm frontend npx tsc --noEmit

echo "[4/4] Validation passed."

echo
echo "=============================================="
echo " SUCCESS"
echo "=============================================="
echo
echo "The core demo remains enabled:"
echo "  ✓ UAV/video detection"
echo "  ✓ autonomous threat engine"
echo "  ✓ WebSocket assessments"
echo "  ✓ AI reasoning"
echo "  ✓ live map movement"
echo "  ✓ tactical summary"
echo "  ✓ intelligence search"
echo
echo "Incident History is safely disabled for the demo."
echo
echo "Backup:"
echo "  $BACKUP"
echo
