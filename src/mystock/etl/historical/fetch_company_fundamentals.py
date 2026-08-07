"""Fetches company fundamentals (P/E, debt, revenue, dividends, etc.) for the NIFTY Total
Market Index constituent list, via Yahoo Finance (yfinance, .NS suffix). NSE's own live
quote API (which shows the same ratios on their website) is blocked to scripted access by
their anti-bot protection — this is the practical alternative.

Data quality note: yfinance's India coverage is noticeably weaker below NIFTY 500 (many
small-caps are thinly traded or SME-platform-adjacent) — expect a higher missing/incomplete-
fundamentals rate for that tail, surfaced via data_completeness_pct in
main.fact_stock_quality_score.

Two modes, since these fields change on very different cadences (one HTTP call per symbol
either way — the cost is in count of symbols, not in what's pulled per symbol):
  --mode snapshot (daily): just the price-derived .info ratios (P/E, market cap, etc.) —
      these genuinely move every day, and several quality-score inputs (PEG, P/E-vs-own-
      history, ownership trend) need a real time series of daily snapshots, not one point.
  --mode full (weekly): snapshot + annual/quarterly financials (income statement, balance
      sheet, cash flow) + full dividend history — these only change when a company files a
      new quarterly/annual statement or declares a dividend, so daily re-fetching them was
      pure wasted cost (see run_daily_job.py for the daily wiring; a separate weekly
      launchd job runs --mode full).

Staging stores everything raw as JSONB (schema-on-read) — only a curated subset of the
highest-value fields get typed columns downstream in Main.

Usage:
    python -m mystock.etl.historical.fetch_company_fundamentals --mode snapshot
    python -m mystock.etl.historical.fetch_company_fundamentals --mode full
    python -m mystock.etl.historical.fetch_company_fundamentals --mode full --symbols-file path/to/list.txt
"""
import argparse
import json
import sys
import time
import uuid
from datetime import date

import psycopg2.extras
import yfinance as yf
from jugaad_data.nse import NSEArchives

from mystock.db import get_conn, etl_run

NIFTY_TOTAL_MARKET_LIST_URL = "https://nsearchives.nseindia.com/content/indices/ind_niftytotalmarket_list.csv"


def fetch_nifty_total_market_symbols():
    import csv
    import io
    archives = NSEArchives()
    resp = archives.s.get(NIFTY_TOTAL_MARKET_LIST_URL, timeout=15)
    resp.raise_for_status()
    reader = csv.DictReader(io.StringIO(resp.text))
    return [row["Symbol"].strip() for row in reader]


def insert_snapshot(conn, symbol, info, batch_id):
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO staging.yf_company_snapshot_raw (symbol, snapshot_date, raw_payload, batch_id)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (symbol, snapshot_date) DO UPDATE
                   SET raw_payload = EXCLUDED.raw_payload, batch_id = EXCLUDED.batch_id, fetched_at = now()""",
            (symbol, date.today(), json.dumps(info, default=str), batch_id),
        )
    conn.commit()


def insert_financials(conn, symbol, statement_type, period_type, df, batch_id):
    if df is None or df.empty:
        return 0
    values = []
    for col in df.columns:
        period_end = col.date() if hasattr(col, "date") else col
        payload = {k: v for k, v in df[col].dropna().to_dict().items()}
        values.append((symbol, statement_type, period_type, period_end, json.dumps(payload, default=str), batch_id))
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """INSERT INTO staging.yf_financials_raw
                   (symbol, statement_type, period_type, period_end_date, raw_payload, batch_id)
               VALUES %s
               ON CONFLICT (symbol, statement_type, period_type, period_end_date) DO UPDATE
                   SET raw_payload = EXCLUDED.raw_payload, batch_id = EXCLUDED.batch_id, fetched_at = now()""",
            values,
        )
    conn.commit()
    return len(values)


def insert_dividends(conn, symbol, dividends, batch_id):
    if dividends is None or dividends.empty:
        return 0
    values = [(symbol, idx.date(), float(val), batch_id) for idx, val in dividends.items()]
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """INSERT INTO staging.yf_dividends_raw (symbol, ex_date, dividend, batch_id)
               VALUES %s
               ON CONFLICT (symbol, ex_date) DO UPDATE
                   SET dividend = EXCLUDED.dividend, batch_id = EXCLUDED.batch_id, fetched_at = now()""",
            values,
        )
    conn.commit()
    return len(values)


def fetch_one_symbol(conn, symbol, batch_id, mode):
    t = yf.Ticker(f"{symbol}.NS")
    total_rows = 0

    info = t.info
    if info:
        insert_snapshot(conn, symbol, info, batch_id)
        total_rows += 1

    if mode == "full":
        for statement_type, annual_df, quarterly_df in [
            ("income", t.financials, t.quarterly_financials),
            ("balance", t.balance_sheet, t.quarterly_balance_sheet),
            ("cashflow", t.cashflow, t.quarterly_cashflow),
        ]:
            total_rows += insert_financials(conn, symbol, statement_type, "annual", annual_df, batch_id)
            total_rows += insert_financials(conn, symbol, statement_type, "quarterly", quarterly_df, batch_id)

        total_rows += insert_dividends(conn, symbol, t.dividends, batch_id)

    return total_rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["snapshot", "full"], default="full",
                     help="snapshot = .info only (daily); full = snapshot + financials + dividends (weekly)")
    ap.add_argument("--symbols-file", help="if omitted, uses the NIFTY Total Market constituent list")
    ap.add_argument("--sleep", type=float, default=0.5, help="seconds between symbols")
    args = ap.parse_args()

    if args.symbols_file:
        with open(args.symbols_file) as f:
            symbols = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    else:
        symbols = fetch_nifty_total_market_symbols()

    print(f"{len(symbols)} symbols to fetch (mode={args.mode})", flush=True)
    conn = get_conn()
    batch_id = str(uuid.uuid4())

    with etl_run(f"historical_company_fundamentals_{args.mode}", {"symbols": len(symbols)}) as run:
        for i, symbol in enumerate(symbols, 1):
            try:
                n = fetch_one_symbol(conn, symbol, batch_id, args.mode)
                run["rows"] += n
                print(f"[{i}/{len(symbols)}] {symbol}: {n} rows", flush=True)
            except Exception as e:
                print(f"[{i}/{len(symbols)}] {symbol}: FAILED - {e}", file=sys.stderr, flush=True)
            time.sleep(args.sleep)

    conn.close()


if __name__ == "__main__":
    main()
