
  create view "oura"."staging"."stg_sleep_periods__dbt_tmp"
    
    
  as (
    select
    doc_id,
    day::date                                          as day,
    payload->>'type'                                   as type,
    (payload->>'bedtime_start')::timestamptz           as bedtime_start,
    (payload->>'bedtime_end')::timestamptz             as bedtime_end,
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
from "oura"."raw"."oura_documents"
where endpoint = 'sleep'
  );