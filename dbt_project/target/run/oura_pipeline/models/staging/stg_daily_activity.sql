
  create view "oura"."staging"."stg_daily_activity__dbt_tmp"
    
    
  as (
    select
    day::date                                  as day,
    (payload->>'score')::int                   as activity_score,
    (payload->>'steps')::int                   as steps,
    (payload->>'total_calories')::int          as total_calories,
    (payload->>'active_calories')::int         as active_calories,
    (payload->>'sedentary_time')::int / 3600.0 as sedentary_hours,
    (payload->>'non_wear_time')::int / 3600.0  as non_wear_hours
from "oura"."raw"."oura_documents"
where endpoint = 'daily_activity'
  );