
  create view "oura"."staging"."stg_workouts__dbt_tmp"
    
    
  as (
    select
    doc_id,
    day::date                                  as day,
    payload->>'activity'                       as activity,
    payload->>'intensity'                      as intensity,
    (payload->>'calories')::numeric            as calories,
    (payload->>'start_datetime')::timestamptz  as start_at,
    (payload->>'end_datetime')::timestamptz    as end_at
from "oura"."raw"."oura_documents"
where endpoint = 'workout'
  );