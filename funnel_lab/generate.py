"""Write a local sample warehouse: GA4-shaped events plus the simulated paywall test.

The events use the same nested schema as Google's GA4 BigQuery export, so the dbt
models run unchanged against either this sample or the real public dataset.

    python -m funnel_lab.generate            # ~15k users, writes data/raw.duckdb
    python -m funnel_lab.generate --users 2000
"""

from __future__ import annotations

import argparse
import math
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from funnel_lab.experiments.simulate import simulate_paywall_meter

START = datetime(2020, 11, 1, tzinfo=timezone.utc)  # same window as the GA4 public sample
DAYS = 92
US_PER_SECOND = 1_000_000
US_PER_DAY = 86_400 * US_PER_SECOND
BLACK_FRIDAY = 26  # days after START

DEVICES = ["desktop", "mobile", "tablet"]
DEVICE_WEIGHTS = [0.58, 0.39, 0.03]
DEVICE_CONVERSION = {"desktop": 1.0, "mobile": 0.6, "tablet": 0.8}
COUNTRIES = ["United States", "India", "Canada", "United Kingdom", "Germany", "France", "Japan"]
COUNTRY_WEIGHTS = [0.45, 0.10, 0.10, 0.10, 0.09, 0.08, 0.08]
SOURCES = [
    ("google", "organic"),
    ("(direct)", "(none)"),
    ("google", "cpc"),
    ("newsletter", "email"),
    ("partner.example.com", "referral"),
]
SOURCE_WEIGHTS = [0.40, 0.30, 0.12, 0.08, 0.10]
SITE = "https://shop.example.com"
PAGES = ["/", "/store/apparel", "/store/drinkware", "/store/bags", "/store/lifestyle", "/sale"]


def seasonal_boost(day: int) -> float:
    """Purchase intent: a Black Friday spike, a December ramp, a post-Christmas lull."""
    boost = 1.0 + 0.8 * math.exp(-((day - BLACK_FRIDAY) ** 2) / 8)
    if 30 <= day < 55:  # Dec 1 - Dec 24
        boost += 0.3
    elif day >= 55:
        boost -= 0.3
    return boost


def generate_events(n_users: int = 15_000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    start_us = int(START.timestamp() * US_PER_SECOND)
    end_us = start_us + DAYS * US_PER_DAY
    rows: list[tuple] = []

    for u in range(n_users):
        user_id = f"{u:010d}.{rng.integers(10**9, 10**10)}"
        device = DEVICES[rng.choice(3, p=DEVICE_WEIGHTS)]
        country = COUNTRIES[rng.choice(len(COUNTRIES), p=COUNTRY_WEIGHTS)]
        source, medium = SOURCES[rng.choice(len(SOURCES), p=SOURCE_WEIGHTS)]

        t = start_us + int(rng.integers(0, DAYS * US_PER_DAY))
        for s in range(rng.geometric(0.55)):
            if s > 0:  # at least an hour between sessions, so session ids never collide
                t += int(rng.exponential(5 * US_PER_DAY)) + 3600 * US_PER_SECOND
            if t >= end_us:
                break

            factor = DEVICE_CONVERSION[device] * seasonal_boost((t - start_us) // US_PER_DAY)
            session_id = t // US_PER_SECOND
            landing = SITE + PAGES[rng.integers(len(PAGES))]

            names: list[tuple[str, str | None, float | None]] = []
            if s == 0:
                names.append(("first_visit", landing, None))
            names.append(("session_start", landing, None))
            for _ in range(1 + rng.poisson(2.5)):
                names.append(("page_view", SITE + PAGES[rng.integers(len(PAGES))], None))
            if rng.random() < 0.45:
                names.append(("view_item", None, None))
                if rng.random() < 0.22 * factor:
                    names.append(("add_to_cart", None, None))
                    if rng.random() < 0.5:
                        names.append(("begin_checkout", SITE + "/checkout", None))
                        if rng.random() < min(0.95, 0.45 * factor):
                            revenue = round(float(rng.lognormal(math.log(55), 0.6)), 2)
                            names.append(("purchase", SITE + "/checkout/complete", revenue))

            ts = t
            for name, page, revenue in names:
                rows.append((ts, name, user_id, session_id, page, device, country, source, medium, revenue))
                ts += int(rng.exponential(30 * US_PER_SECOND)) + 1
            t = ts

    events = pd.DataFrame(
        rows,
        columns=[
            "event_timestamp", "event_name", "user_pseudo_id", "ga_session_id", "page_location",
            "device_category", "country", "ts_source", "ts_medium", "purchase_revenue_in_usd",
        ],
    )
    events["purchase_revenue_in_usd"] = events["purchase_revenue_in_usd"].astype("Float64")
    return events


# Rebuild GA4's nested export layout from the flat rows.
GA4_EVENTS_SQL = """
create table ga4.events as
select
    strftime(make_timestamp(event_timestamp), '%Y%m%d') as event_date,
    event_timestamp,
    event_name,
    [
        {'key': 'ga_session_id', 'value': {
            'string_value': null::varchar, 'int_value': ga_session_id::bigint,
            'float_value': null::double, 'double_value': null::double}},
        {'key': 'page_location', 'value': {
            'string_value': page_location::varchar, 'int_value': null::bigint,
            'float_value': null::double, 'double_value': null::double}}
    ] as event_params,
    user_pseudo_id,
    {'category': device_category} as device,
    {'country': country} as geo,
    {'source': ts_source, 'medium': ts_medium} as traffic_source,
    {'purchase_revenue_in_usd': purchase_revenue_in_usd::double} as ecommerce
from flat_events
order by event_timestamp
"""


def write_raw(path: Path, events: pd.DataFrame, experiment: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    con = duckdb.connect(str(path))
    try:
        con.execute("create schema ga4")
        con.execute("create schema experiments")
        con.register("flat_events", events)
        con.execute(GA4_EVENTS_SQL)
        con.register("experiment_users", experiment)
        con.execute("create table experiments.paywall_meter_users as select * from experiment_users")
    finally:
        con.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--users", type=int, default=15_000, help="GA4 users to generate")
    parser.add_argument("--experiment-users", type=int, default=40_000)
    parser.add_argument("--out", type=Path, default=Path("data/raw.duckdb"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)

    events = generate_events(args.users, args.seed)
    experiment = simulate_paywall_meter(args.experiment_users)
    write_raw(args.out, events, experiment)
    print(f"Wrote {len(events):,} events and {len(experiment):,} experiment users to {args.out}")


if __name__ == "__main__":
    main()
