-- A step count above the session count means the session rollup is double counting.
-- Returns failing rows; dbt passes the test when this is empty.

select *
from {{ ref('mart_daily_funnel') }}
where view_item_sessions > sessions
   or add_to_cart_sessions > sessions
   or begin_checkout_sessions > sessions
   or purchase_sessions > sessions
