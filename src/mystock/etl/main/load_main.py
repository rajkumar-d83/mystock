"""Runs the staging -> main SQL loads in order. Idempotent (INSERT ... ON CONFLICT DO
UPDATE throughout), safe to re-run any time staging has new data. Run this after
mystock.etl.staging.transform_all.

Usage:
    python -m mystock.etl.main.load_main
"""
import time
from pathlib import Path

from mystock.db import get_conn, etl_run

SQL_DIR = Path(__file__).resolve().parent / "sql"
LOADS = [
    "01_dim_security.sql",
    "02_dim_date_trading_days.sql",
    "03_fact_daily_prices.sql",
    "04_fact_volume.sql",
    "05_fact_delivery.sql",
    "06_fact_company_fundamentals.sql",
    "07_fact_company_financials.sql",
    "08_fact_company_dividends.sql",
    "09_dim_index.sql",
    "10_fact_index_daily.sql",
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
    for filename in LOADS:
        path = SQL_DIR / filename
        with etl_run(f"main_load_{filename}", {"file": filename}) as run:
            t0 = time.time()
            rows = run_sql_file(conn, path)
            run["rows"] = rows
            print(f"{filename}: {rows} rows affected ({time.time() - t0:.1f}s)")
    conn.close()


if __name__ == "__main__":
    main()
