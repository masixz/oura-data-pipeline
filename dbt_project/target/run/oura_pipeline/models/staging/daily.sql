
  create view "oura"."staging"."daily__dbt_tmp"
    
    
  as (
    -- One row per day: the analysis-ready wide table
select
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
from "oura"."staging"."stg_daily_sleep" ds
left join "oura"."staging"."stg_daily_readiness" dr using (day)
left join "oura"."staging"."stg_daily_activity" da using (day)
left join lateral (
    select * from "oura"."staging"."stg_sleep_periods" p
    where p.day = ds.day and p.type = 'long_sleep'
    order by p.sleep_hours desc limit 1
) sp on true
  );