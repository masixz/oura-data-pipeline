select
    doc_id,
    day::date                                          as day,
    payload->>'type'                                   as type,
    (payload->>'bedtime_start')::timestamptz           as bedtime_start,
    (payload->>'bedtime_end')::timestamptz             as bedtime_end,
    -- Wall-clock time as the ring recorded it. Casting to timestamptz
    -- normalises to UTC, so reading the hour off it answers "what time was it
    -- in London", not "what time did I go to bed". Helsinki runs UTC+2 or +3
    -- depending on DST, which would also inject a fake 1-hour seasonal swing.
    -- Oura embeds the offset that was actually in force, including abroad, so
    -- the leading 19 characters are the local clock and are what circadian
    -- questions need. Format is asserted by assert_bedtime_format.
    (left(payload->>'bedtime_start', 19))::timestamp   as bedtime_start_local,
    (left(payload->>'bedtime_end', 19))::timestamp     as bedtime_end_local,
    right(payload->>'bedtime_start', 6)                as tz_offset,
    (payload->>'total_sleep_duration')::int / 3600.0   as sleep_hours,
    (payload->>'time_in_bed')::int / 3600.0            as time_in_bed_hours,
    (payload->>'efficiency')::int                      as efficiency,
    (payload->>'latency')::int / 60.0                  as latency_min,
    (payload->>'deep_sleep_duration')::int / 3600.0    as deep_hours,
    (payload->>'rem_sleep_duration')::int / 3600.0     as rem_hours,
    (payload->>'light_sleep_duration')::int / 3600.0   as light_hours,
    (payload->>'awake_time')::int / 3600.0             as awake_hours,
    (payload->>'average_heart_rate')::numeric          as avg_hr,
    (payload->>'lowest_heart_rate')::int               as lowest_hr,
    (payload->>'average_hrv')::int                     as avg_hrv,
    (payload->>'average_breath')::numeric              as avg_breath
from {{ source('raw', 'oura_documents') }}
where endpoint = 'sleep'
