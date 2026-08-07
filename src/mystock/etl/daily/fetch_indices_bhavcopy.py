"""Fetches NSE's whole-market index closing snapshot (all indices — NIFTY 50, NIFTY 500,
sector indices — plus each index's own P/E/P/B/dividend yield) from niftyindices.com's
static daily archive. Powers Relative Strength scoring and sector-level valuation
comparison (see MYSTOCK_PRODUCT_SPEC.md §9, Market Behaviour category).

Usage:
    python -m mystock.etl.daily.fetch_indices_bhavcopy --date 2026-07-14
    python -m mystock.etl.daily.fetch_indices_bhavcopy --from-date 2019-01-01 --to-date 2026-07-14
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
from jugaad_data.nse import NSEIndicesArchives

from mystock.db import get_conn, etl_run


def parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


def daterange(start, end):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def fetch_day(archives, trade_date):
    url = f"https://www.niftyindices.com/Daily_Snapshot/ind_close_all_{trade_date.strftime('%d%m%Y')}.csv"
    resp = archives.s.get(url, timeout=15)
    if resp.status_code != 200 or not resp.text.strip():
        return None
    reader = csv.DictReader(io.StringIO(resp.text))
    rows = [{k.strip(): v.strip() for k, v in row.items() if k} for row in reader]
    return rows or None


def already_loaded_dates(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT trade_date FROM staging.nse_indices_bhavcopy_raw")
        return {r[0] for r in cur.fetchall()}


def insert_rows(conn, trade_date, rows, batch_id):
    if not rows:
        return 0
    values = [(trade_date, row.get("Index Name"), json.dumps(row), batch_id) for row in rows if row.get("Index Name")]
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """INSERT INTO staging.nse_indices_bhavcopy_raw (trade_date, index_name, raw_payload, batch_id)
               VALUES %s
               ON CONFLICT (trade_date, index_name, source) DO NOTHING""",
            values,
        )
    conn.commit()
    return len(values)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", type=parse_date)
    ap.add_argument("--from-date", type=parse_date)
    ap.add_argument("--to-date", type=parse_date)
    ap.add_argument("--sleep", type=float, default=0.2)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    if args.date:
        dates = [args.date]
    elif args.from_date and args.to_date:
        dates = list(daterange(args.from_date, args.to_date))
    else:
        dates = [date.today()]

    conn = get_conn()
    if not args.force:
        loaded = already_loaded_dates(conn)
        before = len(dates)
        dates = [d for d in dates if d not in loaded]
        if before != len(dates):
            print(f"Skipping {before - len(dates)} dates already loaded (pass --force to re-fetch)", flush=True)

    archives = NSEIndicesArchives()
    with etl_run("indices_bhavcopy", {"dates": [str(dates[0]), str(dates[-1])] if dates else []}) as run:
        for d in dates:
            try:
                rows = fetch_day(archives, d)
                if rows is None:
                    print(f"{d}: no data (holiday/weekend/unavailable)", flush=True)
                else:
                    n = insert_rows(conn, d, rows, str(uuid.uuid4()))
                    run["rows"] += n
                    print(f"{d}: {n} index rows", flush=True)
            except Exception as e:
                print(f"{d}: FAILED - {e}", file=sys.stderr, flush=True)
            time.sleep(args.sleep)

    conn.close()


if __name__ == "__main__":
    main()
