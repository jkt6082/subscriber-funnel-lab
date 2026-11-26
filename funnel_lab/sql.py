"""A small SQL prompt for exploring the warehouse.

    python -m funnel_lab.sql

Type a query, end it with ; and press Enter. Type .tables to list tables, .quit to leave.
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pandas as pd

WAREHOUSE = Path("data/warehouse.duckdb")


def main() -> None:
    if not WAREHOUSE.exists():
        sys.exit("No warehouse yet. Run `python -m funnel_lab.generate` and `dbt build` first.")

    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    # The staging views read from the raw file, so attach it the same way dbt does
    con.execute("attach 'data/raw.duckdb' as raw (read_only)")
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 30)
    print(__doc__.strip().splitlines()[-1])

    buffer: list[str] = []
    while True:
        try:
            line = input("sql> " if not buffer else "...> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break

        stripped = line.strip()
        if not buffer and stripped in {".quit", ".exit"}:
            break
        if not buffer and stripped == ".tables":
            print(con.execute("select table_name from information_schema.tables "
                              "where table_schema = 'main' order by 1").df().to_string(index=False))
            continue

        buffer.append(line)
        if not stripped.endswith(";"):
            continue

        query = "\n".join(buffer)
        buffer.clear()
        try:
            result = con.execute(query).df()
        except duckdb.Error as error:
            print(f"Error: {error}")
            continue
        print(result.head(50).to_string(index=False))
        if len(result) > 50:
            print(f"... ({len(result):,} rows, showing the first 50)")

    con.close()


if __name__ == "__main__":
    main()
