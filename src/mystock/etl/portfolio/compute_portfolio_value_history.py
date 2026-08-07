"""Computes one day's portfolio value snapshot (portfolio.fact_portfolio_value_daily) per
portfolio, from the latest OPENING_BALANCE holdings only.

Design note: current holdings/cost-basis always come from the most recent
OPENING_BALANCE row per security/scheme, never summed with BUY/SELL trade rows — see
MYSTOCK_PRODUCT_SPEC.md's "store facts once" design principle. Summing OPENING_BALANCE
with trades would double-count. Trade-derived realized P&L is tracked separately from the
value snapshot's cost basis/unrealized P&L.

Cumulative dividends and realized P&L are only counted from the OPENING_BALANCE's own
date forward — we don't know how long the current position was actually held before
that date, so counting earlier dividends/trades would overstate what's attributable to
the current holding. This is a known limitation of snapshot-seeded (rather than
full-history) portfolios; it means the value/dividend trend starts thin and builds up
correctly only from here on, the same way main.fact_stock_quality_score builds a real
trend one daily run at a time rather than being backfilled.

Usage:
    python -m mystock.etl.portfolio.compute_portfolio_value_history                  # today, all portfolios
    python -m mystock.etl.portfolio.compute_portfolio_value_history --date 2026-08-03
    python -m mystock.etl.portfolio.compute_portfolio_value_history --portfolio-id 1
"""
import argparse
from datetime import date, datetime

from mystock.db import get_conn


def latest_trading_date_on_or_before(conn, target_date):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT max(dd.full_date) FROM main.dim_date dd
               WHERE dd.full_date <= %s
                 AND EXISTS (SELECT 1 FROM main.fact_daily_prices p WHERE p.date_key = dd.date_key)""",
            (target_date,),
        )
        return cur.fetchone()[0]


def compute_equity_value(conn, portfolio_id, as_of):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT t.security_key, t.quantity, t.price, t.transaction_date
               FROM portfolio.transactions t
               WHERE t.portfolio_id = %s AND t.transaction_type = 'OPENING_BALANCE'""",
            (portfolio_id,),
        )
        holdings = cur.fetchall()

        market_value = cost_basis = 0.0
        rows = []
        for security_key, qty, avg_price, ob_date in holdings:
            qty, avg_price = float(qty), float(avg_price)
            cur.execute(
                """SELECT fdp.close FROM main.fact_daily_prices fdp
                   JOIN main.dim_date dd ON dd.date_key = fdp.date_key
                   WHERE fdp.security_key = %s AND dd.full_date <= %s
                   ORDER BY dd.full_date DESC LIMIT 1""",
                (security_key, as_of),
            )
            price_row = cur.fetchone()
            close = float(price_row[0]) if price_row else avg_price
            market_value += qty * close
            cost_basis += qty * avg_price
            rows.append((security_key, qty, ob_date))

        cur.execute(
            """SELECT coalesce(sum(fcd.dividend), 0)
               FROM portfolio.transactions t
               JOIN main.fact_company_dividends fcd ON fcd.security_key = t.security_key
               JOIN main.dim_date dd ON dd.date_key = fcd.ex_date_key
               WHERE t.portfolio_id = %s AND t.transaction_type = 'OPENING_BALANCE'
                 AND dd.full_date > t.transaction_date AND dd.full_date <= %s""",
            (portfolio_id, as_of),
        )
        per_share_div_total = cur.fetchone()[0]
        cash_dividends = 0.0
        for security_key, qty, ob_date in rows:
            cur.execute(
                """SELECT coalesce(sum(fcd.dividend), 0)
                   FROM main.fact_company_dividends fcd
                   JOIN main.dim_date dd ON dd.date_key = fcd.ex_date_key
                   WHERE fcd.security_key = %s AND dd.full_date > %s AND dd.full_date <= %s""",
                (security_key, ob_date, as_of),
            )
            cash_dividends += qty * float(cur.fetchone()[0])

        cur.execute(
            """SELECT coalesce(sum(CASE WHEN transaction_type='SELL' THEN quantity*price ELSE -quantity*price END), 0)
               FROM portfolio.transactions
               WHERE portfolio_id = %s AND transaction_type IN ('BUY','SELL') AND transaction_date <= %s""",
            (portfolio_id, as_of),
        )
        realized_pnl = float(cur.fetchone()[0])

    return market_value, cost_basis, cash_dividends, realized_pnl


