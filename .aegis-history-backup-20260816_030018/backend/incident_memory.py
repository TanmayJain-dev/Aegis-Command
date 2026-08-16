import sqlite3
import threading
from datetime import datetime, timezone, timedelta


class IncidentMemory:
    """Persistent memory for distinct threat incidents.

    Repeated video frames can describe the same ongoing object. A short
    temporal + spatial window prevents those frames from becoming hundreds
    of historical incidents.
    """

    DEDUP_SECONDS = 30
    COORD_EPSILON = 0.0005

    def __init__(self, db_path="incidents.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.lock = threading.Lock()
        self.create_table()

    def create_table(self):
        with self.lock:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS incidents(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    object_class TEXT,
                    latitude REAL,
                    longitude REAL,
                    threat_level TEXT,
                    score INTEGER,
                    timestamp TEXT
                )
            """)
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_incidents_class_time
                ON incidents(object_class, timestamp)
            """)
            self.conn.commit()

    def _is_duplicate_locked(self, event):
        object_class = event.get("class")
        latitude = event.get("latitude")
        longitude = event.get("longitude")

        if not object_class:
            return False

        cutoff = (
            datetime.now(timezone.utc)
            - timedelta(seconds=self.DEDUP_SECONDS)
        ).isoformat()

        try:
            latitude = float(latitude) if latitude is not None else None
            longitude = float(longitude) if longitude is not None else None
        except (TypeError, ValueError):
            latitude = longitude = None

        if latitude is not None and longitude is not None:
            row = self.conn.execute("""
                SELECT 1
                FROM incidents
                WHERE object_class = ?
                  AND timestamp >= ?
                  AND latitude IS NOT NULL
                  AND longitude IS NOT NULL
                  AND ABS(latitude - ?) <= ?
                  AND ABS(longitude - ?) <= ?
                LIMIT 1
            """, (
                object_class,
                cutoff,
                latitude,
                self.COORD_EPSILON,
                longitude,
                self.COORD_EPSILON,
            )).fetchone()
        else:
            row = self.conn.execute("""
                SELECT 1
                FROM incidents
                WHERE object_class = ?
                  AND timestamp >= ?
                LIMIT 1
            """, (object_class, cutoff)).fetchone()

        return row is not None

    def store_incident(self, event, assessment):
        with self.lock:
            if self._is_duplicate_locked(event):
                return False

            self.conn.execute("""
                INSERT INTO incidents
                (object_class, latitude, longitude, threat_level, score, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                event.get("class"),
                event.get("latitude"),
                event.get("longitude"),
                assessment.get("threat_level"),
                assessment.get("score"),
                datetime.now(timezone.utc).isoformat(),
            ))
            self.conn.commit()
            return True

    def find_previous_incidents(self, object_class):
        with self.lock:
            row = self.conn.execute(
                "SELECT COUNT(*) FROM incidents WHERE object_class = ?",
                (object_class,),
            ).fetchone()
            return row[0] if row else 0

    def close(self):
        with self.lock:
            self.conn.close()
