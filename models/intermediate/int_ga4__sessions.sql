-- Roll events up to sessions and flag how far down the funnel each session got.

with events as (

    select * from {{ ref('stg_ga4__events') }}
    where ga_session_id is not null

)

select
    session_key,
    user_pseudo_id,
    min(event_date) as session_date,
    min(event_at) as session_started_at,
    max(event_at) as session_ended_at,

    -- GA4 repeats these on every event in a session, so any one value will do
    max(device_category) as device_category,
    max(country) as country,
    max(traffic_source) as traffic_source,
    max(traffic_medium) as traffic_medium,

    sum(case when event_name = 'page_view' then 1 else 0 end) as page_views,
    max(case when event_name = 'view_item' then 1 else 0 end) as did_view_item,
    max(case when event_name = 'add_to_cart' then 1 else 0 end) as did_add_to_cart,
    max(case when event_name = 'begin_checkout' then 1 else 0 end) as did_begin_checkout,
    max(case when event_name = 'purchase' then 1 else 0 end) as did_purchase,
    sum(case when event_name = 'purchase' then coalesce(purchase_revenue_usd, 0) else 0 end) as revenue_usd

from events
group by session_key, user_pseudo_id
