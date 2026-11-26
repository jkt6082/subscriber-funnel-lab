select *
from {{ ref('mart_weekly_retention') }}
where retention_rate < 0 or retention_rate > 1 or weeks_since_first_visit < 0