def compute_mf_value(conn, portfolio_id, as_of):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT scheme_key, units, price FROM portfolio.mf_transactions
               WHERE portfolio_id = %s AND transaction_type = 'OPENING_BALANCE'""",
            (portfolio_id,),
        )
        holdings = cur.fetchall()

        market_value = cost_basis = 0.0
        for scheme_key, units, avg_price in holdings:
            units, avg_price = float(units), float(avg_price)
            cur.execute(
                """SELECT nav FROM main.fact_mf_nav_daily fmnd
                   JOIN main.dim_date dd ON dd.date_key = fmnd.date_key
                   WHERE fmnd.scheme_key = %s AND dd.full_date <= %s
                   ORDER BY dd.full_date DESC LIMIT 1""",
                (scheme_key, as_of),
            )
            nav_row = cur.fetchone()
            nav = float(nav_row[0]) if nav_row else avg_price
            market_value += units * nav
            cost_basis += units * avg_price

    return market_value, cost_basis


def write_snapshot(conn, portfolio_id, as_of, market_value, cost_basis, cash_dividends, realized_pnl):
    unrealized_pnl = market_value - cost_basis
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO portfolio.fact_portfolio_value_daily
                   (portfolio_id, date_key, market_value, cost_basis, cash_dividends_received,
                    unrealized_pnl, realized_pnl)
               SELECT %s, dd.date_key, %s, %s, %s, %s, %s
               FROM main.dim_date dd WHERE dd.full_date = %s
               ON CONFLICT (portfolio_id, date_key) DO UPDATE SET
                   market_value = EXCLUDED.market_value, cost_basis = EXCLUDED.cost_basis,
                   cash_dividends_received = EXCLUDED.cash_dividends_received,
                   unrealized_pnl = EXCLUDED.unrealized_pnl, realized_pnl = EXCLUDED.realized_pnl""",
            (portfolio_id, market_value, cost_basis, cash_dividends, unrealized_pnl, realized_pnl, as_of),
        )
    conn.commit()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(), default=date.today())
    ap.add_argument("--portfolio-id", type=int, default=None)
    args = ap.parse_args()

    conn = get_conn()
    as_of = latest_trading_date_on_or_before(conn, args.date)
    if as_of is None:
        print(f"No price data on or before {args.date}; nothing to compute.")
        return

    with conn.cursor() as cur:
        if args.portfolio_id:
            cur.execute("SELECT portfolio_id, portfolio_name FROM portfolio.portfolios WHERE portfolio_id = %s",
                        (args.portfolio_id,))
        else:
            cur.execute("SELECT portfolio_id, portfolio_name FROM portfolio.portfolios")
        portfolios = cur.fetchall()

    for portfolio_id, name in portfolios:
        eq_mv, eq_cb, cash_div, realized = compute_equity_value(conn, portfolio_id, as_of)
        mf_mv, mf_cb = compute_mf_value(conn, portfolio_id, as_of)
        market_value, cost_basis = eq_mv + mf_mv, eq_cb + mf_cb
        write_snapshot(conn, portfolio_id, as_of, market_value, cost_basis, cash_div, realized)
        print(f"portfolio_id={portfolio_id} ({name}) as_of={as_of}: "
              f"market_value={market_value:,.2f} cost_basis={cost_basis:,.2f} "
              f"unrealized_pnl={market_value - cost_basis:,.2f} realized_pnl={realized:,.2f} "
              f"cash_dividends={cash_div:,.2f}")

    conn.close()


if __name__ == "__main__":
    main()
