#!/usr/bin/env bash

set -e

echo "=============================================="
echo " AEGIS — TACTICAL MAP STABILITY FIX"
echo "=============================================="

MAP="frontend/src/components/Map.tsx"

if [ ! -f "$MAP" ]; then
  echo "ERROR: $MAP not found."
  echo "Run this from the repository root."
  exit 1
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP=".aegis-map-stability-backup-${STAMP}"

echo
echo "[1/5] Creating backup..."
mkdir -p "$BACKUP/frontend/src/components"
cp "$MAP" "$BACKUP/frontend/src/components/Map.tsx"

echo "Backup: $BACKUP"

echo
echo "[2/5] Replacing MapUpdater..."

python3 <<'PY'
from pathlib import Path

p = Path("frontend/src/components/Map.tsx")
s = p.read_text()

start = s.find("function MapUpdater(")
end = s.find("\n\nexport default function Map", start)

if start == -1 or end == -1:
    raise SystemExit("ERROR: Could not locate MapUpdater block.")

new_block = r'''function MapUpdater({ coordinates }: { coordinates: [number, number] | null }) {
  const map = useMap();

  const lastTarget = React.useRef<[number, number] | null>(null);
  const lastCameraUpdate = React.useRef(0);

  useEffect(() => {
    if (!coordinates) return;

    const now = Date.now();
    const previous = lastTarget.current;

    /*
     * Ignore tiny coordinate changes.
     * These are usually caused by frame-to-frame detection noise.
     */
    if (
      previous &&
      Math.abs(previous[0] - coordinates[0]) < 0.00008 &&
      Math.abs(previous[1] - coordinates[1]) < 0.00008
    ) {
      return;
    }

    /*
     * Do not repeatedly interrupt Leaflet animations.
     */
    if (now - lastCameraUpdate.current < 1500) {
      lastTarget.current = coordinates;
      return;
    }

    /*
     * Keep the operator's current zoom level.
     * We should not force zoom 14 every time a target moves.
     */
    const currentZoom = map.getZoom();

    /*
     * Only move the camera when the target has actually
     * moved a meaningful geographic distance.
     */
    if (previous) {
      const latDelta = Math.abs(previous[0] - coordinates[0]);
      const lngDelta = Math.abs(previous[1] - coordinates[1]);

      if (latDelta < 0.00015 && lngDelta < 0.00015) {
        lastTarget.current = coordinates;
        return;
      }
    }

    lastTarget.current = coordinates;
    lastCameraUpdate.current = now;

    map.flyTo(
      coordinates,
      currentZoom,
      {
        duration: 0.9,
        easeLinearity: 0.35,
      }
    );
  }, [coordinates, map]);

  return null;
}'''

s = s[:start] + new_block + s[end:]

p.write_text(s)

print("MapUpdater replaced successfully.")
PY

echo
echo "[3/5] Adding a small visual smoothing transition..."

python3 <<'PY'
from pathlib import Path

p = Path("frontend/src/components/Map.tsx")
s = p.read_text()

old = '<div className="w-full h-full rounded border-none overflow-hidden relative">'

new = '<div className="w-full h-full rounded border-none overflow-hidden relative z-0">'

if old in s:
    s = s.replace(old, new, 1)
else:
    print("Map root already patched or not found.")

p.write_text(s)
PY

echo
echo "[4/5] Validating TypeScript..."

docker compose run --rm frontend npx tsc --noEmit

echo
echo "[5/5] Showing relevant diff..."

git diff -- frontend/src/components/Map.tsx

echo
echo "=============================================="
echo " SUCCESS"
echo "=============================================="
echo
echo "Map camera movement has been stabilized."
echo
echo "Changes:"
echo "  - ignores tiny GPS changes"
echo "  - limits camera updates to ~1.5s"
echo "  - preserves current zoom"
echo "  - reduces animation duration"
echo "  - prevents repeated flyTo interruptions"
echo
echo "Backup:"
echo "  $BACKUP"
echo
echo "Test with:"
echo "  docker compose up --build"
echo
