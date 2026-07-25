
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

select
    doc_id as unique_field,
    count(*) as n_records

from "oura"."staging"."stg_sleep_periods"
where doc_id is not null
group by doc_id
having count(*) > 1



  
  
      
    ) dbt_internal_test