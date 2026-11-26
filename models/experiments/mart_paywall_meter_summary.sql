select
    variant,
    count(*) as users,
    sum(subscribed) as subscribers,
    avg(subscribed) as subscription_rate,
    avg(articles_read) as avg_articles_read,
    avg(pre_period_articles_read) as avg_pre_period_articles_read
from {{ ref('fct_paywall_meter_users') }}
group by variant
