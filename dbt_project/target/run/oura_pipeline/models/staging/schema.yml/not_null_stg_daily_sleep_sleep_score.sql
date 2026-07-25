
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select sleep_score
from "oura"."staging"."stg_daily_sleep"
where sleep_score is null



  
  
      
    ) dbt_internal_test