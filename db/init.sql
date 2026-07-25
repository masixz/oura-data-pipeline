-- Raw layer: one table per Oura API endpoint, payload kept as JSONB.
-- Idempotent ingestion: primary key on the Oura document id,
-- re-running an ingest upserts instead of duplicating.

CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.oura_documents (
    endpoint     TEXT        NOT NULL,
    doc_id       TEXT        NOT NULL,
    day          DATE,
    payload      JSONB       NOT NULL,
    ingested_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (endpoint, doc_id)
);

CREATE INDEX IF NOT EXISTS idx_oura_documents_endpoint_day
    ON raw.oura_documents (endpoint, day);
