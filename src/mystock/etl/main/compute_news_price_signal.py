"""Computes the news/price correlation signal for currently-held securities: is a day's
price move larger than that stock's own recent volatility would suggest (a z-score
against trailing 20-trading-day returns, not just "price went down"), and is that move
corroborated by news sentiment that day.

signal_type:
  negative_sentiment_selloff  - abnormal drop + negative news that day (the "consider
                                 buying the dip, if you still believe the business case"
                                 signal)
  unusual_drop_no_bad_news    - abnormal drop, no corroborating negative news (likely
                                 market-wide/technical, less clear-cut)
  positive_sentiment_breakout - abnormal rise + positive news
  normal                      - no abnormal move

Z-score threshold and sentiment threshold are deliberately simple/transparent (not
fitted) — this is a screening flag to prompt a manual look, not a trading signal to act
on blindly.

Also writes main.fact_news_sentiment_daily (per-security daily news aggregation) as a
byproduct, since the signal computation needs it anyway.

Usage:
    python -m mystock.etl.main.compute_news_price_signal                    # today only
    python -m mystock.etl.main.compute_news_price_signal --backfill-days 30 # last 30 trading days
"""
import argparse
import statistics
from datetime import date, datetime

from mystock.db import get_conn

TRAILING_WINDOW = 20
ZSCORE_THRESHOLD = 1.5
SENTIMENT_THRESHOLD = 0.10
MIN_TRAILING_OBS = 10


def current_holdings(conn):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT DISTINCT security_key FROM portfolio.transactions
               WHERE transaction_type = 'OPENING_BALANCE'"""
        )
        return [r[0] for r in cur.fetchall()]


def price_history(conn, security_key, lookback_days=TRAILING_WINDOW + 60):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT dd.full_date, dd.date_key, fdp.close
               FROM main.fact_daily_prices fdp
               JOIN main.dim_date dd ON dd.date_key = fdp.date_key
               WHERE fdp.security_key = %s
               ORDER BY dd.full_date DESC LIMIT %s""",
            (security_key, lookback_days),
        )
        rows = cur.fetchall()[::-1]  # ascending
        return rows


def daily_sentiment(conn, security_key, target_date):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT count(*), avg(sentiment_score),
                      count(*) FILTER (WHERE sentiment_label='positive'),
                      count(*) FILTER (WHERE sentiment_label='negative'),
                      count(*) FILTER (WHERE sentiment_label='neutral')
               FROM staging.news_sentiment
               WHERE security_key = %s AND published_at::date = %s""",
            (security_key, target_date),
        )
        return cur.fetchone()


def write_sentiment_daily(conn, security_key, target_date, news_count, avg_score, pos, neg, neu):
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO main.fact_news_sentiment_daily
                   (security_key, date_key, news_count, avg_sentiment_score, positive_count, negative_count, neutral_count)
               SELECT %s, dd.date_key, %s, %s, %s, %s, %s
               FROM main.dim_date dd WHERE dd.full_date = %s
               ON CONFLICT (security_key, date_key) DO UPDATE SET
                   news_count = EXCLUDED.news_count, avg_sentiment_score = EXCLUDED.avg_sentiment_score,
                   positive_count = EXCLUDED.positive_count, negative_count = EXCLUDED.negative_count,
                   neutral_count = EXCLUDED.neutral_count, computed_at = now()""",
            (security_key, news_count, avg_score, pos, neg, neu, target_date),
        )


def classify_signal(return_pct, zscore, avg_sentiment, news_count):
    if zscore is None or abs(zscore) < ZSCORE_THRESHOLD:
        return "normal", False
    if return_pct < 0:
        if news_count > 0 and avg_sentiment is not None and avg_sentiment <= -SENTIMENT_THRESHOLD:
            return "negative_sentiment_selloff", True
        return "unusual_drop_no_bad_news", True
    if news_count > 0 and avg_sentiment is not None and avg_sentiment >= SENTIMENT_THRESHOLD:
        return "positive_sentiment_breakout", True
    return "normal", False


def write_signal(conn, security_key, target_date, return_pct, zscore, avg_sentiment, news_count, signal_type, flagged):
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO main.fact_price_sentiment_signal
                   (security_key, date_key, daily_return_pct, return_zscore, avg_sentiment_score,
                    news_count, signal_type, flagged)
               SELECT %s, dd.date_key, %s, %s, %s, %s, %s, %s
               FROM main.dim_date dd WHERE dd.full_date = %s
               ON CONFLICT (security_key, date_key) DO UPDATE SET
                   daily_return_pct = EXCLUDED.daily_return_pct, return_zscore = EXCLUDED.return_zscore,
                   avg_sentiment_score = EXCLUDED.avg_sentiment_score, news_count = EXCLUDED.news_count,
                   signal_type = EXCLUDED.signal_type, flagged = EXCLUDED.flagged, computed_at = now()""",
            (security_key, return_pct, zscore, avg_sentiment, news_count, signal_type, flagged, target_date),
        )


def process_security(conn, security_key, target_dates):
    history = price_history(conn, security_key)
    if len(history) < MIN_TRAILING_OBS + 1:
        return 0

    returns_by_date = {}
    for i in range(1, len(history)):
        prev_close, close = float(history[i - 1][2]), float(history[i][2])
        if prev_close:
            returns_by_date[history[i][0]] = 100.0 * (close - prev_close) / prev_close

    dates_sorted = [h[0] for h in history]
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

        news_count, avg_score, pos, neg, neu = daily_sentiment(conn, security_key, target_date)
        avg_score = float(avg_score) if avg_score is not None else None
        write_sentiment_daily(conn, security_key, target_date, news_count, avg_score, pos, neg, neu)

        signal_type, flagged = classify_signal(today_return, zscore, avg_score, news_count)
        write_signal(conn, security_key, target_date, today_return, zscore, avg_score, news_count, signal_type, flagged)
        computed += 1

    return computed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(), default=date.today())
    ap.add_argument("--backfill-days", type=int, default=1, help="number of recent trading days to (re)compute")
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

    holdings = current_holdings(conn)
    print(f"{len(holdings)} holdings, {len(target_dates)} target date(s)", flush=True)

    total_computed = flagged_total = 0
    for security_key in holdings:
        n = process_security(conn, security_key, target_dates)
        conn.commit()
        total_computed += n

    with conn.cursor() as cur:
        cur.execute(
            """SELECT count(*) FROM main.fact_price_sentiment_signal s
               JOIN main.dim_date dd ON dd.date_key = s.date_key
               WHERE dd.full_date = ANY(%s) AND s.flagged = true""",
            (list(target_dates),),
        )
        flagged_total = cur.fetchone()[0]

    conn.close()
    print(f"Done. {total_computed} security-days computed, {flagged_total} flagged.")


if __name__ == "__main__":
    main()
