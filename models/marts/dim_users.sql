with sessions as (

    select * from {{ ref('fct_sessions') }}

),

first_session as (

    select
        user_pseudo_id,
        device_category as first_device_category,
        country as first_country,
        traffic_source as first_traffic_source,
        traffic_medium as first_traffic_medium
    from sessions
    where user_session_number = 1

),

totals as (

    select
        user_pseudo_id,
        min(session_started_at) as first_seen_at,
        max(session_started_at) as last_seen_at,
        count(*) as sessions,
        sum(did_purchase) as purchasing_sessions,
        sum(revenue_usd) as lifetime_revenue_usd
    from sessions
    group by user_pseudo_id

)

select
    totals.*,
    first_session.first_device_category,
    first_session.first_country,
    first_session.first_traffic_source,
    first_session.first_traffic_medium
from totals
inner join first_session using (user_pseudo_id)
