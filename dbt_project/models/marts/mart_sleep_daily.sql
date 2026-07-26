-- Analysis-ready daily features, one row per night.
--
-- Every notebook used to rebuild these in pandas, four copies of the same
-- logic. Pushing them down here removes the duplication and fixes a bug worth
-- naming: pandas `.rolling(7)` counts rows, not days. This dataset is missing
-- 189 calendar days, so "the previous seven nights" spanned up to 34 calendar
-- days and 311 of 1,244 rolling means were averaging the wrong window, off by
-- as much as 14 sleep-score points. The windows below use RANGE with date
-- intervals, so a gap shortens the window instead of silently widening it.
-- `roll7_nights` reports how many nights actually landed in each window.
--
-- Seven nights carry a sleep score but no `long_sleep` period at all: the night
-- fragmented into short `sleep`, `rest` and nap segments instead. They are the
-- worst nights on record, scoring 24 to 50 against a 71 average, and because
-- `daily` sources bedtime and duration from the long sleep, both are null on
-- them. Any pandas analysis that drops nulls therefore discards the seven worst
-- nights without saying so. They are kept here with `has_long_sleep = false` so
-- the exclusion is a choice a query has to make out loud.

with base as (

    select
        day,
        sleep_score,
        readiness_score,
        activity_score,
        sleep_hours,
        efficiency,
        avg_hrv,
        lowest_hr,
        rem_hours,
        deep_hours,
        temp_deviation,
        steps,
        bedtime_start_local,
        bedtime_end_local,
        tz_offset,
        -- Hours after 18:00, so an evening and the small hours sit on one scale
        case
            when extract(hour from bedtime_start_local) >= 18
                then extract(hour from bedtime_start_local) - 18
            else extract(hour from bedtime_start_local) + 6
        end + extract(minute from bedtime_start_local) / 60.0   as bedtime_hours,
        extract(hour from bedtime_end_local)
            + extract(minute from bedtime_end_local) / 60.0     as wake_hours,
        extract(isodow from day)::int                           as isodow,
        date_trunc('week', day)::date                           as week_start,
        (bedtime_start_local is not null)                       as has_long_sleep
    from {{ ref('daily') }}
    where sleep_score is not null

),

windowed as (

    select
        base.*,
        -- Oura files a night under its wake-up day, so isodow 1 is Sunday night
        (isodow = 1)                                as is_sunday_night,
        (isodow in (6, 7))                          as is_weekend_night,

        -- "Previous" means most recently recorded, not necessarily last night.
        -- Pair these with days_since_prev_record: after a 28-day gap the
        -- previous score is a month old, and a model deserves to know that
        -- rather than being handed a stale number as if it were fresh.
        lag(sleep_score)      over ordered          as prev_score,
        lag(sleep_hours)      over ordered          as prev_sleep_hours,
        lag(activity_score)   over ordered          as prev_activity_score,
        lag(steps)            over ordered          as prev_steps,
        lag(day)              over ordered          as prev_day,

        avg(sleep_score)  over trailing_7           as roll7_score,
        avg(sleep_hours)  over trailing_7           as roll7_hours,
        count(*)          over trailing_7           as roll7_nights,
        avg(avg_hrv)      over trailing_28          as roll28_hrv,

        avg(sleep_score)   over per_week            as week_mean_score,
        avg(bedtime_hours) over per_week            as week_mean_bedtime,
        count(*)           over per_week            as week_nights,

        percent_rank()    over ordered_by_score     as score_percentile

    from base
    window
        ordered as (order by day),
        ordered_by_score as (order by sleep_score),
        -- Strictly the preceding week: excludes tonight, so these stay usable
        -- as pre-bed features in a forecast without leaking the target
        trailing_7 as (
            order by day
            range between interval '7 days' preceding
                      and interval '1 day' preceding
        ),
        trailing_28 as (
            order by day
            range between interval '28 days' preceding and current row
        ),
        per_week as (partition by week_start)

)

select
    day,
    week_start,
    isodow,
    is_sunday_night,
    is_weekend_night,
    has_long_sleep,

    sleep_score,
    readiness_score,
    activity_score,
    sleep_hours,
    efficiency,
    avg_hrv,
    lowest_hr,
    rem_hours,
    deep_hours,
    temp_deviation,
    steps,

    bedtime_start_local,
    bedtime_hours,
    wake_hours,
    tz_offset,

    prev_score,
    prev_sleep_hours,
    prev_activity_score,
    prev_steps,
    roll7_score,
    roll7_hours,
    roll7_nights,
    roll28_hrv,

    -- Within-week deviations strip anything slower than a week. This is how
    -- day-of-week questions avoid crediting seasonal drift with an effect;
    -- notebook 04 explains why the alternative correction kills real findings.
    sleep_score   - week_mean_score               as score_dev_from_week,
    bedtime_hours - week_mean_bedtime             as bedtime_dev_from_week,
    week_nights,

    score_percentile,
    (day - prev_day)                              as days_since_prev_record,
    coalesce(day - prev_day, 1) > 3               as follows_gap

from windowed
