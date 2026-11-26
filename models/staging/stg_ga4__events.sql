-- One row per GA4 event, with the nested fields we use pulled out into columns.

with source as (

    select * from {{ source('ga4', 'events') }}

),

renamed as (

    select
        {{ yyyymmdd_to_date('event_date') }} as event_date,
        {{ micros_to_timestamp('event_timestamp') }} as event_at,
        event_timestamp as event_timestamp_micros,
        event_name,
        user_pseudo_id,
        {{ ga4_param('ga_session_id', 'int') }} as ga_session_id,
        {{ ga4_param('page_location') }} as page_location,
        device.category as device_category,
        geo.country as country,
        traffic_source.source as traffic_source,
        traffic_source.medium as traffic_medium,
        ecommerce.purchase_revenue_in_usd as purchase_revenue_usd
    from source

)

select
    {{ dbt.hash(dbt.concat([
        "user_pseudo_id",
        "'|'",
        "cast(event_timestamp_micros as " ~ dbt.type_string() ~ ")",
        "'|'",
        "event_name"
    ])) }} as event_id,
    {{ dbt.concat(["user_pseudo_id", "'-'", "cast(ga_session_id as " ~ dbt.type_string() ~ ")"]) }} as session_key,
    *
from renamed
