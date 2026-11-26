-- Weekly retention: of the users who first visited in a given week (their cohort),
-- what share came back 1, 2, 3... weeks later?

with cohorts as (

    select
        user_pseudo_id,
        {{ dbt.date_trunc('week', 'first_seen_at') }} as cohort_week
    from {{ ref('dim_users') }}

),

activity as (

    select distinct
        user_pseudo_id,
        {{ dbt.date_trunc('week', 'session_started_at') }} as active_week
    from {{ ref('fct_sessions') }}

),

cohort_activity as (

    select
        cohorts.cohort_week,
        {{ dbt.datediff('cohorts.cohort_week', 'activity.active_week', 'week') }} as weeks_since_first_visit,
        cohorts.user_pseudo_id
    from cohorts
    inner join activity
        on cohorts.user_pseudo_id = activity.user_pseudo_id

),

active_counts as (

    select
        cohort_week,
        weeks_since_first_visit,
        count(distinct user_pseudo_id) as active_users
    from cohort_activity
    group by cohort_week, weeks_since_first_visit

),

cohort_sizes as (

    select cohort_week, count(*) as cohort_users
    from cohorts
    group by cohort_week

)

select
    active_counts.cohort_week,
    active_counts.weeks_since_first_visit,
    cohort_sizes.cohort_users,
    active_counts.active_users,
    1.0 * active_counts.active_users / cohort_sizes.cohort_users as retention_rate
from active_counts
inner join cohort_sizes
    on active_counts.cohort_week = cohort_sizes.cohort_week
