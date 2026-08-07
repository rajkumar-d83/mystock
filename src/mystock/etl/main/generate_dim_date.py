"""Generates main.dim_date for 2000-01-01..2030-12-31. Self-contained — doesn't
depend on any NSE data. is_trading_day is backfilled separately once staging.stock_daily
has data (a date is a trading day if any row references it).

Usage:
    python -m mystock.etl.main.generate_dim_date
"""
from datetime import date, timedelta

import psycopg2.extras

from mystock.db import get_conn

START = date(2000, 1, 1)
END = date(2030, 12, 31)


def financial_year(d):
    # India's FY runs Apr 1 - Mar 31
    start_year = d.year if d.month >= 4 else d.year - 1
    return f"FY{start_year}-{str(start_year + 1)[-2:]}"


def build_rows():
    rows = []
    d = START
    while d <= END:
        rows.append((
            int(d.strftime("%Y%m%d")),
            d,
            d.year,
            (d.month - 1) // 3 + 1,
            d.month,
            d.strftime("%B"),
            d.day,
            d.isoweekday(),
            d.strftime("%A"),
            d.isoweekday() >= 6,
            financial_year(d),
        ))
        d += timedelta(days=1)
    return rows


def main():
    rows = build_rows()
    conn = get_conn()
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """INSERT INTO main.dim_date
                   (date_key, full_date, year, quarter, month, month_name, day,
                    day_of_week, day_name, is_weekend, financial_year)
               VALUES %s
               ON CONFLICT (date_key) DO NOTHING""",
            rows,
        )
    conn.commit()
    conn.close()
    print(f"Generated {len(rows)} dates ({START}..{END})")


if __name__ == "__main__":
    main()
