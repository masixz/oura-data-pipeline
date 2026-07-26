-- Synthetic Oura documents for CI.
--
-- No real health data: every value here is invented. The point is to give the
-- dbt staging layer something to parse, so the schema tests assert that the
-- JSONB extraction works rather than passing vacuously against zero rows.
--
-- Covers three days across every endpoint the staging models read. 2026-01-02
-- deliberately carries two sleep periods, and the nap is made *longer* than
-- that night's long sleep. Fixtures should be adversarial rather than
-- realistic: this shape means `daily` must both filter on type and collapse to
-- one row per day, and the existing unique/not_null tests on `daily.day` fail
-- loudly if the lateral join is ever loosened into a plain join.

INSERT INTO raw.oura_documents (endpoint, doc_id, day, payload) VALUES

-- daily_sleep -------------------------------------------------------------
('daily_sleep', 'ds-2026-01-01', '2026-01-01', '{
  "score": 74, "contributors": {"deep_sleep": 80, "efficiency": 95,
  "latency": 70, "rem_sleep": 60, "restfulness": 65, "timing": 88,
  "total_sleep": 72}}'),
('daily_sleep', 'ds-2026-01-02', '2026-01-02', '{
  "score": 61, "contributors": {"deep_sleep": 55, "efficiency": 90,
  "latency": 45, "rem_sleep": 48, "restfulness": 58, "timing": 40,
  "total_sleep": 59}}'),
('daily_sleep', 'ds-2026-01-03', '2026-01-03', '{
  "score": 88, "contributors": {"deep_sleep": 92, "efficiency": 98,
  "latency": 85, "rem_sleep": 79, "restfulness": 81, "timing": 94,
  "total_sleep": 90}}'),

-- daily_readiness ---------------------------------------------------------
('daily_readiness', 'dr-2026-01-01', '2026-01-01', '{
  "score": 70, "temperature_deviation": -0.1, "contributors": {
  "resting_heart_rate": 82, "hrv_balance": 68, "recovery_index": 74,
  "sleep_balance": 71, "activity_balance": 66, "body_temperature": 90,
  "previous_day_activity": 60, "previous_night": 73}}'),
('daily_readiness', 'dr-2026-01-02', '2026-01-02', '{
  "score": 58, "temperature_deviation": 0.7, "contributors": {
  "resting_heart_rate": 61, "hrv_balance": 49, "recovery_index": 52,
  "sleep_balance": 60, "activity_balance": 71, "body_temperature": 55,
  "previous_day_activity": 64, "previous_night": 57}}'),
('daily_readiness', 'dr-2026-01-03', '2026-01-03', '{
  "score": 85, "temperature_deviation": 0.0, "contributors": {
  "resting_heart_rate": 90, "hrv_balance": 83, "recovery_index": 88,
  "sleep_balance": 86, "activity_balance": 79, "body_temperature": 92,
  "previous_day_activity": 70, "previous_night": 87}}'),

-- daily_activity ----------------------------------------------------------
('daily_activity', 'da-2026-01-01', '2026-01-01', '{
  "score": 82, "steps": 9500, "total_calories": 2600, "active_calories": 520,
  "sedentary_time": 28800, "non_wear_time": 1800}'),
('daily_activity', 'da-2026-01-02', '2026-01-02', '{
  "score": 64, "steps": 4200, "total_calories": 2250, "active_calories": 210,
  "sedentary_time": 43200, "non_wear_time": 3600}'),
('daily_activity', 'da-2026-01-03', '2026-01-03', '{
  "score": 91, "steps": 14300, "total_calories": 2950, "active_calories": 810,
  "sedentary_time": 21600, "non_wear_time": 0}'),

-- daily_stress ------------------------------------------------------------
('daily_stress', 'st-2026-01-01', '2026-01-01', '{
  "day_summary": "normal", "stress_high": 7200, "recovery_high": 10800}'),
('daily_stress', 'st-2026-01-02', '2026-01-02', '{
  "day_summary": "stressful", "stress_high": 18000, "recovery_high": 3600}'),
('daily_stress', 'st-2026-01-03', '2026-01-03', '{
  "day_summary": "restored", "stress_high": 3600, "recovery_high": 21600}'),

-- sleep periods -----------------------------------------------------------
-- On 2026-01-02 the night is short (5.25 h) and the nap is longer (6 h), so
-- ordering by duration alone would pick the wrong row.
('sleep', 'sp-2026-01-01-long', '2026-01-01', '{
  "type": "long_sleep", "bedtime_start": "2025-12-31T23:10:00+02:00",
  "bedtime_end": "2026-01-01T07:05:00+02:00", "total_sleep_duration": 25500,
  "time_in_bed": 28500, "efficiency": 91, "latency": 900,
  "deep_sleep_duration": 5400, "rem_sleep_duration": 4500,
  "light_sleep_duration": 15600, "awake_time": 3000,
  "average_heart_rate": 54.5, "lowest_heart_rate": 48,
  "average_hrv": 62, "average_breath": 14.2}'),
('sleep', 'sp-2026-01-02-long', '2026-01-02', '{
  "type": "long_sleep", "bedtime_start": "2026-01-02T01:40:00+02:00",
  "bedtime_end": "2026-01-02T07:20:00+02:00", "total_sleep_duration": 18900,
  "time_in_bed": 20400, "efficiency": 84, "latency": 1500,
  "deep_sleep_duration": 3300, "rem_sleep_duration": 2700,
  "light_sleep_duration": 12900, "awake_time": 1500,
  "average_heart_rate": 61.2, "lowest_heart_rate": 56,
  "average_hrv": 41, "average_breath": 15.1}'),
('sleep', 'sp-2026-01-02-nap', '2026-01-02', '{
  "type": "late_nap", "bedtime_start": "2026-01-02T13:00:00+02:00",
  "bedtime_end": "2026-01-02T19:30:00+02:00", "total_sleep_duration": 21600,
  "time_in_bed": 23400, "efficiency": 88, "latency": 300,
  "deep_sleep_duration": 3600, "rem_sleep_duration": 2400,
  "light_sleep_duration": 15600, "awake_time": 1800,
  "average_heart_rate": 63.0, "lowest_heart_rate": 59,
  "average_hrv": 38, "average_breath": 15.6}'),
('sleep', 'sp-2026-01-03-long', '2026-01-03', '{
  "type": "long_sleep", "bedtime_start": "2026-01-02T22:30:00+02:00",
  "bedtime_end": "2026-01-03T07:00:00+02:00", "total_sleep_duration": 29100,
  "time_in_bed": 30600, "efficiency": 96, "latency": 600,
  "deep_sleep_duration": 6600, "rem_sleep_duration": 6000,
  "light_sleep_duration": 16500, "awake_time": 1500,
  "average_heart_rate": 51.8, "lowest_heart_rate": 46,
  "average_hrv": 78, "average_breath": 13.7}'),

-- workouts ----------------------------------------------------------------
('workout', 'wk-2026-01-01-a', '2026-01-01', '{
  "activity": "walking", "intensity": "easy", "calories": 180,
  "start_datetime": "2026-01-01T17:00:00+02:00",
  "end_datetime": "2026-01-01T18:00:00+02:00"}'),
('workout', 'wk-2026-01-03-a', '2026-01-03', '{
  "activity": "strength_training", "intensity": "hard", "calories": 420,
  "start_datetime": "2026-01-03T18:15:00+02:00",
  "end_datetime": "2026-01-03T19:30:00+02:00"}')

ON CONFLICT (endpoint, doc_id) DO UPDATE
    SET payload = EXCLUDED.payload, ingested_at = now();
