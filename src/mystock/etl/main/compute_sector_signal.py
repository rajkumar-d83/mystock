"""Computes the sector-level signal: is a sector (containing 2+ currently-held stocks)
moving abnormally as a group today, using the same z-score-vs-own-trailing-20-day-history
approach as compute_news_price_signal.py, applied to the equal-weighted average
daily return across that sector's held stocks. Complements the single-stock signal —
catches sector-wide moves (e.g. a commodity shock hitting Metals & Mining broadly) that
no single stock's own news would explain.

Usage:
    python -m mystock.etl.main.compute_sector_signal                    # today only
    python -m mystock.etl.main.compute_sector_signal --backfill-days 30
"""
import argparse
import statistics
from datetime import date, datetime

from mystock.db import get_conn

TRAILING_WINDOW = 20
ZSCORE_THRESHOLD = 1.5
MIN_TRAILING_OBS = 10
MIN_HOLDINGS_PER_SECTOR = 2


def sectors_with_multiple_holdings(conn):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT d.sector_key, array_agg(DISTINCT d.security_key) AS security_keys
               FROM portfolio.transactions t
               JOIN main.dim_security d ON d.security_key = t.security_key
               WHERE t.transaction_type = 'OPENING_BALANCE' AND d.sector_key IS NOT NULL
               GROUP BY d.sector_key
               HAVING count(DISTINCT d.security_key) >= %s""",
            (MIN_HOLDINGS_PER_SECTOR,),
        )
        return cur.fetchall()


def sector_daily_returns(conn, security_keys, lookback_days=TRAILING_WINDOW + 60):
    """Equal-weighted average daily return % across the given securities, per date."""
    with conn.cursor() as cur:
        cur.execute(
            """WITH px AS (
                   SELECT dd.full_date, fdp.security_key, fdp.close,
                          lag(fdp.close) OVER (PARTITION BY fdp.security_key ORDER BY dd.full_date) AS prev_close
                   FROM main.fact_daily_prices fdp
                   JOIN main.dim_date dd ON dd.date_key = fdp.date_key
                   WHERE fdp.security_key = ANY(%s)
                     AND dd.full_date >= (SELECT max(dd2.full_date) FROM main.dim_date dd2
                                          JOIN main.fact_daily_prices p2 ON p2.date_key = dd2.date_key) - (%s || ' days')::interval
               )
               SELECT full_date, avg(100.0 * (close - prev_close) / NULLIF(prev_close, 0)) AS avg_return_pct
               FROM px WHERE prev_close IS NOT NULL
               GROUP BY full_date ORDER BY full_date""",
            (security_keys, lookback_days),
        )
        return cur.fetchall()  # [(date, avg_return_pct), ...] ascending


def write_signal(conn, sector_key, target_date, avg_return, zscore, num_holdings, flagged):
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO main.fact_sector_signal
                   (sector_key, date_key, avg_return_pct, return_zscore, num_holdings, flagged)
               SELECT %s, dd.date_key, %s, %s, %s, %s
               FROM main.dim_date dd WHERE dd.full_date = %s
               ON CONFLICT (sector_key, date_key) DO UPDATE SET
                   avg_return_pct = EXCLUDED.avg_return_pct, return_zscore = EXCLUDED.return_zscore,
                   num_holdings = EXCLUDED.num_holdings, flagged = EXCLUDED.flagged, computed_at = now()""",
            (sector_key, avg_return, zscore, num_holdings, flagged, target_date),
        )


def process_sector(conn, sector_key, security_keys, target_dates):
    returns = sector_daily_returns(conn, security_keys)
    if len(returns) < MIN_TRAILING_OBS + 1:
        return 0
    dates_sorted = [r[0] for r in returns]
    returns_by_date = {r[0]: float(r[1]) for r in returns if r[1] is not None}

    computed = 0
    for target_date in target_dates:
        if target_date not in returns_by_date or target_date not in dates_sorted:
            continue
        idx = dates_sorted.index(target_date)
        trailing_dates = dates_sorted[max(0, idx - TRAILING_WINDOW):idx]
        trailing_returns = [returns_by_date[d] for d in trailing_dates if d in returns_by_date]
        if len(trailing_returns) < MIN_TRAILING_OBS:
            continue

        mean_r = statistics.mean(trailing_returns)
        stdev_r = statistics.stdev(trailing_returns) if len(trailing_returns) > 1 else 0
        today_return = returns_by_date[target_date]
        zscore = (today_return - mean_r) / stdev_r if stdev_r > 0 else None
        flagged = zscore is not None and abs(zscore) >= ZSCORE_THRESHOLD

        write_signal(conn, sector_key, target_date, today_return, zscore, len(security_keys), flagged)
        computed += 1
    return computed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(), default=date.today())
    ap.add_argument("--backfill-days", type=int, default=1)
    args = ap.parse_args()

    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """SELECT full_date FROM main.dim_date
               WHERE full_date <= %s AND EXISTS (SELECT 1 FROM main.fact_daily_prices p WHERE p.date_key = dim_date.date_key)
               ORDER BY full_date DESC LIMIT %s""",
            (args.date, args.backfill_days),
        )
        target_dates = set(r[0] for r in cur.fetchall())

    sectors = sectors_with_multiple_holdings(conn)
    print(f"{len(sectors)} sectors with >= {MIN_HOLDINGS_PER_SECTOR} holdings, {len(target_dates)} target date(s)", flush=True)

    total_computed = 0
    for sector_key, security_keys in sectors:
        n = process_sector(conn, sector_key, security_keys, target_dates)
        conn.commit()
        total_computed += n

    with conn.cursor() as cur:
        cur.execute(
            """SELECT count(*) FROM main.fact_sector_signal s
               JOIN main.dim_date dd ON dd.date_key = s.date_key
               WHERE dd.full_date = ANY(%s) AND s.flagged = true""",
            (list(target_dates),),
        )
        flagged_total = cur.fetchone()[0]

    conn.close()
    print(f"Done. {total_computed} sector-days computed, {flagged_total} flagged.")


if __name__ == "__main__":
    main()
