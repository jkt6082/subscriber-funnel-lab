-- Daily funnel by device: how many sessions reach each step, and step-to-step conversion.

with sessions as (

    select * from {{ ref('fct_sessions') }}

),

daily as (

    select
        session_date,
        device_category,
        count(*) as sessions,
        sum(did_view_item) as view_item_sessions,
        sum(did_add_to_cart) as add_to_cart_sessions,
        sum(did_begin_checkout) as begin_checkout_sessions,
        sum(did_purchase) as purchase_sessions,
        sum(revenue_usd) as revenue_usd
    from sessions
    group by session_date, device_category

)

select
    *,
    1.0 * view_item_sessions / nullif(sessions, 0) as visit_to_view_rate,
    1.0 * add_to_cart_sessions / nullif(view_item_sessions, 0) as view_to_cart_rate,
    1.0 * begin_checkout_sessions / nullif(add_to_cart_sessions, 0) as cart_to_checkout_rate,
    1.0 * purchase_sessions / nullif(begin_checkout_sessions, 0) as checkout_to_purchase_rate,
    1.0 * purchase_sessions / nullif(sessions, 0) as session_conversion_rate
from daily
