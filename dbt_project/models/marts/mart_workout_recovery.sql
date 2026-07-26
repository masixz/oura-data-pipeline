-- Does training cost me the following night?
--
-- 1,106 workouts sat in the raw layer unused. This joins each training day to
-- the night that followed it and to my own trailing baseline, so the question
-- becomes "was that night worse than my usual week" rather than "was that night
-- below average", which would mostly measure whatever else was happening.
--
-- Grain: one row per workout day. Note the offset. Oura files a night under its
-- wake-up day, so the night after training on the 5th is the row dated the 6th.
--
-- Two data-quality decisions, both forced by what Oura actually records:
--
-- * Load is measured in minutes, not calories. Calories are null on 407 of
--   1,106 workouts (mostly walks), and an earlier version of this model ranked
--   load with `ntile(4) over (order by total_calories)`, which sorts nulls last
--   in Postgres and so quietly labelled missing data as the heaviest quartile.
--   Duration is complete on every row. Calories are still exposed, next to a
--   flag saying when they are missing.
-- * `intensity` is not usable as a signal: 1,082 of 1,106 workouts are tagged
--   "moderate", 21 "easy" and 3 "hard". It is passed through for reference and
--   should not be modelled on.

with workout_days as (

    select
        day                                                     as workout_day,
        count(*)                                                as workouts,
        sum(extract(epoch from (end_at - start_at)) / 60.0)      as total_workout_minutes,
        max(extract(epoch from (end_at - start_at)) / 60.0)      as longest_workout_minutes,
        sum(calories)                                           as total_calories,
        count(*) filter (where calories is null)                 as workouts_missing_calories,
        string_agg(distinct activity,  ', ' order by activity)   as activities,
        string_agg(distinct intensity, ', ' order by intensity)  as intensities,
        max(end_at)                                             as last_workout_end
    from {{ ref('stg_workouts') }}
    where day is not null
      and start_at is not null
      and end_at is not null
    group by day

),

joined as (

    select
        w.workout_day,
        w.workouts,
        w.total_workout_minutes,
        w.longest_workout_minutes,
        w.total_calories,
        (w.workouts_missing_calories > 0)          as calories_incomplete,
        w.activities,
        w.intensities,

        night.day                                  as following_night,
        night.sleep_score,
        night.readiness_score,
        night.sleep_hours,
        night.avg_hrv,
        night.lowest_hr,
        night.rem_hours,
        night.bedtime_hours,

        -- The comparison that matters: this night against the week before it
        night.roll7_score,
        night.roll7_nights,
        night.sleep_score - night.roll7_score      as score_vs_baseline,
        night.score_dev_from_week,

        -- Hours between finishing training and getting into bed. Late training
        -- is the plausible mechanism, so it has to be measurable.
        extract(epoch from (
            night.bedtime_start_local - w.last_workout_end::timestamp
        )) / 3600.0                                as hours_from_workout_to_bed

    from workout_days w
    -- inner join: a workout with no following night recorded tells us nothing
    join {{ ref('mart_sleep_daily') }} night
      on night.day = w.workout_day + 1

)

select
    joined.*,
    -- Ranked on minutes, which is complete. Partitioning by nullness would be
    -- unnecessary here and is deliberately absent: if this ever returns null,
    -- the not_null test on total_workout_minutes has already failed.
    ntile(4) over (order by total_workout_minutes) as load_quartile
from joined
order by workout_day
