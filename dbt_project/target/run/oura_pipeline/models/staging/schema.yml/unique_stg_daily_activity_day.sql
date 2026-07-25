
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

select
    day as unique_field,
    count(*) as n_records

from "oura"."staging"."stg_daily_activity"
where day is not null
group by day
having count(*) > 1



  
  
      
    ) dbt_internal_test