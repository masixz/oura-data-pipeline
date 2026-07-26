{{ config(materialized='table') }}

-- Sleep stage and movement, one reading every 30 seconds, 1.4 million of each.
--
-- Oura ships both as a run-length string of digits rather than an array: one
-- character per 30-second epoch. `sleep_phase_30_sec` is the hypnogram, the
-- thing a sleep lab draws, at the finest resolution the API offers.
--
-- Codes are Oura's, and both fields were checked against the full dataset to
-- confirm only 1 to 4 ever appear:
--   phase     1 deep, 2 light, 3 REM, 4 awake
--   movement  1 no motion, 2 restless, 3 tossing and turning, 4 active
--
-- Table rather than view for the same reason as stg_sleep_hr_hrv: 1.4 million
-- substring operations per read is not something to repeat.
--
-- The two strings are the same length on 1,261 of 1,266 nights and differ by
-- one character on the other 5. Indexing past the end of a string returns empty
-- in Postgres rather than erroring, so `nullif(..., '')` turns that into a null
-- instead of a silent zero. The phase string sets the row count because the
-- hypnogram is the point; movement is along for the ride.

with sleeps as (

    select
        doc_id,
        day::date                                                 as day,
        (left(payload->'heart_rate'->>'timestamp', 19))::timestamp as series_start,
        payload->>'sleep_phase_30_sec'                            as phase_string,
        payload->>'movement_30_sec'                               as movement_string,
        length(payload->>'sleep_phase_30_sec')                    as n_epochs
    from {{ source('raw', 'oura_documents') }}
    where endpoint = 'sleep'
      and payload->>'type' = 'long_sleep'
      and payload->>'sleep_phase_30_sec' is not null
      and payload->'heart_rate' ? 'timestamp'

)

select
    s.doc_id,
    s.day,
    g.i                                                           as epoch_index,
    s.series_start + ((g.i - 1) * 30) * interval '1 second'       as epoch_time_local,
    ((g.i - 1) * 0.5)                                             as minutes_into_sleep,

    substr(s.phase_string, g.i, 1)::int                           as phase_code,
    case substr(s.phase_string, g.i, 1)
        when '1' then 'deep'
        when '2' then 'light'
        when '3' then 'rem'
        when '4' then 'awake'
    end                                                           as sleep_phase,

    nullif(substr(s.movement_string, g.i, 1), '')::int            as movement_code,
    case nullif(substr(s.movement_string, g.i, 1), '')
        when '1' then 'still'
        when '2' then 'restless'
        when '3' then 'tossing'
        when '4' then 'active'
    end                                                           as movement,

    s.n_epochs
from sleeps s
cross join lateral generate_series(1, s.n_epochs) as g(i)
