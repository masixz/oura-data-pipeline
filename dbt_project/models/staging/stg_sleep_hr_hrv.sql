{{ config(materialized='table') }}

-- Heart rate and HRV sampled every 5 minutes through each night.
--
-- The rest of this project analyses one summary row per night. This is the
-- layer underneath: 141,120 heart-rate samples and the same number of HRV
-- samples, sitting in the raw payload since the first ingest and unused until
-- now. Oura does not expose the raw PPG waveform or accelerometer axes through
-- the public API, so this is as close to the sensor as the API allows.
--
-- Materialized as a table, unlike the rest of staging, because unnesting a JSON
-- array into 141k rows on every read is waste. The default stays `view` for
-- thin casts; this earns the exception.
--
-- Both series share one start timestamp and one interval, verified across all
-- 1,266 nights, so sample i of each lines up. Nulls appear where the ring lost
-- contact and are kept rather than dropped: a gap is information about wear.

with sleeps as (

    select
        doc_id,
        day::date                                                as day,
        -- Local wall clock, same positional parse as bedtime_start_local.
        -- Casting to timestamptz would normalise to UTC and put every night on
        -- the wrong clock, which is a bug this project already paid for once.
        (left(payload->'heart_rate'->>'timestamp', 19))::timestamp as series_start,
        (payload->'heart_rate'->>'interval')::numeric             as interval_seconds,
        payload->'heart_rate'->'items'                            as hr_items,
        payload->'hrv'->'items'                                   as hrv_items,
        jsonb_array_length(payload->'heart_rate'->'items')        as n_samples
    from {{ source('raw', 'oura_documents') }}
    where endpoint = 'sleep'
      and payload->>'type' = 'long_sleep'
      and payload->'heart_rate' ? 'items'
      and payload->'hrv' ? 'items'

)

select
    s.doc_id,
    s.day,
    g.i                                                          as sample_index,
    s.series_start
        + ((g.i - 1) * s.interval_seconds) * interval '1 second'  as sample_time_local,
    ((g.i - 1) * s.interval_seconds / 60.0)                      as minutes_into_sleep,
    (s.hr_items ->> (g.i - 1))::numeric                          as heart_rate,
    (s.hrv_items ->> (g.i - 1))::numeric                         as hrv,
    s.n_samples
from sleeps s
cross join lateral generate_series(1, s.n_samples) as g(i)
