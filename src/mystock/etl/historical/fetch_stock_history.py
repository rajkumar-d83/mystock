"""Historical backfill: per-symbol daily history via jugaad_data.stock_df.

This is the only route that reaches back past ~2019-10 — it's one request sequence per
symbol, not a whole-market file, so it's slower and must be polite to NSE's servers.

Runs in 2-year windows, newest-first (so the most useful recent history lands first).
Before each window, refreshes staging.nse_equity_master from NSE live and pulls the
current full symbol list from the DB — any symbol newly listed since the last window
is picked up automatically ("added on the go"), without restarting the whole job.

Resumable across restarts: a window already completed successfully (per
metadata.etl_runs) is skipped unless --force is passed. Within a window, jugaad_data's
own on-disk response cache (~/Library/Caches/nsehistory-stock) makes a restart cheap —
already-fetched (symbol, sub-range) calls are served from disk, not re-requested from NSE.
Row inserts are idempotent (ON CONFLICT DO NOTHING) regardless.

Usage:
    python -m mystock.etl.historical.fetch_stock_history
    python -m mystock.etl.historical.fetch_stock_history --batch-years 2 --sleep 0.5
    python -m mystock.etl.historical.fetch_stock_history --symbols-file etl/historical/symbols_nifty50.txt
"""
import argparse
import json
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

import psycopg2.extras
from jugaad_data.nse import stock_df

from mystock.db import get_conn, etl_run
from mystock.etl.historical.fetch_equity_master import refresh_equity_master

JOB_NAME = "historical_stock_history_batch"


def parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


def load_symbols_file(path):
    with open(path) as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


def load_symbols_from_db(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT symbol FROM staging.nse_equity_master ORDER BY symbol")
        return [r[0] for r in cur.fetchall()]


def subtract_years(d, years):
    try:
        return d.replace(year=d.year - years)
    except ValueError:  # Feb 29 on a non-leap target year
        return d.replace(month=2, day=28, year=d.year - years)


def build_windows(overall_from, overall_to, batch_years):
    """Newest-first list of (start, end) date windows spanning overall_from..overall_to."""
    windows = []
    end = overall_to
    while end > overall_from:
        start = subtract_years(end, batch_years) + timedelta(days=1)
        if start < overall_from:
            start = overall_from
        windows.append((start, end))
        end = start - timedelta(days=1)
    return windows


def window_already_done(conn, start, end):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT 1 FROM metadata.etl_runs
               WHERE job_name = %s AND status = 'success'
                 AND params->>'window_start' = %s AND params->>'window_end' = %s
               LIMIT 1""",
            (JOB_NAME, str(start), str(end)),
        )
        return cur.fetchone() is not None


def fetch_symbol_rows(symbol, from_date, to_date):
    df = stock_df(symbol=symbol, from_date=from_date, to_date=to_date, series="EQ")
    if df is None or df.empty:
        return []
    # jugaad_data's series filter isn't applied server-side — it returns other
    # series (AE, BE, ...) alongside EQ for the same dates. Filter explicitly so
    # staging gets one deterministic row per trade_date instead of whichever series
    # happened to win the ON CONFLICT race.
    df = df[df["SERIES"] == "EQ"]
    if df.empty:
        return []
    return json.loads(df.to_json(orient="records", date_format="iso"))


def fetch_symbol_rows_with_timeout(symbol, from_date, to_date, timeout_secs):
    """NSE occasionally hangs a connection indefinitely (observed: 9+ min stall on a
    single symbol, no exception raised) rather than erroring or timing out on its own.
    Bounds each symbol to timeout_secs of wall-clock time so one bad request can't stall
    the whole multi-hour run. The underlying thread is abandoned (not killed) on timeout —
    Python can't force-stop blocking I/O — but it's inert (blocked on a dead socket) and
    the process exits at the end of the run regardless."""
    ex = ThreadPoolExecutor(max_workers=1)
    future = ex.submit(fetch_symbol_rows, symbol, from_date, to_date)
    try:
        return future.result(timeout=timeout_secs)
    finally:
        ex.shutdown(wait=False)


def insert_rows(conn, symbol, records, source, batch_id):
    if not records:
        return 0
    values = [(symbol, rec["DATE"][:10], json.dumps(rec), source, batch_id) for rec in records]
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """INSERT INTO staging.nse_stock_history_raw
                   (symbol, trade_date, raw_payload, source, batch_id)
               VALUES %s
               ON CONFLICT (symbol, trade_date, source) DO NOTHING""",
            values,
        )
    conn.commit()
    return len(values)


def run_window(conn, start, end, symbols, sleep_secs, timeout_secs):
    batch_id = str(uuid.uuid4())
    total_rows = 0
    failures = []
    for i, symbol in enumerate(symbols, 1):
        try:
            records = fetch_symbol_rows_with_timeout(symbol, start, end, timeout_secs)
            n = insert_rows(conn, symbol, records, "jugaad_data.stock_df", batch_id)
            total_rows += n
            print(f"  [{i}/{len(symbols)}] {symbol}: {n} rows", flush=True)
        except Exception as e:
            failures.append(symbol)
            print(f"  [{i}/{len(symbols)}] {symbol}: FAILED - {e}", file=sys.stderr, flush=True)
        time.sleep(sleep_secs)
    return total_rows, failures


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols-file", help="if omitted, pulls the full list from staging.nse_equity_master")
    ap.add_argument("--from-date", type=parse_date, default=date(2016, 8, 3))
    ap.add_argument("--to-date", type=parse_date, default=date(2019, 9, 30))
    ap.add_argument("--batch-years", type=int, default=2)
    ap.add_argument("--sleep", type=float, default=0.5, help="seconds between symbols")
    ap.add_argument("--timeout", type=float, default=45.0, help="max seconds to wait per symbol before treating it as failed")
    ap.add_argument("--force", action="store_true", help="re-run windows already marked successful")
    args = ap.parse_args()

    conn = get_conn()
    windows = build_windows(args.from_date, args.to_date, args.batch_years)
    print(f"{len(windows)} windows, newest-first: {windows[0]} .. {windows[-1]}", flush=True)

    for start, end in windows:
        if not args.force and window_already_done(conn, start, end):
            print(f"=== window {start}..{end}: already done, skipping ===", flush=True)
            continue

        if args.symbols_file:
            symbols = load_symbols_file(args.symbols_file)
        else:
            total, new_symbols = refresh_equity_master(conn)
            if new_symbols:
                print(f"  equity master refresh: {total} symbols, {len(new_symbols)} new: {sorted(new_symbols)}", flush=True)
            symbols = load_symbols_from_db(conn)

        print(f"=== window {start}..{end}: {len(symbols)} symbols ===", flush=True)
        with etl_run(JOB_NAME, {"window_start": str(start), "window_end": str(end), "symbols": len(symbols)}) as run:
            rows, failures = run_window(conn, start, end, symbols, args.sleep, args.timeout)
            run["rows"] = rows
        print(f"=== window {start}..{end} done: {rows} rows, {len(failures)} symbol failures ===", flush=True)

    conn.close()


if __name__ == "__main__":
    main()
