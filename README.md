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

**The 2024 dip is real and physiological.** Sleep score, HRV, and night
heart rate degraded together from late 2023 and bottomed out in spring 2024:
rolling HRV sat below -1.5 sigma of its own distribution for 44 consecutive
days (bottoming at -2.6 sigma), and all three signals recovered through 2025.
Full statistics in [notebooks/01_sleep_statistics.ipynb](notebooks/01_sleep_statistics.ipynb),
including the Welch t-tests and the falsified late-bedtime hypothesis behind
the Sunday-night effect.

![Average sleep score by night of week](assets/weekday_scores.png)

**Sunday night is reliably my worst sleep** (average score 68.6 vs 73.8 for
Monday night) across four years of data. Oura assigns each sleep to the
wake-up day, so this is the classic Sunday-night effect, visible in n=173
Sunday nights rather than anecdote.

**Can tonight's sleep be predicted before bed?** Partly: a random forest on
pre-bed features (bedtime, day of week, recent history, day's activity) beats
the naive baselines by ~13% (MAE 7.9 vs 9.1) on a time-based test split.
Bedtime is the biggest controllable lever. Full modeling with baselines and
honest evaluation in
[notebooks/02_sleep_forecasting.ipynb](notebooks/02_sleep_forecasting.ipynb).

## Privacy

The code is public. The data is not.

- Raw health data never enters this repo (see `.gitignore`)
- Published analysis contains aggregated statistics and charts only
- See [PRIVACY.md](PRIVACY.md)

## Dashboard

Built in Metabase (runs in the same docker compose) on top of the dbt staging
layer:

![Metabase dashboard](assets/metabase_dashboard.png)

## Architecture

```
Oura API v2 (OAuth2) -> Python ingestion -> PostgreSQL (Docker)
                                              raw (JSONB) -> dbt staging models -> notebooks + charts
```

- `ingestion/` — OAuth2 flow + idempotent API ingestion (upsert on document id; re-runs never duplicate), covered by pytest
- `dbt_project/` — staging layer as dbt models: typed views over raw JSONB, with schema tests (unique, not_null, score ranges)
- `notebooks/` — statistics (01) and forecasting (02), executed with outputs
- `analysis/` — README chart generation (aggregates only)

```bash
make refresh   # ingest -> dbt build -> charts
make test      # pytest
```

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

# 5. Pull your data, build the staging layer
make refresh
```
