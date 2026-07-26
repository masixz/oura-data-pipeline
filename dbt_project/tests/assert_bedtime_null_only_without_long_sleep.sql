-- bedtime_hours is allowed to be null, but only for the specific reason that
-- the night never consolidated into a `long_sleep` period. That is a real
-- physiological event worth keeping, not missing data.
--
-- Without this test, a future join or filter bug could start dropping bedtimes
-- on ordinary nights and the relaxed not_null on bedtime_hours would hide it.
-- Rows returned = a night where nullness and has_long_sleep disagree.

select
    day,
    has_long_sleep,
    bedtime_hours,
    sleep_score
from {{ ref('mart_sleep_daily') }}
where has_long_sleep = (bedtime_hours is null)
