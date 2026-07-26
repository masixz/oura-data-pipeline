-- One row per calendar week: the grain the headline finding lives at.
--
-- Timing is the week's mean bedtime, consistency its standard deviation. The
-- README claim is that timing carries the effect and consistency only looks
-- relevant because the two move together, so both columns are here to be
-- compared directly rather than trusted.
--
-- `nights_logged` and `coverage` are first-class columns, not diagnostics.
-- Coverage runs 87% overall and drops to 80% through the 2024 dip, so any week
-- built from three nights deserves less weight than one built from seven.

with weekly as (

    select
        week_start,
        count(*)                                                   as nights_logged,
        round(count(*) / 7.0, 3)                                   as coverage,
        avg(sleep_score)                                           as mean_score,
        percentile_cont(0.5) within group (order by sleep_score)    as median_score,
        min(sleep_score)                                           as worst_score,
        max(sleep_score)                                           as best_score,
        avg(sleep_hours)                                           as mean_sleep_hours,
        -- Timing and consistency, the two competing explanations
        avg(bedtime_hours)                                         as mean_bedtime_hours,
        stddev_samp(bedtime_hours)                                 as bedtime_sd_hours,
        avg(avg_hrv)                                               as mean_hrv,
        avg(lowest_hr)                                             as mean_lowest_hr,
        avg(readiness_score)                                       as mean_readiness,
        sum(steps)                                                 as total_steps,
        count(*) filter (where is_weekend_night)                   as weekend_nights,
        count(*) filter (where follows_gap)                        as nights_after_a_gap
    from {{ ref('mart_sleep_daily') }}
    group by week_start

),

compared as (

    select
        weekly.*,

        lag(mean_score)  over ordered                  as prev_week_score,
        mean_score - lag(mean_score) over ordered      as score_wow_delta,
        lag(mean_bedtime_hours) over ordered           as prev_week_bedtime,

        -- Date-based so the four-week context does not quietly reach across a
        -- month-long gap and call it recent
        avg(mean_score) over trailing_4wk              as score_4wk_mean,
        avg(mean_bedtime_hours) over trailing_4wk      as bedtime_4wk_mean,
        count(*) over trailing_4wk                     as weeks_in_4wk_window,

        percent_rank() over (order by mean_score)      as score_percentile,
        ntile(4) over (order by mean_score)            as score_quartile,

        avg(mean_score) over ()                        as all_time_mean_score

    from weekly
    window
        ordered as (order by week_start),
        trailing_4wk as (
            order by week_start
            range between interval '28 days' preceding and current row
        )

),

-- Gaps and islands: label runs of consecutive weeks on the same side of the
-- all-time average, so "a bad spell" becomes a queryable object rather than
-- something read off a chart by eye.
flagged as (

    select
        compared.*,
        (mean_score < all_time_mean_score) as below_average,
        row_number() over (order by week_start)
            - row_number() over (
                partition by (mean_score < all_time_mean_score)
                order by week_start
              ) as spell_group
    from compared

)

select
    week_start,
    nights_logged,
    coverage,
    mean_score,
    median_score,
    worst_score,
    best_score,
    mean_sleep_hours,
    mean_bedtime_hours,
    bedtime_sd_hours,
    mean_hrv,
    mean_lowest_hr,
    mean_readiness,
    total_steps,
    weekend_nights,
    nights_after_a_gap,
    prev_week_score,
    score_wow_delta,
    prev_week_bedtime,
    score_4wk_mean,
    bedtime_4wk_mean,
    weeks_in_4wk_window,
    score_percentile,
    score_quartile,
    below_average,
    count(*) over (partition by below_average, spell_group) as spell_length_weeks,
    row_number() over (
        partition by below_average, spell_group order by week_start
    ) as week_within_spell
from flagged
order by week_start
