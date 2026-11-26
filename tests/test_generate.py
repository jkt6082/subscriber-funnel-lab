import duckdb

from funnel_lab.experiments.simulate import simulate_paywall_meter
from funnel_lab.generate import generate_events, write_raw


def test_generated_sample_has_ga4_shape(tmp_path):
    path = tmp_path / "raw.duckdb"
    write_raw(path, generate_events(n_users=300, seed=5), simulate_paywall_meter(n_users=500))

    con = duckdb.connect(str(path), read_only=True)
    columns = {r[0] for r in con.execute("describe ga4.events").fetchall()}
    assert {"event_date", "event_timestamp", "event_name", "event_params", "user_pseudo_id",
            "device", "geo", "traffic_source", "ecommerce"} <= columns

    session_id = con.execute("""
        select (list_filter(event_params, lambda p: p.key = 'ga_session_id')[1]).value.int_value
        from ga4.events limit 1
    """).fetchone()[0]
    assert session_id > 1_600_000_000  # epoch seconds in Nov 2020

    dupes = con.execute("""
        select count(*) from (
            select user_pseudo_id, event_timestamp, event_name from ga4.events
            group by all having count(*) > 1
        )
    """).fetchone()[0]
    assert dupes == 0

    # purchases carry revenue, other events don't
    bad = con.execute("""
        select count(*) from ga4.events
        where (event_name = 'purchase') != (ecommerce.purchase_revenue_in_usd is not null)
    """).fetchone()[0]
    assert bad == 0
    con.close()
