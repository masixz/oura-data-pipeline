select
    day::date                            as day,
    payload->>'day_summary'              as day_summary,
    (payload->>'stress_high')::int / 3600.0    as stress_high_hours,
    (payload->>'recovery_high')::int / 3600.0  as recovery_high_hours
from "oura"."raw"."oura_documents"
where endpoint = 'daily_stress'