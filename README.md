# Oura Data Pipeline

[![CI](https://github.com/masixz/oura-data-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/masixz/oura-data-pipeline/actions/workflows/ci.yml)

Four years of my own Oura Ring data: pulled through the Oura API v2 (OAuth2),
loaded into PostgreSQL, analyzed with SQL and Python.

**1,244 nights. 2,238 sleep periods. 1,106 workouts.**

## Why

I have worn an Oura ring daily since 2022 and check the stats every morning.
This project turns that habit into a data pipeline: my own sleep, readiness,
activity, heart rate, and stress data, end to end.

## The headline finding

![Every hour of later bedtime costs about 2 sleep points, and timing beats consistency](assets/bedtime_cost.png)

I first assumed bedtime *consistency* was what mattered. It is not, and the
reason is worth more than the headline: consistency looks like it matters
(r = -0.23 across 176 weeks, p = 0.002) purely because I go to bed both later
*and* more erratically, and those two move together (r = +0.47). Hold timing
fixed and consistency drops to **r = +0.03** (p = 0.73), nothing. Hold
consistency fixed and timing survives almost untouched at **r = -0.49**
(p = 4e-12). Timing carries the entire effect.

Every hour later costs about **2 sleep-score points** (r = -0.38 across 1,237
nights, 2.6 points per hour when weeks are averaged). Nights starting before
23:00 average 78.4 and nights starting at 03:00 or later average 63.5, a gap of
14.9 points, which is what losing three hours of sleep does to the score.
My median bedtime is 02:50, so this is not a hypothetical.

Reproduce it with `make charts`; the analysis lives in `analysis/charts.py`.

## Findings so far

![Sleep score, HRV and lowest heart rate, monthly](assets/three_signals.png)

**The 2024 dip is real and physiological.** Sleep score, HRV, and night
heart rate degraded together from late 2023 and bottomed out in spring 2024,
with large effects winter on winter: HRV -10 ms (d = 0.87), night heart rate
+4.6 bpm (d = 1.02), sleep score -9.4 points (d = 0.84). All three recovered
through 2025. Rolling HRV stayed below -1.5 sigma of its own distribution from
10 April to 3 June, bottoming at -2.6 sigma; that 44-day span says how long
the excursion lasted, not how strong the evidence is.
Full statistics in [notebooks/01_sleep_statistics.ipynb](notebooks/01_sleep_statistics.ipynb),
including the Welch t-tests and the falsified late-bedtime hypothesis behind
the Sunday-night effect.

![Average sleep score by night of week](assets/weekday_scores.png)

**Sunday night is reliably my worst sleep** (average score 68.6 vs 73.8 for
Monday night) across four years of data. Oura assigns each sleep to the
wake-up day, so this is the classic Sunday-night effect, visible in n=173
Sunday nights rather than anecdote. Tested by permuting days inside each week,
which keeps seasonal drift out of the comparison: 3.4 points below the week
average, p = 0.0007, 95% CI 1.3 to 5.5 points.

**Why is my REM low? Not for the reasons I assumed.** Nine hypotheses tested
in assumption -> check -> visualisation format
([notebooks/03_rem_investigation.ipynb](notebooks/03_rem_investigation.ipynb)):
stress, workouts, and late bedtimes all came back clean, and at ~1,000 nights
each those nulls are strong enough to rule out anything above r = 0.09. The
only strong lever is duration (r = 0.80, ~15 min REM per extra hour of
sleep), with the morning end carrying a disproportionate REM share. My REM
is not damaged - it is starved of an 8th hour of sleep.

**Two findings did not survive their own robustness check.** A multi-year REM
decline and a weekend REM effect were both reported as significant on
p-values that assumed independent nights. Re-tested properly, the REM decline
is better explained as a measurement step change at an Oura algorithm update,
and the weekend effect is inconclusive. Both are withdrawn, with the working
shown in
[notebooks/04_statistical_robustness.ipynb](notebooks/04_statistical_robustness.ipynb):
effect sizes, autocorrelation-aware p-values, minimum detectable effects for
every null, and a Benjamini-Hochberg pass over the whole inventory.

**One bug worth documenting, because it hit the headline.** Every bedtime here
was originally read in UTC. Postgres normalises a `timestamptz` to UTC, so
taking the hour off it answers "what time was it in London" rather than "what
time did I go to bed" - two hours out in winter, three in summer, plus a fake
seasonal swing each time DST shifted. `stg_sleep_periods` now also exposes
`bedtime_start_local`, read from the offset Oura itself recorded so nights
abroad are handled correctly, and a dbt test fails loudly if that timestamp
format ever changes. Fixing it made the headline stronger (timing r = -0.42 to
-0.53) and improved the forecast, since its most important feature had been
scrambled the whole time.

**Can tonight's sleep be predicted before bed?** Partly: a ridge regression on
pre-bed features (bedtime, day of week, recent history, day's activity) beats
the naive baselines by 16% (MAE 7.64 vs 9.13) on a time-based test split, with
a random forest slightly behind at 7.76. The linear model winning is the right
kind of boring: with a correctly specified bedtime feature there is no
curvature left for the trees to find. Bedtime is the biggest controllable lever
by a wide margin, -4.3 points per standard deviation later. Full modeling with
baselines and honest evaluation in
[notebooks/02_sleep_forecasting.ipynb](notebooks/02_sleep_forecasting.ipynb).

## What this data cannot tell you

Everything above is one person's ring, so the honest framing is a case study
rather than a result. The specific limits are worth naming, because most of them
bound a claim I actually made.

**n = 1.** Nothing here generalises. Duration dominating my sleep score is a
fact about me. The method transfers; the numbers do not.

**Observational, so no causal claims.** I never randomised a bedtime. Every
correlation here is compatible with reverse causation or a common cause: a
stressful week can produce both a late bedtime and a bad night, and this design
cannot separate that from bedtime causing the bad night. The one natural
experiment in the data, the 2024 dip, is confounded by everything else that was
happening in my life at the time, which is precisely the thing I have no data
on.

**86.8% coverage, and it is thinnest where it matters most.** 1,244 nights
across 1,433 calendar days, with 15 gaps longer than three days including two
of roughly four weeks. Coverage is not uniform: the baseline winter used for the
dip comparison is 91.4% complete, the dip winter only 84.2%, and the 44-day HRV
trough itself 80%. All of 2024 sits at 81.4% against 91.5% for 2025. If I
stopped wearing the ring during bad stretches, the dip is understated; if I
stopped during travel and good stretches, it is overstated. The nights right
after a long gap do score lower (68.2 against 71.5), but with only 15 such
nights that comparison proves nothing either way (d = -0.27, p = 0.40). So the
direction of the bias is unknown and its size is unquantified. The dip's effect
sizes are large enough (d = 0.84 to 1.02) that this is unlikely to have invented
it, and small enough gaps that I would not defend the exact magnitude.

**A consumer wearable is not a sleep lab.** Oura's stage classification agrees
with polysomnography roughly 70% of the time epoch by epoch, so REM and deep
figures are useful as trends and unreliable as absolute values. Worse, the
staging algorithm changed inside my dataset: REM share steps from 20.1% before
November 2023 to 17.2% after January 2024 (d = 0.62), which is why the
multi-year REM decline was withdrawn. Any comparison spanning that boundary is
partly measuring a software update.

**The most explanatory variables were never recorded.** No alcohol, caffeine,
late meals, work stress, or illness logs, because I did not keep them. Oura's
own stress metric only starts 2023-09-12, so the stress hypothesis rests on 935
of 1,244 nights and says nothing about the first year. Illness is proxied by
body-temperature deviation, which crosses 0.5 C on 32 days and 1.0 C on 2, so
that hypothesis was withdrawn as untestable rather than reported as negative.
The `session` endpoint is ingested and contains 2 documents. Absence of these
variables is the single largest reason the forecast plateaus at MAE 7.64.

**Nights are not independent observations, which most statistics assume.** HRV
carries about 48 independent observations across 1,237 nights, REM share about
70. Every claim above is re-tested against that in notebook 04, and two did not
survive. Any p-value in this repo that is not from notebook 04 should be read as
optimistic.

**The analysis was not pre-registered.** I chose windows, thresholds and
transformations after seeing the data. Benjamini-Hochberg across the 15 headline
tests controls for the comparisons I ran and reported; it cannot control for the
ones I tried and abandoned. The falsified hypotheses are written up precisely so
that this is auditable rather than hidden.

**Measuring myself changes me.** I check these numbers every morning, so my
behaviour responds to them. The bedtime finding in particular is contaminated by
the fact that I now know about the bedtime finding.

**Only the daily long sleep is analysed.** `daily` keeps one sleep period per
day, so 789 short `sleep` fragments, 126 `rest` periods and 57 naps are outside
every result here. Fragmented nights are invisible in the wide table.

**Seven nights never consolidated into sleep at all, and they are the worst
seven.** They carry a sleep score but no `long_sleep` period, only short
fragments and rest, so bedtime and duration are null on them. Scores run 24 to
50 against a 71 average. Any analysis that drops nulls therefore discards the
seven worst nights on record without mentioning it, which means every bedtime
result here is estimated on a sample with the extremes trimmed off one end. The
direction of that bias depends on what time I went to bed on those nights, which
is exactly what was not recorded. `mart_sleep_daily` keeps them with
`has_long_sleep = false` so the exclusion has to be deliberate from now on.

**`intensity` on workouts is unusable and calories are a third missing.** 1,082
of 1,106 workouts are tagged "moderate", 21 "easy" and 3 "hard", so intensity
carries no signal. Calories are null on 407 workouts, mostly walks. Training
load is therefore measured in minutes, which is complete on every row. An
earlier version of `mart_workout_recovery` ranked load by calories with
`ntile(4) over (order by total_calories)`, which sorts nulls last in Postgres and
so labelled a quartile of missing data as the heaviest training.

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

- `ingestion/` — OAuth2 flow plus incremental API ingestion, covered by pytest. Each endpoint resumes from the newest day it already holds minus a 10-day overlap, so a daily run fetches about 11 days instead of 1,433. The overlap exists because Oura revises recent days as sleep staging finalises, and a strict high-water mark would freeze the first version of every recent night. The watermark is per endpoint rather than global: `session` last produced data in July 2025, so one shared watermark would never look for it again. The upsert is conditional, so a document whose payload has not changed is not rewritten, which means `ingested_at` records when a document last *changed* and `dbt source freshness` reports whether data is actually arriving rather than whether the job ran
- `dbt_project/` — two layers. **Staging**: typed views over the raw JSONB, one per endpoint, with schema tests. **Marts**: three tables at the grains the questions are actually asked at, with the feature logic the notebooks used to duplicate in pandas. 46 tests across both, plus `dbt_utils`
  - `mart_sleep_daily`, one row per night: lags, trailing windows, within-week deviations, bedtime in local hours, coverage flags
  - `mart_sleep_weekly`, one row per week: timing and consistency side by side, week-over-week deltas, quartiles, and a gaps-and-islands grouping that turns "a bad spell" into a queryable object. The longest run below my own average is 17 consecutive weeks, starting three months before the window notebook 01 tested
  - `mart_workout_recovery`, one row per training day joined to the night after it and to that night's own trailing baseline. 1,106 workouts that were previously sitting unused
- `notebooks/` — statistics (01), forecasting (02), REM investigation (03) and robustness testing (04), executed with outputs
- `analysis/` — README chart generation plus `statistics.py`, the inference helpers behind notebook 04 (effective sample size, block bootstrap, within-week contrasts, FDR)
- `.github/workflows/ci.yml` — every push to main and every pull request runs the test suite and `dbt build` against a Postgres service container, seeded with synthetic fixtures in `tests/fixtures/` so the schema tests check the JSONB extraction instead of passing against an empty table

```bash
make refresh     # ingest -> dbt deps + build -> charts
make test        # pytest
make freshness   # warn if no new or revised data in 36h
make backfill    # refetch the whole history from scratch
```

**Why the marts are not incremental**, since it is the obvious next question:
not volume, but correctness. Every mart holds at least one unbounded window
function, `percent_rank` over all nights, `ntile` over all workouts, `avg() over
()` for the all-time mean, and the `row_number` pair behind the spell grouping.
An incremental run sees only its lookback slice, so those would be computed
against the last N days and written into a column labelled all-time. That fails
silently. A lookback rescues trailing 7- and 28-day aggregates; it cannot rescue
a global ranking. Doing it properly means separating the bounded features from
the global ones first, and at 1,244 rows a full refresh takes 0.14s. The
ingestion is incremental, which is where the cost actually was.

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
