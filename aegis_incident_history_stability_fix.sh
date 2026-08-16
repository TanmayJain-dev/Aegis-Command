#!/usr/bin/env bash
set -euo pipefail

echo "=============================================================="
echo " AEGIS — INCIDENT HISTORY STABILITY FIX"
echo "=============================================================="

PAGE="frontend/src/app/page.tsx"

if [ ! -f "$PAGE" ]; then
    echo "ERROR: page.tsx missing"
    exit 1
fi

BACKUP=".aegis-history-stability-backup-$(date +%Y%m%d_%H%M%S)"

mkdir -p "$BACKUP/frontend/src/app"

cp "$PAGE" "$BACKUP/frontend/src/app/page.tsx"

echo "Backup created: $BACKUP"


echo "[1/4] Adding history request lock..."

python3 <<'PY'
from pathlib import Path

p=Path("frontend/src/app/page.tsx")
s=p.read_text()

old='const [historyLoading, setHistoryLoading] =\n    useState(false);'

new='''const [historyLoading, setHistoryLoading] =
    useState(false);

  const historyRequestLock = useRef(false);'''

if old in s:
    s=s.replace(old,new)
else:
    print("history state block already patched")


p.write_text(s)
PY


echo "[2/4] Protecting history loader..."

python3 <<'PY'
from pathlib import Path

p=Path("frontend/src/app/page.tsx")
s=p.read_text()

old='''const loadIncidentHistory = async () => {
    setHistoryLoading(true);'''

new='''const loadIncidentHistory = async () => {

    if (historyRequestLock.current) {
      console.log("[HISTORY] request ignored - already loading");
      return;
    }

    historyRequestLock.current = true;

    setHistoryLoading(true);'''

s=s.replace(old,new)


old2='''    } finally {
      setHistoryLoading(false);
    }
  };'''

new2='''    } finally {
      setHistoryLoading(false);
      historyRequestLock.current = false;
    }
  };'''

s=s.replace(old2,new2)

p.write_text(s)
PY


echo "[3/4] Limiting rendered history records..."

python3 <<'PY'
from pathlib import Path

p=Path("frontend/src/app/page.tsx")
s=p.read_text()

old='''{historyRecords
                .filter'''

new='''{historyRecords
                .slice(0,50)
                .filter'''

if old in s:
    s=s.replace(old,new)

p.write_text(s)
PY


echo "[4/4] TypeScript validation..."

docker compose run --rm frontend npx tsc --noEmit

echo ""
echo "=============================================================="
echo " SUCCESS"
echo "=============================================================="
echo "Restart:"
echo "docker compose down"
echo "docker compose up --build"
echo ""
