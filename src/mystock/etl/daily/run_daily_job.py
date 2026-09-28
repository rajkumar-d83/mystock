"""Daily incremental job: fetch a day's whole-market equity bhavcopy and index snapshot,
and (only on a genuine "today" run, not a --date backfill/reprocess) NIFTY Total Market
company fundamentals, validate they landed, then refresh Staging and Main. Idempotent —
safe to re-run for the same date, and safe to run even when there's no trading
(holidays/weekends just short-circuit after fetch).

Fundamentals are gated on `d == date.today()` specifically, not the --date argument,
because yfinance's snapshot has no concept of "give me the file as of date X" the way
NSE's bhavcopy does — it's always "right now". Running `--date 2026-07-10` to reprocess
an old day shouldn't also pull today's fundamentals as a side effect (see
MYSTOCK_PRODUCT_SPEC.md §7, Data Freshness).

Fundamentals: the .info snapshot (P/E, market cap, etc.) is re-fetched daily (not just
backfilled once) deliberately — several scoring inputs (PEG, P/E-vs-own-history, ownership
trend) need a real time series of snapshots, not a single point-in-time pull. The full
financial statements (income/balance/cashflow) and dividend history are quarterly-static,
so this job only pulls the snapshot (--mode snapshot); a separate weekly launchd job
(com.mystock.weeklyfundamentals) runs --mode full to refresh those.

The Staging/Main steps do a full idempotent re-run over all of staging/raw each time (not
just the new day) — simplest correct approach at current data volume. If that ever gets
too slow as the warehouse grows, revisit with an incremental watermark instead of a full
refresh.

F&O is out of scope for mystock (see MYSTOCK_PRODUCT_SPEC.md §4 Non-Goals) — no F&O fetch
step.

Quality scores are recomputed on every "today" run, right after data quality checks (see
MYSTOCK_PRODUCT_SPEC.md §9) — not on --date backfills, since they depend on the same
"right now" fundamentals snapshot as the fetch step above. Portfolio value/health run on
every day that has price data, not just "today" runs (both compute from the latest
OPENING_BALANCE holdings only, so they're cheap and don't depend on the day's
fundamentals/scores being current — see compute_portfolio_value_history.py for why
--date backfills should refresh them too).

News/sentiment (added Phase 5) is gated on is_today_run like fundamentals —
Google News RSS has no "as of date X" concept, it's always "right now", so a --date
backfill/reprocess shouldn't also pull today's news as a side effect. Scoped to
currently-held securities only (portfolio.transactions OPENING_BALANCE), not the whole
fundamentals universe — see fetch_news.py.

Sector signal + daily alert (added Phase 5) run on every day with price data, same as
portfolio value/health — both are derived purely from main.fact_daily_prices and
portfolio holdings, no "right now"-only dependency, so --date backfills should refresh
them too. The daily alert digest (portfolio.daily_alert) is the single table to query
each day for "does anything need my attention" — see compute_daily_alert.py.

Usage:
    python -m mystock.etl.daily.run_daily_job                    # today
    python -m mystock.etl.daily.run_daily_job --date 2026-07-10   # backfill/reprocess one date
"""
import argparse
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone

from mystock.db import get_conn, etl_run

PYTHON = sys.executable

# Price feeds are fetched for a trailing window, not just the run date: already-loaded dates are
# skipped (no download) and stale/holiday files are rejected by the loader, so this is cheap and
# self-heals runs the Mac slept through or days NSE hadn't published yet at 19:07.
CATCH_UP_DAYS = 7


def parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


def run_step(name, module):
    cmd = [PYTHON, "-m", module]
    print(f"--- {name}: {' '.join(cmd)}", flush=True)
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise RuntimeError(f"{name} failed with exit code {result.returncode}")


def run_step_with_args(name, module, extra_args):
    cmd = [PYTHON, "-m", module, *extra_args]
    print(f"--- {name}: {' '.join(cmd)}", flush=True)
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise RuntimeError(f"{name} failed with exit code {result.returncode}")


def equity_staging_row_count(conn, trade_date):
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM staging.nse_bhavcopy_raw WHERE trade_date = %s", (trade_date,))
        return cur.fetchone()[0]


def fundamentals_rows_inserted_since(conn, watermark):
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM staging.yf_company_snapshot_raw WHERE fetched_at >= %s", (watermark,))
        return cur.fetchone()[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", type=parse_date, default=date.today())
    args = ap.parse_args()
    d = args.date

    conn = get_conn()
    with etl_run("daily_job", {"date": str(d)}) as run:
        window = ["--from-date", str(d - timedelta(days=CATCH_UP_DAYS)), "--to-date", str(d)]
        run_step_with_args("fetch equity bhavcopy", "mystock.etl.daily.fetch_daily_bhavcopy", window)
        run_step_with_args("fetch indices bhavcopy", "mystock.etl.daily.fetch_indices_bhavcopy", window)

        is_today_run = d == date.today()
        fund_n = 0
        if is_today_run:
            fund_watermark = datetime.now(timezone.utc)
            run_step_with_args("fetch company fundamentals", "mystock.etl.historical.fetch_company_fundamentals", ["--mode", "snapshot"])
            fund_n = fundamentals_rows_inserted_since(conn, fund_watermark)

        eq_n = equity_staging_row_count(conn, d)
        print(f"validate: {eq_n} equity, {fund_n} fundamentals staging rows landed for {d}")
        if eq_n == 0 and fund_n == 0:
            print(f"No data for {d} (holiday/weekend, or not yet published) — skipping Staging/Main refresh.")
            run["rows"] = 0
        else:
            run_step("staging transform", "mystock.etl.staging.transform_all")
            run_step("main load", "mystock.etl.main.load_main")
            run_step("data quality checks", "mystock.etl.quality.run_data_quality_checks")
            if is_today_run:
                run_step("compute stock quality scores", "mystock.etl.main.compute_stock_quality_scores")
                run_step("fetch holdings news", "mystock.etl.daily.fetch_news")
                run_step("score news sentiment", "mystock.etl.staging.score_news_sentiment")
                run_step_with_args("compute news/price signal", "mystock.etl.main.compute_news_price_signal", ["--date", str(d)])
            run_step_with_args("compute portfolio value history", "mystock.etl.portfolio.compute_portfolio_value_history", ["--date", str(d)])
            run_step_with_args("compute portfolio health", "mystock.etl.portfolio.compute_portfolio_health", ["--date", str(d)])
            run_step_with_args("compute mtf interest", "mystock.etl.portfolio.compute_mtf_interest", ["--date", str(d)])
            run_step_with_args("compute sector signal", "mystock.etl.main.compute_sector_signal", ["--date", str(d)])
            run_step_with_args("compute daily alert", "mystock.etl.portfolio.compute_daily_alert", ["--date", str(d)])
            run["rows"] = eq_n + fund_n

    conn.close()
    print(f"Daily job complete for {d}.")


if __name__ == "__main__":
    main()
