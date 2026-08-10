"""Runs the raw -> clean SQL transforms in order, both within the staging schema.
Idempotent (every transform is INSERT ... ON CONFLICT DO UPDATE), so safe to re-run any
time the raw tables have new data -- this is what the daily incremental job calls after
the day's raw load.

Usage:
    python -m mystock.etl.staging.transform_all
"""
import time
from pathlib import Path

from mystock.db import get_conn, etl_run

SQL_DIR = Path(__file__).resolve().parent / "sql"
TRANSFORMS = [
    "01_equity_master.sql",
    "02_stock_daily_from_stock_history.sql",
    "03_stock_daily_from_bhavcopy.sql",
    "04_company_fundamentals_snapshot.sql",
    "05_company_financials.sql",
    "06_company_dividends.sql",
    "07_index_daily.sql",
]


def run_sql_file(conn, path):
    sql = path.read_text()
    with conn.cursor() as cur:
        cur.execute(sql)
        rowcount = cur.rowcount
    conn.commit()
    return rowcount


def main():
    conn = get_conn()
    for filename in TRANSFORMS:
        path = SQL_DIR / filename
        with etl_run(f"staging_transform_{filename}", {"file": filename}) as run:
            t0 = time.time()
            rows = run_sql_file(conn, path)
            run["rows"] = rows
            print(f"{filename}: {rows} rows affected ({time.time() - t0:.1f}s)")
    conn.close()


if __name__ == "__main__":
    main()
