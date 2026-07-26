-- stg_sleep_periods reads local wall-clock time positionally: the first 19
-- characters are the local timestamp, the last 6 are the UTC offset. Oura sends
-- e.g. 2026-01-02T01:40:00.000+02:00.
--
-- This asserts exactly what that parse depends on and nothing more. The leading
-- 19 characters must be a full ISO timestamp and the string must end in a
-- numeric offset; fractional seconds may be present, absent, or any length,
-- because they sit between the two slices and never affect either. A 'Z'
-- suffix, a missing offset, or a shifted layout would silently yield wrong
-- bedtimes instead of failing, which is what this catches.
--
-- Rows returned = test failure.

select
    doc_id,
    payload->>'bedtime_start' as bedtime_start_raw,
    payload->>'bedtime_end'   as bedtime_end_raw
from {{ source('raw', 'oura_documents') }}
where endpoint = 'sleep'
  and (
        payload->>'bedtime_start' !~ '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?[+-]\d{2}:\d{2}$'
     or payload->>'bedtime_end'   !~ '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?[+-]\d{2}:\d{2}$'
  )
