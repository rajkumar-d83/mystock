"""Daily/incremental load: whole-market bhavcopy via jugaad_data.bhavcopy_raw.

Only reliable from ~2019-10-01 onward — for dates before that, use
etl/historical/fetch_stock_history.py instead. One call covers the entire market for a
single day, so this is also the fast way to backfill 2019-10 through today once the
pre-2019 per-symbol backfill is done separately.

Every file is validated against the trading date stamped INSIDE it (BHAVDATA-FULL: DATE1,
UDIFF: TradDt) before it's stored. For a date with no file of its own (weekends,
holidays, or a weekday whose file isn't published yet) NSE's archive serves the most
recent file instead of an error, and without this check that stale file used to be filed
under the requested date -- duplicating Fridays under Sat/Sun and, with ON CONFLICT DO
NOTHING, permanently blocking the real session from ever loading. A date already loaded
is skipped (no download) unless --force, so a range is a cheap catch-up after missed runs.

Usage:
    python -m mystock.etl.daily.fetch_daily_bhavcopy --date 2026-07-14
    python -m mystock.etl.daily.fetch_daily_bhavcopy --from-date 2019-10-01 --to-date 2026-07-14
"""
import argparse
import csv
import io
import json
import sys
import time
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


def payload_trade_date(rows):
    """The trading date stamped inside the file itself, or None if it can't be read."""
    for row in rows:
        raw = row.get("TradDt") or row.get("DATE1")
        if not raw:
            continue
        for fmt in ("%Y-%m-%d", "%d-%b-%Y"):
            try:
                return datetime.strptime(raw, fmt).date()
            except ValueError:
                continue
    return None


def already_loaded_dates(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT trade_date FROM staging.nse_bhavcopy_raw")
        return {r[0] for r in cur.fetchall()}


def fetch_day_rows(archives, trade_date):
    text = archives.bhavcopy_raw(trade_date)
    if text.lstrip().startswith("<"):
        return None  # NSE error/HTML page: no data for this date (holiday or unavailable)
    reader = csv.DictReader(io.StringIO(text, newline=""))
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
    ap.add_argument("--sleep", type=float, default=0.3, help="seconds between dates in a range")
    ap.add_argument("--force", action="store_true", help="re-download dates that are already loaded")
    args = ap.parse_args()

    if args.date:
        dates = [args.date]
    elif args.from_date and args.to_date:
        dates = list(daterange(args.from_date, args.to_date))
    else:
        dates = [date.today()]

    archives = NSEArchives()
    conn = get_conn()
    loaded = set() if args.force else already_loaded_dates(conn)

    with etl_run("daily_bhavcopy", {"dates": [str(d) for d in (dates[:1] + dates[-1:])]}) as run:
        for d in dates:
            if d in loaded:
                if len(dates) == 1:
                    print(f"{d}: already loaded (use --force to re-download)")
                continue
            try:
                rows = fetch_day_rows(archives, d)
                if rows is None:
                    print(f"{d}: no data (holiday or unavailable)")
                    continue
                actual = payload_trade_date(rows)
                if actual != d:
                    print(f"{d}: no data (NSE served the {actual} file: weekend, holiday or not yet published)")
                    continue
                n = insert_rows(conn, d, rows, str(uuid.uuid4()))
                run["rows"] += n
                print(f"{d}: {n} rows")
            except Exception as e:
                print(f"{d}: FAILED - {e}", file=sys.stderr)
            if len(dates) > 1:
                time.sleep(args.sleep)

    conn.close()


if __name__ == "__main__":
    main()
