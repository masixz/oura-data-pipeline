-- Sleep architecture per night, derived from the 30-second hypnogram and the
-- 5-minute HR and HRV series rather than from Oura's nightly summaries.
--
-- Why bother when `daily` already has REM hours: the summaries say how much,
-- the hypnogram says when. Those answer different questions. "REM is
-- concentrated at the morning end" was inferred in notebook 03 from a
-- correlation with wake time; here it can be measured directly by splitting
-- each night into thirds.
--
-- Standard sleep-medicine metrics where they exist, because inventing private
-- definitions makes results incomparable to anything published:
--   * sleep onset latency, first sleep epoch after the series starts
--   * REM latency, onset to first REM epoch
--   * WASO, wake after sleep onset, minutes awake between first and last sleep
--   * awakenings, transitions into a wake epoch after sleep has begun
--
-- Thirds are thirds of the sleep period, not of clock time, so a short night
-- and a long one stay comparable.

with epochs as (

    select
        doc_id,
        day,
        epoch_index,
        minutes_into_sleep,
        sleep_phase,
        movement_code,
        (sleep_phase <> 'awake')                                  as asleep,
        n_epochs
    from {{ ref('stg_sleep_phases') }}

),

-- Sleep onset is the first non-awake epoch. Everything before it is time spent
-- lying there, and counting that as WASO would overstate fragmentation badly.
onset as (

    select
        doc_id,
        min(epoch_index) filter (where asleep)                    as first_sleep_epoch,
        max(epoch_index) filter (where asleep)                    as last_sleep_epoch,
        min(epoch_index) filter (where sleep_phase = 'rem')       as first_rem_epoch,
        min(epoch_index) filter (where sleep_phase = 'deep')      as first_deep_epoch
    from epochs
    group by doc_id

),

-- Thirds of the sleep period, plus a flag for each epoch that starts a new
-- awakening rather than continuing one
positioned as (

    select
        e.*,
        o.first_sleep_epoch,
        o.last_sleep_epoch,
        o.first_rem_epoch,
        o.first_deep_epoch,
        ntile(3) over (
            partition by e.doc_id order by e.epoch_index
        )                                                          as night_third,
        (not e.asleep
         and lag(e.asleep) over (partition by e.doc_id order by e.epoch_index)
        )                                                          as starts_awakening
    from epochs e
    join onset o using (doc_id)
    where o.first_sleep_epoch is not null
      and e.epoch_index between o.first_sleep_epoch and o.last_sleep_epoch

),

per_night as (

    select
        doc_id,
        day,
        max(n_epochs)                                              as epochs_total,
        count(*)                                                   as epochs_in_sleep_period,
        count(*) * 0.5                                             as sleep_period_minutes,

        (min(first_sleep_epoch) - 1) * 0.5                         as sleep_onset_latency_min,
        case when min(first_rem_epoch) is not null
             then (min(first_rem_epoch) - min(first_sleep_epoch)) * 0.5
        end                                                        as rem_latency_min,
        case when min(first_deep_epoch) is not null
             then (min(first_deep_epoch) - min(first_sleep_epoch)) * 0.5
        end                                                        as deep_latency_min,

        count(*) filter (where not asleep) * 0.5                   as waso_min,
        count(*) filter (where starts_awakening)                   as awakenings,

        round(100.0 * count(*) filter (where sleep_phase = 'rem')   / count(*), 2) as rem_pct,
        round(100.0 * count(*) filter (where sleep_phase = 'deep')  / count(*), 2) as deep_pct,
        round(100.0 * count(*) filter (where sleep_phase = 'light') / count(*), 2) as light_pct,

        -- The question notebook 03 could only approach indirectly
        round(100.0 * count(*) filter (where sleep_phase = 'rem' and night_third = 1)
                    / nullif(count(*) filter (where night_third = 1), 0), 2) as rem_pct_third_1,
        round(100.0 * count(*) filter (where sleep_phase = 'rem' and night_third = 2)
                    / nullif(count(*) filter (where night_third = 2), 0), 2) as rem_pct_third_2,
        round(100.0 * count(*) filter (where sleep_phase = 'rem' and night_third = 3)
                    / nullif(count(*) filter (where night_third = 3), 0), 2) as rem_pct_third_3,
        round(100.0 * count(*) filter (where sleep_phase = 'deep' and night_third = 1)
                    / nullif(count(*) filter (where night_third = 1), 0), 2) as deep_pct_third_1,
        round(100.0 * count(*) filter (where sleep_phase = 'deep' and night_third = 3)
                    / nullif(count(*) filter (where night_third = 3), 0), 2) as deep_pct_third_3,

        round(avg(movement_code), 3)                               as mean_movement
    from positioned
    group by doc_id, day

),

-- Heart rate and HRV are on a 5-minute grid, so they are summarised separately
-- and joined back rather than forced onto the 30-second one
vitals as (

    select
        doc_id,
        min(heart_rate)                                            as hr_min,
        round(avg(heart_rate), 1)                                  as hr_mean,
        round(avg(hrv), 1)                                         as hrv_mean,
        -- When the night's lowest heart rate arrives. Early is the textbook
        -- pattern; late can mean the body never settled.
        (array_agg(minutes_into_sleep order by heart_rate asc nulls last))[1] as minutes_to_hr_nadir,
        round(avg(hrv) filter (where minutes_into_sleep < 60), 1)  as hrv_first_hour,
        round(avg(hrv) filter (
            where minutes_into_sleep >= (max_minutes - 60)), 1)    as hrv_last_hour,
        count(*) filter (where heart_rate is null)                 as missing_hr_samples,
        count(*)                                                   as hr_samples
    from (
        select *, max(minutes_into_sleep) over (partition by doc_id) as max_minutes
        from {{ ref('stg_sleep_hr_hrv') }}
    ) h
    group by doc_id

)

select
    p.*,
    v.hr_min,
    v.hr_mean,
    v.hrv_mean,
    v.minutes_to_hr_nadir,
    v.hrv_first_hour,
    v.hrv_last_hour,
    v.hrv_last_hour - v.hrv_first_hour                             as hrv_overnight_change,
    v.missing_hr_samples,
    v.hr_samples,
    d.sleep_score,
    d.readiness_score,
    -- Oura records which scoring version produced each night. v2 reclassified
    -- roughly ten points of deep sleep as light on 2023-06-21, so any analysis
    -- of stages spanning that date has to control for this column.
    coalesce(src.payload->>'sleep_algorithm_version', 'pre-versioning') as sleep_algorithm_version
from per_night p
left join vitals v using (doc_id)
left join {{ ref('daily') }} d on d.day = p.day
left join {{ source('raw', 'oura_documents') }} src
       on src.doc_id = p.doc_id and src.endpoint = 'sleep'
