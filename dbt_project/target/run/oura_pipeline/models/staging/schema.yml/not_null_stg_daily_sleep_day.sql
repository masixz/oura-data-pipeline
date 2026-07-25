
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select day
from "oura"."staging"."stg_daily_sleep"
where day is null



  
  
      
    ) dbt_internal_test