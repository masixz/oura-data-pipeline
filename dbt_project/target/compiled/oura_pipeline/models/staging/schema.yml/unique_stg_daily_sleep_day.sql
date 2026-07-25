
    
    

select
    day as unique_field,
    count(*) as n_records

from "oura"."staging"."stg_daily_sleep"
where day is not null
group by day
having count(*) > 1


