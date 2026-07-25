"""Pull Oura data into a local SQLite database.

Run: python -m ingestion.ingest --start 2022-01-01

Idempotent: every document is upserted on (endpoint, doc_id), so re-running
never creates duplicates. Heart rate is high-volume time series and is
fetched separately with --heartrate.

Storage is SQLite (data/oura.db, gitignored) — zero setup, stdlib only.
The schema and upsert pattern translate 1:1 to PostgreSQL later.
"""

import argparse
import datetime as dt
import json
import os
import sqlite3

from ingestion.client import OuraClient

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "oura.db")

# Daily-level endpoints: small volume, safe to fetch full history
DAILY_ENDPOINTS = [
    "daily_sleep",
    "daily_readiness",
    "daily_activity",
    "daily_stress",
    "daily_spo2",
    "sleep",          # per-sleep-period detail (HR, HRV, stages)
    "workout",
    "session",
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS oura_documents (
    endpoint     TEXT NOT NULL,
    doc_id       TEXT NOT NULL,
    day          TEXT,
    payload      TEXT NOT NULL,
    ingested_at  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (endpoint, doc_id)
);
CREATE INDEX IF NOT EXISTS idx_documents_endpoint_day
    ON oura_documents (endpoint, day);
"""

UPSERT = """
INSERT INTO oura_documents (endpoint, doc_id, day, payload)
VALUES (?, ?, ?, ?)
ON CONFLICT (endpoint, doc_id)
DO UPDATE SET payload = excluded.payload, ingested_at = datetime('now')
"""


def doc_day(doc: dict) -> str | None:
    """Best-effort day extraction; endpoints use 'day' or 'timestamp'."""
    if "day" in doc:
        return doc["day"]
    ts = doc.get("timestamp") or doc.get("start_datetime")
    return ts[:10] if ts else None


def upsert(conn, endpoint: str, docs: list[dict]) -> int:
    rows = [
        (endpoint, str(d.get("id", doc_day(d))), doc_day(d), json.dumps(d))
        for d in docs
    ]
    conn.executemany(UPSERT, rows)
    conn.commit()
    return len(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2022-01-01", help="start date YYYY-MM-DD")
    parser.add_argument("--end", default=str(dt.date.today()), help="end date YYYY-MM-DD")
    parser.add_argument("--heartrate", action="store_true",
                        help="also fetch raw heart rate time series (high volume)")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)

    client = OuraClient()

    for endpoint in DAILY_ENDPOINTS:
        docs = list(client.fetch_all(endpoint, args.start, args.end))
        n = upsert(conn, endpoint, docs)
        print(f"{endpoint:20s} {n:6d} documents")

    if args.heartrate:
        start_dt = f"{args.start}T00:00:00+00:00"
        end_dt = f"{args.end}T23:59:59+00:00"
        docs = [
            {"id": f"hr_{d['timestamp']}", "timestamp": d["timestamp"],
             "bpm": d["bpm"], "source": d.get("source")}
            for d in client.fetch_all_heartrate(start_dt, end_dt)
        ]
        n = upsert(conn, "heartrate", docs)
        print(f"{'heartrate':20s} {n:6d} documents")

    conn.close()
    print(f"\nDone. Database: {os.path.abspath(DB_PATH)}")


if __name__ == "__main__":
    main()
