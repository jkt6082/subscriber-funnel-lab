"""Build the static dashboard: query the dbt marts and bake the results into one HTML page.

    python -m funnel_lab.dashboard        # after `dbt build`; writes site/index.html
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import date
from pathlib import Path

import duckdb

from funnel_lab.experiments.readout import analyse

TEMPLATE = Path(__file__).resolve().parent.parent / "web" / "index.html"
DATA_MARKER = "/*__DASHBOARD_DATA__*/null"


def _records(con: duckdb.DuckDBPyConnection, sql: str) -> list[dict]:
    df = con.execute(sql).df()
    for col in df.columns:
        if str(df[col].dtype).startswith(("datetime", "date")):
            df[col] = df[col].dt.strftime("%Y-%m-%d")
    return json.loads(df.to_json(orient="records"))


def collect(con: duckdb.DuckDBPyConnection) -> dict:
    kpis = _records(con, """
        select
            count(*) as sessions,
            count(distinct user_pseudo_id) as users,
            sum(did_purchase) as purchases,
            sum(revenue_usd) as revenue_usd,
            1.0 * sum(did_purchase) / count(*) as conversion_rate,
            min(session_date) as first_date,
            max(session_date) as last_date
        from fct_sessions
    """)[0]

    funnel = _records(con, """
        select
            device_category,
            sum(sessions) as visit,
            sum(view_item_sessions) as view_item,
            sum(add_to_cart_sessions) as add_to_cart,
            sum(begin_checkout_sessions) as begin_checkout,
            sum(purchase_sessions) as purchase
        from mart_daily_funnel
        group by device_category
        order by visit desc
    """)

    daily = _records(con, """
        select session_date, sum(sessions) as sessions, sum(purchase_sessions) as purchases
        from mart_daily_funnel
        group by session_date
        order by session_date
    """)

    weekly_conversion = _records(con, """
        select
            date_trunc('week', session_date) as week,
            device_category,
            sum(sessions) as sessions,
            1.0 * sum(purchase_sessions) / sum(sessions) as conversion_rate
        from mart_daily_funnel
        group by 1, 2
        order by 1, 2
    """)

    retention = _records(con, """
        select cohort_week, weeks_since_first_visit, cohort_users, active_users, retention_rate
        from mart_weekly_retention
        order by cohort_week, weeks_since_first_visit
    """)

    users = con.execute("select * from fct_paywall_meter_users").df()
    experiment = analyse(users).to_dict()

    return {
        "kpis": kpis,
        "funnel": funnel,
        "daily": daily,
        "weekly_conversion": weekly_conversion,
        "retention": retention,
        "experiment": experiment,
        "built_at": date.today().isoformat(),
    }


def _clean(value):
    """JSON has no NaN/inf; turn them into null."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clean(v) for v in value]
    return value


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--warehouse", type=Path, default=Path("data/warehouse.duckdb"))
    parser.add_argument("--out", type=Path, default=Path("site/index.html"))
    args = parser.parse_args(argv)

    con = duckdb.connect(str(args.warehouse), read_only=True)
    try:
        data = _clean(collect(con))
    finally:
        con.close()

    html = TEMPLATE.read_text(encoding="utf-8")
    if DATA_MARKER not in html:
        raise SystemExit(f"Template {TEMPLATE} is missing the data marker {DATA_MARKER!r}")
    payload = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html.replace(DATA_MARKER, payload), encoding="utf-8")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
