"""Tests for the ingestion layer.

Run: .venv/bin/pytest
The idempotency test needs the dockerized Postgres up (docker compose up -d).
"""

import json
import os

import psycopg2
import pytest
from dotenv import load_dotenv

from ingestion.client import OuraClient
from ingestion.ingest import DEFAULT_START, doc_day, resume_from, upsert

load_dotenv()


# --- doc_day: day extraction from heterogeneous documents ---------------

def test_doc_day_prefers_day_field():
    assert doc_day({"day": "2026-01-15", "timestamp": "2026-01-16T08:00:00"}) == "2026-01-15"


def test_doc_day_falls_back_to_timestamp():
    assert doc_day({"timestamp": "2026-01-16T08:00:00+00:00"}) == "2026-01-16"


def test_doc_day_handles_missing_everything():
    assert doc_day({"id": "x"}) is None


# --- pagination: fetch_all must follow next_token to the end ------------

def test_fetch_all_follows_pagination(monkeypatch):
    pages = [
        {"data": [{"id": "a"}, {"id": "b"}], "next_token": "t1"},
        {"data": [{"id": "c"}], "next_token": None},
    ]
    calls = []

    def fake_get(self, url, params):
        calls.append(dict(params))
        return pages[len(calls) - 1]

    monkeypatch.setattr(OuraClient, "__init__", lambda self: None)
    monkeypatch.setattr(OuraClient, "_get", fake_get)

    docs = list(OuraClient().fetch_all("daily_sleep", "2026-01-01", "2026-01-31"))
    assert [d["id"] for d in docs] == ["a", "b", "c"]
    assert "next_token" not in calls[0]
    assert calls[1]["next_token"] == "t1"


# --- idempotency: re-ingesting must not duplicate ------------------------

@pytest.fixture
def pg():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    yield conn
    with conn.cursor() as cur:
        cur.execute("DELETE FROM raw.oura_documents WHERE endpoint = '_test'")
    conn.commit()
    conn.close()


def test_upsert_is_idempotent(pg):
    docs = [{"id": "t1", "day": "2026-01-01", "score": 80},
            {"id": "t2", "day": "2026-01-02", "score": 90}]
    upsert(pg, "_test", docs)
    upsert(pg, "_test", docs)  # same docs again

    with pg.cursor() as cur:
        cur.execute("SELECT count(*) FROM raw.oura_documents WHERE endpoint = '_test'")
        assert cur.fetchone()[0] == 2


def test_upsert_updates_payload_on_conflict(pg):
    upsert(pg, "_test", [{"id": "t1", "day": "2026-01-01", "score": 80}])
    upsert(pg, "_test", [{"id": "t1", "day": "2026-01-01", "score": 85}])

    with pg.cursor() as cur:
        cur.execute("SELECT payload FROM raw.oura_documents WHERE endpoint = '_test'")
        rows = cur.fetchall()
    assert len(rows) == 1
    payload = rows[0][0] if isinstance(rows[0][0], dict) else json.loads(rows[0][0])
    assert payload["score"] == 85


# --- conditional upsert: unchanged payloads must not be rewritten -------
# ingested_at is what dbt source freshness reads, so it has to mean "this
# document changed", not "the job ran again".

def ingested_at(conn, doc_id="t1"):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT ingested_at FROM raw.oura_documents "
            "WHERE endpoint = '_test' AND doc_id = %s", (doc_id,))
        return cur.fetchone()[0]


def test_upsert_reports_rows_actually_written(pg):
    docs = [{"id": "t1", "day": "2026-01-01", "score": 80},
            {"id": "t2", "day": "2026-01-02", "score": 90}]
    assert upsert(pg, "_test", docs) == 2
    assert upsert(pg, "_test", docs) == 0  # nothing changed, nothing written


def test_upsert_leaves_ingested_at_alone_when_nothing_changed(pg):
    doc = [{"id": "t1", "day": "2026-01-01", "score": 80}]
    upsert(pg, "_test", doc)
    before = ingested_at(pg)
    upsert(pg, "_test", doc)
    assert ingested_at(pg) == before


def test_upsert_bumps_ingested_at_when_the_payload_changes(pg):
    upsert(pg, "_test", [{"id": "t1", "day": "2026-01-01", "score": 80}])
    before = ingested_at(pg)
    assert upsert(pg, "_test", [{"id": "t1", "day": "2026-01-01", "score": 85}]) == 1
    assert ingested_at(pg) > before


def test_upsert_counts_only_the_changed_document_in_a_mixed_batch(pg):
    docs = [{"id": "t1", "day": "2026-01-01", "score": 80},
            {"id": "t2", "day": "2026-01-02", "score": 90}]
    upsert(pg, "_test", docs)
    docs[1] = {"id": "t2", "day": "2026-01-02", "score": 91}
    assert upsert(pg, "_test", docs) == 1


# --- incremental watermark ----------------------------------------------

def test_resume_from_falls_back_to_default_when_endpoint_is_empty(pg):
    assert resume_from(pg, "_test_never_seen") == DEFAULT_START


def test_resume_from_rewinds_by_the_overlap_window(pg):
    upsert(pg, "_test", [{"id": "t1", "day": "2026-03-20", "score": 70}])
    assert resume_from(pg, "_test", overlap_days=10) == "2026-03-10"


def test_resume_from_uses_the_newest_day_not_the_first(pg):
    upsert(pg, "_test", [{"id": "t1", "day": "2026-03-01", "score": 70},
                         {"id": "t2", "day": "2026-03-20", "score": 75}])
    assert resume_from(pg, "_test", overlap_days=5) == "2026-03-15"


def test_resume_from_never_goes_earlier_than_the_default_start(pg):
    upsert(pg, "_test", [{"id": "t1", "day": "2022-01-03", "score": 70}])
    assert resume_from(pg, "_test", overlap_days=365) == DEFAULT_START


def test_resume_from_is_per_endpoint(pg):
    # Endpoints do not advance together, so one shared watermark would skip
    # the tail of whichever endpoint lags behind.
    upsert(pg, "_test", [{"id": "t1", "day": "2026-03-20", "score": 70}])
    assert resume_from(pg, "_test", overlap_days=0) == "2026-03-20"
    assert resume_from(pg, "_test_other", overlap_days=0) == DEFAULT_START
