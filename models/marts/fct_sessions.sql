with sessions as (

    select * from {{ ref('int_ga4__sessions') }}

)

select
    *,
    row_number() over (
        partition by user_pseudo_id
        order by session_started_at
    ) as user_session_number,
    {{ dbt.datediff('session_started_at', 'session_ended_at', 'second') }} as session_duration_seconds,
    case
        when did_purchase = 1 then '5_purchase'
        when did_begin_checkout = 1 then '4_begin_checkout'
        when did_add_to_cart = 1 then '3_add_to_cart'
        when did_view_item = 1 then '2_view_item'
        else '1_visit'
    end as deepest_funnel_step
from sessions
