"""Daily/incremental load: whole-market bhavcopy via jugaad_data.bhavcopy_raw.

Only reliable from ~2019-10-01 onward — for dates before that, use
etl/historical/fetch_stock_history.py instead. One call covers the entire market for a
single day, so this is also the fast way to backfill 2019-10 through today once the
pre-2019 per-symbol backfill is done separately.

Usage:
    python -m mystock.etl.daily.fetch_daily_bhavcopy --date 2026-07-14
    python -m mystock.etl.daily.fetch_daily_bhavcopy --from-date 2019-10-01 --to-date 2026-07-14
"""
import argparse
import csv
import io
import json
import sys
import uuid
from datetime import date, datetime, timedelta

import psycopg2.extras
from jugaad_data.nse import NSEArchives

from mystock.db import get_conn, etl_run

SYMBOL_KEYS = ("SYMBOL", "TckrSymb")


def parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


def daterange(start, end):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def symbol_of(row):
    for k in SYMBOL_KEYS:
        if k in row:
            return row[k].strip()
    return None


def fetch_day_rows(archives, trade_date):
    text = archives.bhavcopy_raw(trade_date)
    if text.lstrip().startswith("<"):
        return None  # NSE error/HTML page: no data for this date (holiday or unavailable)
    reader = csv.DictReader(io.StringIO(text))
    return [{k.strip(): v.strip() for k, v in row.items() if k} for row in reader]


def insert_rows(conn, trade_date, rows, batch_id):
    if not rows:
        return 0
    values = [
        (trade_date, symbol_of(row), json.dumps(row), "jugaad_data.bhavcopy", batch_id)
        for row in rows
    ]
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """INSERT INTO staging.nse_bhavcopy_raw
                   (trade_date, symbol, raw_payload, source, batch_id)
               VALUES %s
               ON CONFLICT (trade_date, symbol, source) DO NOTHING""",
            values,
        )
    conn.commit()
    return len(values)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", type=parse_date)
    ap.add_argument("--from-date", type=parse_date)
    ap.add_argument("--to-date", type=parse_date)
    args = ap.parse_args()

    if args.date:
        dates = [args.date]
    elif args.from_date and args.to_date:
        dates = list(daterange(args.from_date, args.to_date))
    else:
        dates = [date.today()]

    archives = NSEArchives()
    conn = get_conn()

    with etl_run("daily_bhavcopy", {"dates": [str(d) for d in (dates[:1] + dates[-1:])]}) as run:
        for d in dates:
            try:
                rows = fetch_day_rows(archives, d)
                if rows is None:
                    print(f"{d}: no data (holiday or unavailable)")
                    continue
                n = insert_rows(conn, d, rows, str(uuid.uuid4()))
                run["rows"] += n
                print(f"{d}: {n} rows")
            except Exception as e:
                print(f"{d}: FAILED - {e}", file=sys.stderr)

    conn.close()


if __name__ == "__main__":
    main()
