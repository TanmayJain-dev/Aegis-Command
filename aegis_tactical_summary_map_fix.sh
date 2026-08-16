#!/usr/bin/env bash

set -e

echo "=============================================="
echo " AEGIS — TACTICAL SUMMARY + MAP FIX"
echo "=============================================="

ROOT="$(pwd)"
PAGE="frontend/src/app/page.tsx"
MAP="frontend/src/components/Map.tsx"

if [ ! -f "$PAGE" ] || [ ! -f "$MAP" ]; then
  echo "ERROR: Run this from the Aegis repository root."
  exit 1
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP=".aegis-tactical-map-fix-backup-${STAMP}"

echo
echo "[1/6] Creating backup..."
mkdir -p "$BACKUP/frontend/src/app" "$BACKUP/frontend/src/components"

cp "$PAGE" "$BACKUP/frontend/src/app/page.tsx"
cp "$MAP" "$BACKUP/frontend/src/components/Map.tsx"

echo "Backup: $BACKUP"

echo
echo "[2/6] Patching Tactical Summary stacking..."

python3 <<'PY'
from pathlib import Path

p = Path("frontend/src/app/page.tsx")
s = p.read_text()

old = '<div className="fixed inset-0 z-50 flex items-center justify-center p-4">'

new = '<div className="fixed inset-0 z-[10000] flex items-center justify-center p-4">'

if old not in s:
    print("WARNING: Tactical Summary root class not found.")
else:
    s = s.replace(old, new, 1)

old = '<div className="absolute inset-0 bg-black/80 backdrop-blur-md"'
new = '<div className="absolute inset-0 z-[10000] bg-black/80 backdrop-blur-md"'

if old not in s:
    print("WARNING: Tactical Summary backdrop not found.")
else:
    s = s.replace(old, new, 1)

old = '<div className="relative bg-slate-950 border border-fuchsia-900/50 rounded shadow-[0_0_50px_rgba(217,70,239,0.15)] w-full max-w-2xl overflow-hidden flex flex-col">'

new = '<div className="relative z-[10001] bg-slate-950 border border-fuchsia-900/50 rounded shadow-[0_0_50px_rgba(217,70,239,0.15)] w-full max-w-2xl overflow-hidden flex flex-col">'

if old not in s:
    print("WARNING: Tactical Summary content container not found.")
else:
    s = s.replace(old, new, 1)

p.write_text(s)
print("Tactical Summary stacking patched.")
PY

echo
echo "[3/6] Patching Leaflet map stacking..."

python3 <<'PY'
from pathlib import Path

p = Path("frontend/src/components/Map.tsx")
s = p.read_text()

old = '<div className="w-full h-full rounded border-none overflow-hidden relative">'

new = '<div className="w-full h-full rounded border-none overflow-hidden relative z-0">'

if old not in s:
    print("WARNING: Map root container not found.")
else:
    s = s.replace(old, new, 1)

old = 'className="absolute top-2 left-2 z-[400]'

new = 'className="absolute top-2 left-2 z-[401]'

if old in s:
    s = s.replace(old, new, 1)

p.write_text(s)
print("Map stacking patched.")
PY

echo
echo "[4/6] Replacing aggressive map flyTo behavior..."

python3 <<'PY'
from pathlib import Path

p = Path("frontend/src/components/Map.tsx")
s = p.read_text()

old = '''function MapUpdater({ coordinates }: { coordinates: [number, number] | null }) {
  const map = useMap();
  useEffect(() => {
    if (coordinates) { map.flyTo(coordinates, 14, { duration: 2.0, easeLinearity: 0.25 }); }
  }, [coordinates, map]);
  return null;
}'''

new = '''function MapUpdater({ coordinates }: { coordinates: [number, number] | null }) {
  const map = useMap();
  const lastCoordinates = React.useRef<[number, number] | null>(null);
  const lastUpdate = React.useRef(0);

  useEffect(() => {
    if (!coordinates) return;

    const now = Date.now();
    const previous = lastCoordinates.current;

    // Ignore extremely small coordinate changes.
    if (
      previous &&
      Math.abs(previous[0] - coordinates[0]) < 0.00005 &&
      Math.abs(previous[1] - coordinates[1]) < 0.00005
    ) {
      return;
    }

    // Do not continuously interrupt Leaflet animations.
    if (now - lastUpdate.current < 1200) {
      return;
    }

    lastCoordinates.current = coordinates;
    lastUpdate.current = now;

    const currentZoom = map.getZoom();

    map.flyTo(
      coordinates,
      Math.max(currentZoom, 12),
      {
        duration: 0.8,
        easeLinearity: 0.35,
      }
    );
  }, [coordinates, map]);

  return null;
}'''

if old not in s:
    print("WARNING: Existing MapUpdater block not found.")
else:
    s = s.replace(old, new, 1)

p.write_text(s)
print("MapUpdater smoothing/animation patch applied.")
PY

echo
echo "[5/6] Validating TypeScript..."

docker compose run --rm frontend npx tsc --noEmit

echo
echo "[6/6] Checking resulting diff..."

git diff -- frontend/src/app/page.tsx frontend/src/components/Map.tsx

echo
echo "=============================================="
echo " SUCCESS"
echo "=============================================="
echo
echo "Tactical Summary is now above Leaflet."
echo "Map movement is rate-limited and less jumpy."
echo
echo "Backup:"
echo "  $BACKUP"
echo
echo "Next:"
echo "  docker compose up --build"
echo
