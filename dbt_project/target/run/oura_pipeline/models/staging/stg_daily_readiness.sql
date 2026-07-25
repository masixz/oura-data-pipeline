
  create view "oura"."staging"."stg_daily_readiness__dbt_tmp"
    
    
  as (
    select
    day::date                                                  as day,
    (payload->>'score')::int                                   as readiness_score,
    (payload->>'temperature_deviation')::numeric               as temp_deviation,
    (payload->'contributors'->>'resting_heart_rate')::int      as c_resting_hr,
    (payload->'contributors'->>'hrv_balance')::int             as c_hrv_balance,
    (payload->'contributors'->>'recovery_index')::int          as c_recovery_index,
    (payload->'contributors'->>'sleep_balance')::int           as c_sleep_balance,
    (payload->'contributors'->>'activity_balance')::int        as c_activity_balance,
    (payload->'contributors'->>'body_temperature')::int        as c_body_temperature,
    (payload->'contributors'->>'previous_day_activity')::int   as c_prev_day_activity,
    (payload->'contributors'->>'previous_night')::int          as c_previous_night
from "oura"."raw"."oura_documents"
where endpoint = 'daily_readiness'
  );