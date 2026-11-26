"""Print a readout of the paywall meter test from the dbt warehouse.

    python -m funnel_lab.experiments              # after `dbt build`
"""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb

from funnel_lab.experiments.readout import analyse


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--warehouse", type=Path, default=Path("data/warehouse.duckdb"))
    args = parser.parse_args(argv)

    con = duckdb.connect(str(args.warehouse), read_only=True)
    users = con.execute("select * from fct_paywall_meter_users").df()
    con.close()
    r = analyse(users)
    conv, raw, cuped = r.conversion, r.articles_raw, r.articles_cuped

    print("Paywall meter test: 5 free articles (control) vs 3 (treatment)\n")
    print(f"Split         {r.control_users:,} vs {r.treatment_users:,}   SRM p = {r.srm_p_value:.3f}"
          + ("   << check assignment!" if r.srm_p_value < 0.001 else ""))
    print(f"Subscription  {r.control_rate:.2%} -> {r.treatment_rate:.2%}   "
          f"diff {conv.estimate:+.2%} [{conv.ci_low:+.2%}, {conv.ci_high:+.2%}]   p = {conv.p_value:.4f}")
    print(f"              relative lift {r.relative_lift:+.1%}   "
          f"(true simulated: {r.true_relative_lift:+.1%}, CI covers truth: {conv.contains(r.true_absolute_lift)})")
    print(f"\nArticles read diff {raw.estimate:+.2f}  raw CI width {raw.ci_high - raw.ci_low:.3f}")
    print(f"                   {cuped.estimate:+.2f}  CUPED CI width {cuped.ci_high - cuped.ci_low:.3f} "
          f"(theta {r.cuped_theta:.2f}, {r.cuped_variance_reduction:.0%} less variance)")
    print(f"\nPower check: {r.users_needed_per_arm:,} users per arm needed to detect the true lift at 80% power.")
    print(f"Peeking: checking daily for {r.peeking_looks} days and stopping at p<0.05 gives a "
          f"{r.peeking_false_positive_rate:.0%} false positive rate in A/A tests.")


if __name__ == "__main__":
    main()
