import sqlite3
import json
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
                    timestamp TEXT,
                    telemetry_json TEXT,
                    assessment_json TEXT,
                    evidence_json TEXT
                )
            """)
            # Lightweight SQLite migration for databases created
            # before rich incident history was introduced.
            existing_columns = {
                row[1]
                for row in self.conn.execute(
                    "PRAGMA table_info(incidents)"
                ).fetchall()
            }

            for column, column_type in (
                ("telemetry_json", "TEXT"),
                ("assessment_json", "TEXT"),
                ("evidence_json", "TEXT"),
            ):
                if column not in existing_columns:
                    self.conn.execute(
                        f"ALTER TABLE incidents ADD COLUMN {column} {column_type}"
                    )

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

    def store_incident(self, event, assessment, evidence=None):
        """Persist a complete AI-assessed threat event.

        Repeated frames are deduplicated, while the first occurrence
        retains the telemetry, AI assessment, and retrieved evidence
        required for historical review.
        """
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


    def get_history(self, limit=200, threat_level=None):
        """Return complete historical threat assessments."""
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

            columns = [
                description[0]
                for description in self.conn.execute(
                    "SELECT * FROM incidents LIMIT 0"
                ).description
            ]

            records = []

            for row in rows:
                record = dict(zip(columns, row))

                for source_key, output_key in (
                    ("telemetry_json", "telemetry"),
                    ("assessment_json", "assessment"),
                    ("evidence_json", "evidence"),
                ):
                    raw = record.pop(source_key, None)

                    if raw:
                        try:
                            record[output_key] = json.loads(raw)
                        except Exception:
                            record[output_key] = raw
                    else:
                        record[output_key] = (
                            [] if output_key == "evidence" else {}
                        )

                # Flatten commonly displayed assessment fields.
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
