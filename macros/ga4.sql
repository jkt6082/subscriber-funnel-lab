{#
  GA4 stores event parameters as an array of {key, value{string_value, int_value, ...}}.
  BigQuery and DuckDB unpack arrays differently, so these macros dispatch per adapter.
#}

{% macro ga4_param(name, value_type='string') -%}
    {{ return(adapter.dispatch('ga4_param')(name, value_type)) }}
{%- endmacro %}

{% macro default__ga4_param(name, value_type) -%}
    (select ep.value.{{ value_type }}_value from unnest(event_params) as ep where ep.key = '{{ name }}' limit 1)
{%- endmacro %}

{% macro duckdb__ga4_param(name, value_type) -%}
    (list_filter(event_params, lambda p: p.key = '{{ name }}')[1]).value.{{ value_type }}_value
{%- endmacro %}


{% macro micros_to_timestamp(column) -%}
    {{ return(adapter.dispatch('micros_to_timestamp')(column)) }}
{%- endmacro %}

{% macro default__micros_to_timestamp(column) -%}
    timestamp_micros({{ column }})
{%- endmacro %}

{% macro duckdb__micros_to_timestamp(column) -%}
    make_timestamp({{ column }})
{%- endmacro %}


{% macro yyyymmdd_to_date(column) -%}
    {{ return(adapter.dispatch('yyyymmdd_to_date')(column)) }}
{%- endmacro %}

{% macro default__yyyymmdd_to_date(column) -%}
    parse_date('%Y%m%d', {{ column }})
{%- endmacro %}

{% macro duckdb__yyyymmdd_to_date(column) -%}
    cast(strptime({{ column }}, '%Y%m%d') as date)
{%- endmacro %}
