"""Compiles the daily portfolio alert: portfolio value change + every stock-level signal
(mystock.etl.main.compute_news_price_signal) and sector-level signal
(mystock.etl.main.compute_sector_signal) flagged that day, into one row with a
plain-English summary in portfolio.daily_alert. Query this table each day rather than
checking three separate signal tables — delivery is query-based, not a push notification,
by design (see MYSTOCK_PRODUCT_SPEC.md §10).

Usage:
    python -m mystock.etl.portfolio.compute_daily_alert                  # today, all portfolios
    python -m mystock.etl.portfolio.compute_daily_alert --date 2026-08-03
"""
import argparse
from datetime import date, datetime

from mystock.db import get_conn


def portfolio_value_change(conn, portfolio_id, target_date):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT dd.full_date, v.market_value FROM portfolio.fact_portfolio_value_daily v
               JOIN main.dim_date dd ON dd.date_key = v.date_key
               WHERE v.portfolio_id = %s AND dd.full_date <= %s
               ORDER BY dd.full_date DESC LIMIT 2""",
            (portfolio_id, target_date),
        )
        rows = cur.fetchall()
    if len(rows) < 2:
        return None, None, None
    (today_date, today_val), (_, prev_val) = rows
    if today_date != target_date or not prev_val:
        return None, None, None
    change_abs = float(today_val) - float(prev_val)
    change_pct = 100.0 * change_abs / float(prev_val)
    return float(today_val), change_abs, change_pct


def stock_signals(conn, portfolio_id, target_date):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT d.symbol, s.daily_return_pct, s.return_zscore, s.signal_type
               FROM main.fact_price_sentiment_signal s
               JOIN main.dim_security d ON d.security_key = s.security_key
               JOIN main.dim_date dd ON dd.date_key = s.date_key
               WHERE dd.full_date = %s AND s.flagged = true
                 AND s.security_key IN (
                     SELECT DISTINCT security_key FROM portfolio.transactions
                     WHERE portfolio_id = %s AND transaction_type = 'OPENING_BALANCE')
               ORDER BY abs(s.return_zscore) DESC""",
            (target_date, portfolio_id),
        )
        return cur.fetchall()


def sector_signals(conn, portfolio_id, target_date):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT sec.industry, s.avg_return_pct, s.return_zscore, s.num_holdings,
                      array_agg(DISTINCT d.symbol) AS symbols
               FROM main.fact_sector_signal s
               JOIN main.dim_sector sec ON sec.sector_key = s.sector_key
               JOIN main.dim_date dd ON dd.date_key = s.date_key
               JOIN main.dim_security d ON d.sector_key = s.sector_key
               JOIN portfolio.transactions t ON t.security_key = d.security_key
                    AND t.portfolio_id = %s AND t.transaction_type = 'OPENING_BALANCE'
               WHERE dd.full_date = %s AND s.flagged = true
               GROUP BY sec.industry, s.avg_return_pct, s.return_zscore, s.num_holdings
               ORDER BY abs(s.return_zscore) DESC""",
            (portfolio_id, target_date),
        )
        return cur.fetchall()


def build_summary(portfolio_name, value, change_abs, change_pct, stocks, sectors):
    parts = []
    if value is not None:
        direction = "+" if change_abs >= 0 else ""
        parts.append(f"{portfolio_name}: Rs {value:,.0f} ({direction}{change_pct:.2f}% / {direction}Rs {change_abs:,.0f} today)")
    else:
        parts.append(f"{portfolio_name}: no prior-day value to compare")

    if stocks:
        stock_bits = [f"{sym} ({ret:+.1f}%, {sig})" for sym, ret, z, sig in stocks]
        parts.append(f"{len(stocks)} holding(s) flagged: " + "; ".join(stock_bits))
    else:
        parts.append("No individual holdings flagged today")

    if sectors:
        sector_bits = [
            f"{ind} ({ret:+.1f}% avg across {n} holdings: {', '.join(syms)})"
            for ind, ret, z, n, syms in sectors
        ]
        parts.append(f"{len(sectors)} sector(s) flagged: " + "; ".join(sector_bits))
    else:
        parts.append("No sector-wide moves flagged today")

    return " | ".join(parts)


def write_alert(conn, portfolio_id, target_date, value_change_abs, value_change_pct, stock_count, sector_count, summary):
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO portfolio.daily_alert
                   (portfolio_id, date_key, portfolio_value_change_pct, portfolio_value_change_abs,
                    stock_signals_count, sector_signals_count, summary)
               SELECT %s, dd.date_key, %s, %s, %s, %s, %s
               FROM main.dim_date dd WHERE dd.full_date = %s
               ON CONFLICT (portfolio_id, date_key) DO UPDATE SET
                   portfolio_value_change_pct = EXCLUDED.portfolio_value_change_pct,
                   portfolio_value_change_abs = EXCLUDED.portfolio_value_change_abs,
                   stock_signals_count = EXCLUDED.stock_signals_count,
                   sector_signals_count = EXCLUDED.sector_signals_count,
                   summary = EXCLUDED.summary, computed_at = now()""",
            (portfolio_id, value_change_pct, value_change_abs, stock_count, sector_count, summary, target_date),
        )
    conn.commit()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(), default=date.today())
    ap.add_argument("--portfolio-id", type=int, default=None)
    args = ap.parse_args()

    conn = get_conn()
    with conn.cursor() as cur:
        if args.portfolio_id:
            cur.execute("SELECT portfolio_id, portfolio_name FROM portfolio.portfolios WHERE portfolio_id = %s", (args.portfolio_id,))
        else:
            cur.execute("SELECT portfolio_id, portfolio_name FROM portfolio.portfolios")
        portfolios = cur.fetchall()

    for portfolio_id, name in portfolios:
        value, change_abs, change_pct = portfolio_value_change(conn, portfolio_id, args.date)
        stocks = stock_signals(conn, portfolio_id, args.date)
        sectors = sector_signals(conn, portfolio_id, args.date)
        summary = build_summary(name, value, change_abs, change_pct, stocks, sectors)
        write_alert(conn, portfolio_id, args.date, change_abs, change_pct, len(stocks), len(sectors), summary)
        print(f"[{args.date}] {summary}")

    conn.close()


if __name__ == "__main__":
    main()
