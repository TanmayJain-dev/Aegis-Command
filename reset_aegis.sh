#!/bin/bash
echo "[AEGIS SYSTEM] Initiating memory wipe..."
rm -f backend/incidents.db
echo "[AEGIS SYSTEM] SQLite Threat memory wiped."
echo "[AEGIS SYSTEM] Restarting Backend Container to flush FAISS vectors..."
docker compose restart backend
echo "[AEGIS SYSTEM] Ready for next judge."