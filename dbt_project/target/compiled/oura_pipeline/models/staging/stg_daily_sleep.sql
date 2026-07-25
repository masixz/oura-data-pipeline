select
    day::date                                          as day,
    (payload->>'score')::int                           as sleep_score,
    (payload->'contributors'->>'deep_sleep')::int      as c_deep_sleep,
    (payload->'contributors'->>'efficiency')::int      as c_efficiency,
    (payload->'contributors'->>'latency')::int         as c_latency,
    (payload->'contributors'->>'rem_sleep')::int       as c_rem_sleep,
    (payload->'contributors'->>'restfulness')::int     as c_restfulness,
    (payload->'contributors'->>'timing')::int          as c_timing,
    (payload->'contributors'->>'total_sleep')::int     as c_total_sleep
from "oura"."raw"."oura_documents"
where endpoint = 'daily_sleep'