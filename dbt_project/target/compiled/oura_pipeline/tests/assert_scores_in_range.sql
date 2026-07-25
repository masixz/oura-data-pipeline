-- All Oura scores must be 0-100; rows returned = test failure
select day, sleep_score
from "oura"."staging"."stg_daily_sleep"
where sleep_score < 0 or sleep_score > 100