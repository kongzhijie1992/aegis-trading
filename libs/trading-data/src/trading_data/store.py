"""Small transactional SQLite store; providers never own database connections."""

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import datetime
from pathlib import Path
from typing import Literal

from .models import DataError, Observation, number, timestamp


class DataStore:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1, 2):
                raise DataError(f"Unsupported database schema: {version}")
            if version == 1:
                if db.execute(
                    "SELECT 1 FROM observations WHERE basis='same_revision_correction_first_seen' LIMIT 1"
                ).fetchone():
                    raise DataError(
                        "Schema 1 corrections require reimport from raw payloads into a new database"
                    )
                db.execute("ALTER TABLE observations ADD COLUMN source_available_at TEXT")
                db.execute("UPDATE observations SET source_available_at=available_at")
            schema = """
            CREATE TABLE IF NOT EXISTS payloads(hash TEXT PRIMARY KEY, body BLOB NOT NULL);
            CREATE TABLE IF NOT EXISTS batches(id TEXT PRIMARY KEY, source TEXT NOT NULL,
              dataset TEXT NOT NULL, payload_hash TEXT NOT NULL REFERENCES payloads(hash),
              ingested_at TEXT NOT NULL, inserted INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS observations(
              id INTEGER PRIMARY KEY, source TEXT NOT NULL, entity TEXT NOT NULL,
              metric TEXT NOT NULL, unit TEXT NOT NULL, period_start TEXT NOT NULL,
              period_end TEXT NOT NULL, revision TEXT NOT NULL, value TEXT,
              available_at TEXT NOT NULL, source_available_at TEXT NOT NULL,
              ingested_at TEXT NOT NULL, basis TEXT NOT NULL,
              event_key TEXT NOT NULL, batch_id TEXT NOT NULL REFERENCES batches(id));
            CREATE INDEX IF NOT EXISTS asof_lookup ON observations
              (source,entity,metric,unit,available_at,ingested_at);
            CREATE INDEX IF NOT EXISTS revision_lookup ON observations(event_key,id);
            PRAGMA user_version=2;
            """
            for statement in schema.split(";"):
                if statement.strip():
                    db.execute(statement)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        with closing(sqlite3.connect(self.path, timeout=10)) as db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=FULL")
            db.execute("PRAGMA foreign_keys=ON")
            with db:
                yield db

    def ingest(
        self,
        source: str,
        dataset: str,
        payload: bytes,
        rows: list[Observation],
        ingested_at: datetime,
    ) -> dict[str, object]:
        seen = timestamp(ingested_at)
        if not source or not dataset or not payload:
            raise DataError("Nonempty source, dataset and raw payload required")
        identities: dict[tuple[str, ...], str | None] = {}
        for row in rows:
            row.validate()
            if row.source != source:
                raise DataError("Batch cannot mix sources")
            identity = (
                row.entity,
                row.metric,
                row.unit,
                row.period_start,
                row.period_end,
                row.revision,
            )
            value = number(row.value)
            if identity in identities and identities[identity] != value:
                raise DataError("Conflicting values for one revision within a batch")
            identities[identity] = value
        raw_hash = hashlib.sha256(payload).hexdigest()
        batch_id = hashlib.sha256(
            json.dumps(
                [
                    source,
                    dataset,
                    raw_hash,
                    seen,
                    [
                        [
                            r.entity,
                            r.metric,
                            r.unit,
                            r.period_start,
                            r.period_end,
                            r.revision,
                            number(r.value),
                            timestamp(r.available_at),
                            r.basis,
                        ]
                        for r in rows
                    ],
                ]
            ).encode()
        ).hexdigest()
        count = 0
        with self.connection() as db:
            prior = db.execute("SELECT inserted FROM batches WHERE id=?", (batch_id,)).fetchone()
            if prior is not None:
                return {
                    "batch_id": batch_id,
                    "inserted": 0,
                    "replayed": True,
                    "payload_sha256": raw_hash,
                }
            db.execute("INSERT OR IGNORE INTO payloads VALUES(?,?)", (raw_hash, payload))
            db.execute(
                "INSERT INTO batches VALUES(?,?,?,?,?,0)",
                (batch_id, source, dataset, raw_hash, seen),
            )
            for row in rows:
                event = hashlib.sha256(
                    json.dumps(
                        [
                            row.source,
                            row.entity,
                            row.metric,
                            row.unit,
                            row.period_start,
                            row.period_end,
                            row.revision,
                        ]
                    ).encode()
                ).hexdigest()
                latest = db.execute(
                    "SELECT value,ingested_at FROM observations WHERE event_key=? ORDER BY id DESC LIMIT 1",
                    (event,),
                ).fetchone()
                value = number(row.value)
                if latest is not None and latest["value"] == value:
                    continue
                available = timestamp(row.available_at)
                basis = row.basis
                if latest is not None:
                    if seen < latest["ingested_at"]:
                        raise DataError(
                            "Cannot insert a correction before the existing first-seen time"
                        )
                    # A changed value under the SAME provider revision has no
                    # defensible earlier release time; first-seen is the bound.
                    available = max(available, seen)
                    basis = "same_revision_correction_first_seen"
                db.execute(
                    "INSERT INTO observations(source,entity,metric,unit,period_start,period_end,revision,value,available_at,source_available_at,ingested_at,basis,event_key,batch_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        row.source,
                        row.entity,
                        row.metric,
                        row.unit,
                        row.period_start,
                        row.period_end,
                        row.revision,
                        value,
                        available,
                        timestamp(row.available_at),
                        seen,
                        basis,
                        event,
                        batch_id,
                    ),
                )
                count += 1
            db.execute("UPDATE batches SET inserted=? WHERE id=?", (count, batch_id))
        return {
            "batch_id": batch_id,
            "inserted": count,
            "replayed": False,
            "payload_sha256": raw_hash,
        }

    def as_of(
        self,
        *,
        source: str,
        entity: str,
        metric: str,
        unit: str,
        cutoff: datetime,
        knowledge: Literal["system", "source"] = "system",
    ) -> list[dict[str, object]]:
        if knowledge not in ("system", "source") or not unit:
            raise DataError("Explicit unit and knowledge mode required")
        end = timestamp(cutoff)
        extra = " AND ingested_at<=?" if knowledge == "system" else ""
        params = [source, entity, metric, unit, end] + ([end] if knowledge == "system" else [])
        with self.connection() as db:
            rows = db.execute(
                """WITH candidates AS (
              SELECT *,ROW_NUMBER() OVER(PARTITION BY period_start,period_end
                ORDER BY source_available_at DESC,ingested_at DESC,id DESC) AS rank
              FROM observations WHERE source=? AND entity=? AND metric=? AND unit=?
                AND available_at<=?"""
                + extra
                + """) SELECT * FROM candidates WHERE rank=1
                ORDER BY period_end,period_start""",
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def inventory(self) -> list[dict[str, object]]:
        with self.connection() as db:
            rows = db.execute("""SELECT source,entity,metric,unit,COUNT(*) AS revisions,
                MIN(period_end) AS first_period,MAX(period_end) AS last_period
                FROM observations GROUP BY source,entity,metric,unit ORDER BY source,entity,metric,unit""").fetchall()
        return [dict(row) for row in rows]

    def backup(self, path: Path) -> None:
        if path.resolve() == self.path.resolve() or path.exists():
            raise DataError("Backup must be a new, separate file")
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as source, closing(sqlite3.connect(path)) as target:
            source.backup(target)
