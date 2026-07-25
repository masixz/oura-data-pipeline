
    
    

select
    doc_id as unique_field,
    count(*) as n_records

from "oura"."staging"."stg_sleep_periods"
where doc_id is not null
group by doc_id
having count(*) > 1


