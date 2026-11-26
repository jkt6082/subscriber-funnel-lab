-- Every user is active in the week they first visited, so week 0 retention must be 100%.

select *
from {{ ref('mart_weekly_retention') }}
where weeks_since_first_visit = 0
  and active_users != cohort_users
