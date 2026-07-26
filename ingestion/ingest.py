"""Pull Oura data into PostgreSQL.

Run: python -m ingestion.ingest            # incremental, the daily default
     python -m ingestion.ingest --full     # refetch the whole history
     python -m ingestion.ingest --start 2024-01-01 --end 2024-03-31

Incremental by default. Each endpoint resumes from the newest day already
stored, minus an overlap window, instead of refetching four years every run.
Heart rate is high-volume time series and stays opt-in via --heartrate.

Two properties make this safe to run as often as you like:

* The upsert is conditional. A document whose payload has not changed is left
  alone, so `ingested_at` means "when this document last changed" rather than
  "when the job last touched it". That is what makes `dbt source freshness`
  meaningful: it reports whether data is actually arriving.
* The overlap window means revisions are not missed. Oura keeps editing recent
  days, since sleep staging is finalised after the fact and daily scores get
  revised, so a strict high-water mark would permanently freeze the first
  version of every recent night. Refetching the trailing window costs almost
  nothing, because unchanged documents write nothing.
"""

import argparse
import datetime as dt
import json
import os

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

from ingestion.client import OuraClient

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

# Earliest day worth asking for. The ring history actually starts 2022-08-23.
DEFAULT_START = "2022-01-01"

# How far back an incremental run re-checks. Ten days comfortably covers Oura's
# revision behaviour, but it is a safety margin rather than a measured latency:
# the original load was one backfill, so the table carries no evidence about how
# long revisions take to settle. Now that the upsert only writes real changes,
# future runs will make that latency measurable.
OVERLAP_DAYS = 10

UPSERT_SQL = """
    INSERT INTO raw.oura_documents (endpoint, doc_id, day, payload)
    VALUES %s
    ON CONFLICT (endpoint, doc_id)
    DO UPDATE SET payload = EXCLUDED.payload, ingested_at = now()
    WHERE raw.oura_documents.payload IS DISTINCT FROM EXCLUDED.payload
"""

load_dotenv()


def doc_day(doc: dict) -> str | None:
    """Best-effort day extraction; endpoints use 'day' or 'timestamp'."""
    if "day" in doc:
        return doc["day"]
    ts = doc.get("timestamp") or doc.get("start_datetime")
    return ts[:10] if ts else None


def upsert(conn, endpoint: str, docs: list[dict]) -> int:
    """Insert or update documents. Returns the rows actually written.

    Unchanged payloads are skipped by the WHERE clause on DO UPDATE, so the
    return value counts new and revised documents rather than documents seen.
    """
    rows = [
        (endpoint, str(d.get("id", doc_day(d))), doc_day(d), json.dumps(d))
        for d in docs
    ]
    if not rows:
        return 0
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(cur, UPSERT_SQL, rows)
        written = cur.rowcount
    conn.commit()
    return max(written, 0)


def resume_from(conn, endpoint: str, overlap_days: int = OVERLAP_DAYS) -> str:
    """Start date for an incremental run of one endpoint.

    Per endpoint rather than global, because they do not advance together: on a
    given morning `sleep` may already hold tomorrow's row while `workout` is two
    days behind. One shared watermark would skip the tail of whichever endpoint
    lags.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT max(day) FROM raw.oura_documents WHERE endpoint = %s",
            (endpoint,),
        )
        newest = cur.fetchone()[0]

    floor = dt.date.fromisoformat(DEFAULT_START)
    if newest is None:
        return floor.isoformat()
    return max(floor, newest - dt.timedelta(days=overlap_days)).isoformat()


def main():
    parser = argparse.ArgumentParser(
        description="Pull Oura data into PostgreSQL (incremental by default)."
    )
    parser.add_argument("--start", default=None,
                        help="start date YYYY-MM-DD (default: resume per endpoint)")
    parser.add_argument("--end", default=str(dt.date.today()),
                        help="end date YYYY-MM-DD")
    parser.add_argument("--full", action="store_true",
                        help=f"refetch everything from {DEFAULT_START}")
    parser.add_argument("--heartrate", action="store_true",
                        help="also fetch raw heart rate time series (high volume)")
    args = parser.parse_args()

    if args.full and args.start:
        parser.error("--full and --start are mutually exclusive")

    client = OuraClient()
    conn = psycopg2.connect(os.environ["DATABASE_URL"])

    mode = "full" if args.full else ("explicit range" if args.start else "incremental")
    print(f"mode: {mode}, through {args.end}\n")
    print(f"{'endpoint':20s} {'from':>12s} {'fetched':>8s} {'written':>8s}")

    total_fetched = total_written = 0
    for endpoint in DAILY_ENDPOINTS:
        if args.full:
            start = DEFAULT_START
        elif args.start:
            start = args.start
        else:
            start = resume_from(conn, endpoint)

        docs = list(client.fetch_all(endpoint, start, args.end))
        written = upsert(conn, endpoint, docs)
        total_fetched += len(docs)
        total_written += written
        print(f"{endpoint:20s} {start:>12s} {len(docs):8d} {written:8d}")

    if args.heartrate:
        # Heart rate uses datetimes and returns 5-min interval data.
        if args.full:
            hr_start = DEFAULT_START
        elif args.start:
            hr_start = args.start
        else:
            hr_start = resume_from(conn, "heartrate")
        docs = [
            {"id": f"hr_{d['timestamp']}", "timestamp": d["timestamp"],
             "bpm": d["bpm"], "source": d.get("source")}
            for d in client.fetch_all_heartrate(
                f"{hr_start}T00:00:00+00:00", f"{args.end}T23:59:59+00:00"
            )
        ]
        written = upsert(conn, "heartrate", docs)
        total_fetched += len(docs)
        total_written += written
        print(f"{'heartrate':20s} {hr_start:>12s} {len(docs):8d} {written:8d}")

    conn.close()
    print(f"\n{total_fetched} documents fetched, {total_written} new or revised.")
    if total_fetched and not total_written:
        print("Nothing had changed, so nothing was written.")


if __name__ == "__main__":
    main()
