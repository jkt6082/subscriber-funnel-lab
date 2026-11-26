-- One row per user in the paywall meter test (control: 5 free articles, treatment: 3).

select
    user_id,
    variant,
    assigned_at,
    pre_period_articles_read,
    articles_read,
    cast(subscribed as integer) as subscribed
from {{ source('experiments', 'paywall_meter_users') }}
