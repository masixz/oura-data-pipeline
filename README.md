# Oura Data Pipeline

Four years of my own Oura Ring data: pulled through the Oura API v2 (OAuth2),
loaded into PostgreSQL, analyzed with SQL and Python.

**1,244 nights. 2,238 sleep periods. 1,106 workouts.**

## Why

I have worn an Oura ring daily since 2022 and check the stats every morning.
This project turns that habit into a data pipeline: my own sleep, readiness,
activity, heart rate, and stress data, end to end.

## Findings so far

![Sleep score, HRV and lowest heart rate, monthly](assets/three_signals.png)

**The winter 2023-24 dip is real and physiological.** Sleep score, HRV, and
night heart rate all degraded together and bottomed out around February-March
2024: average HRV fell from the high 60s (spring 2023) to ~33 ms, and average
lowest night heart rate peaked at ~62 bpm. All three signals recovered through
2025. Three independent metrics telling the same story is what separates a
real change from score noise.

![Average sleep score by night of week](assets/weekday_scores.png)

**Sunday night is reliably my worst sleep** (average score 68.6 vs 73.8 for
Monday night) across four years of data. Oura assigns each sleep to the
wake-up day, so this is the classic Sunday-night effect, visible in n=173
Sunday nights rather than anecdote.

More analysis in `analysis/` as this develops.

## Privacy

The code is public. The data is not.

- Raw health data never enters this repo (see `.gitignore`)
- Published analysis contains aggregated statistics and charts only
- See [PRIVACY.md](PRIVACY.md)

## Architecture

```
Oura API v2 (OAuth2) -> Python ingestion -> PostgreSQL (Docker)
                                              raw (JSONB) -> staging views -> analysis charts
```

- `ingestion/` — OAuth2 flow + idempotent API ingestion (upsert on document id; re-runs never duplicate)
- `db/` — schema and staging layer: typed SQL views over raw JSONB
- `analysis/` — chart generation from the staging layer (aggregates only)

## Setup

```bash
# 1. Start the database
docker compose up -d

# 2. Python environment
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. Credentials: copy the template, fill in your Oura OAuth app values
cp .env.example .env

# 4. One-time OAuth authorization (opens your browser)
python -m ingestion.auth

# 5. Pull your data
python -m ingestion.ingest --start 2022-01-01
```
