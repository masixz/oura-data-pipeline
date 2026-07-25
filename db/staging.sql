-- Staging layer: typed views over the raw JSONB documents.
-- Raw stays untouched (re-ingestable); these views are the analysis interface.

CREATE SCHEMA IF NOT EXISTS staging;

-- One row per sleep period (includes naps; type distinguishes them)
CREATE OR REPLACE VIEW staging.sleep_periods AS
SELECT
    doc_id,
    day::date                                          AS day,
    payload->>'type'                                   AS type,
    (payload->>'bedtime_start')::timestamptz           AS bedtime_start,
    (payload->>'bedtime_end')::timestamptz             AS bedtime_end,
    (payload->>'total_sleep_duration')::int / 3600.0   AS sleep_hours,
    (payload->>'time_in_bed')::int / 3600.0            AS time_in_bed_hours,
    (payload->>'efficiency')::int                      AS efficiency,
    (payload->>'latency')::int / 60.0                  AS latency_min,
    (payload->>'deep_sleep_duration')::int / 3600.0    AS deep_hours,
    (payload->>'rem_sleep_duration')::int / 3600.0     AS rem_hours,
    (payload->>'light_sleep_duration')::int / 3600.0   AS light_hours,
    (payload->>'awake_time')::int / 3600.0             AS awake_hours,
    (payload->>'average_heart_rate')::numeric          AS avg_hr,
    (payload->>'lowest_heart_rate')::int               AS lowest_hr,
    (payload->>'average_hrv')::int                     AS avg_hrv,
    (payload->>'average_breath')::numeric              AS avg_breath
FROM raw.oura_documents
WHERE endpoint = 'sleep';

-- One row per day: sleep score + contributor breakdown
CREATE OR REPLACE VIEW staging.daily_sleep AS
SELECT
    day::date                                              AS day,
    (payload->>'score')::int                               AS sleep_score,
    (payload->'contributors'->>'deep_sleep')::int          AS c_deep_sleep,
    (payload->'contributors'->>'efficiency')::int          AS c_efficiency,
    (payload->'contributors'->>'latency')::int             AS c_latency,
    (payload->'contributors'->>'rem_sleep')::int           AS c_rem_sleep,
    (payload->'contributors'->>'restfulness')::int         AS c_restfulness,
    (payload->'contributors'->>'timing')::int              AS c_timing,
    (payload->'contributors'->>'total_sleep')::int         AS c_total_sleep
FROM raw.oura_documents
WHERE endpoint = 'daily_sleep';

-- One row per day: readiness
CREATE OR REPLACE VIEW staging.daily_readiness AS
SELECT
    day::date                                                  AS day,
    (payload->>'score')::int                                   AS readiness_score,
    (payload->>'temperature_deviation')::numeric               AS temp_deviation,
    (payload->'contributors'->>'resting_heart_rate')::int      AS c_resting_hr,
    (payload->'contributors'->>'hrv_balance')::int             AS c_hrv_balance,
    (payload->'contributors'->>'recovery_index')::int          AS c_recovery_index,
    (payload->'contributors'->>'sleep_balance')::int           AS c_sleep_balance,
    (payload->'contributors'->>'activity_balance')::int        AS c_activity_balance,
    (payload->'contributors'->>'body_temperature')::int        AS c_body_temperature,
    (payload->'contributors'->>'previous_day_activity')::int   AS c_prev_day_activity,
    (payload->'contributors'->>'previous_night')::int          AS c_previous_night
FROM raw.oura_documents
WHERE endpoint = 'daily_readiness';

-- One row per day: activity
CREATE OR REPLACE VIEW staging.daily_activity AS
SELECT
    day::date                                  AS day,
    (payload->>'score')::int                   AS activity_score,
    (payload->>'steps')::int                   AS steps,
    (payload->>'total_calories')::int          AS total_calories,
    (payload->>'active_calories')::int         AS active_calories,
    (payload->>'sedentary_time')::int / 3600.0 AS sedentary_hours,
    (payload->>'non_wear_time')::int / 3600.0  AS non_wear_hours
FROM raw.oura_documents
WHERE endpoint = 'daily_activity';

-- One row per workout
CREATE OR REPLACE VIEW staging.workouts AS
SELECT
    doc_id,
    day::date                            AS day,
    payload->>'activity'                 AS activity,
    payload->>'intensity'                AS intensity,
    (payload->>'calories')::numeric      AS calories,
    (payload->>'start_datetime')::timestamptz AS start_at,
    (payload->>'end_datetime')::timestamptz   AS end_at
FROM raw.oura_documents
WHERE endpoint = 'workout';

-- Daily wide table: everything joined on day (main sleep period only)
CREATE OR REPLACE VIEW staging.daily AS
SELECT
    ds.day,
    ds.sleep_score,
    dr.readiness_score,
    da.activity_score,
    sp.sleep_hours,
    sp.efficiency,
    sp.avg_hrv,
    sp.lowest_hr,
    sp.avg_hr,
    sp.bedtime_start,
    sp.deep_hours,
    sp.rem_hours,
    dr.temp_deviation,
    da.steps
FROM staging.daily_sleep ds
LEFT JOIN staging.daily_readiness dr USING (day)
LEFT JOIN staging.daily_activity  da USING (day)
LEFT JOIN LATERAL (
    SELECT * FROM staging.sleep_periods p
    WHERE p.day = ds.day AND p.type = 'long_sleep'
    ORDER BY p.sleep_hours DESC LIMIT 1
) sp ON true;
