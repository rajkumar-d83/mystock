"""Computes one day's snapshot per open MTF position (portfolio.fact_mtf_position_daily):
current value, interest accrued (daily and cumulative since open), effective leverage,
unrealized P&L both gross and net of interest/fees, break-even price, and days left
before Upstox's 366-day forced square-off. Mirrors compute_portfolio_health.py's shape
(one function per position, upsert a snapshot row, print a summary) but MTF positions
are NOT folded into portfolio.fact_portfolio_value_daily -- see mtf_interest.py's module
docstring and MYSTOCK_PRODUCT_SPEC.md for why: mixing gross MTF value into overall
portfolio value would overstate real net worth by the borrowed amount.

effective_leverage = current_value / (current_value - borrowed_amount), i.e. current
equity, not own_amount -- as price falls, equity shrinks faster than value, so this
number correctly rises toward a margin call as the position moves against you. It's
undefined (reported as null) once equity hits zero or goes negative.

break_even_price is the price at which unrealized_pnl_net = 0: the position value needed
to cover own_amount + borrowed_amount + cumulative_interest + brokerage + pledge/unpledge
fees already paid.

Usage:
    python -m mystock.etl.portfolio.compute_mtf_interest                  # today, all open positions
    python -m mystock.etl.portfolio.compute_mtf_interest --date 2026-10-15
"""
import argparse
from datetime import date, datetime

from mystock.db import get_conn
from mystock.etl.portfolio.mtf_interest import daily_interest, cumulative_interest


def open_positions(conn):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT p.mtf_position_id, ds.symbol, p.security_key, p.broker, p.plan,
                      p.open_date, p.quantity, p.buy_price, p.own_amount, p.borrowed_amount
               FROM portfolio.mtf_positions p
               JOIN main.dim_security ds ON ds.security_key = p.security_key
               WHERE p.status = 'open'"""
        )
        return cur.fetchall()


def latest_close_on_or_before(conn, security_key, as_of):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT fdp.close FROM main.fact_daily_prices fdp
               JOIN main.dim_date dd ON dd.date_key = fdp.date_key
               WHERE fdp.security_key = %s AND dd.full_date <= %s
               ORDER BY dd.full_date DESC LIMIT 1""",
            (security_key, as_of),
        )
        row = cur.fetchone()
        return float(row[0]) if row else None


def flat_fee(conn, broker, plan, segment, charge_type):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT flat_amount FROM portfolio.broker_fee_schedule
               WHERE broker = %s AND plan = %s AND segment = %s AND charge_type = %s
                 AND calc_method = 'flat_per_order'
               ORDER BY effective_from DESC LIMIT 1""",
            (broker, plan, segment, charge_type),
        )
        row = cur.fetchone()
        return float(row[0]) if row else 0.0


def delivery_brokerage(conn, broker, plan):
    # MTF orders are charged the same brokerage as equity delivery -- reused directly
    # from broker_fee_schedule's equity_delivery row, not duplicated as an equity_mtf row,
    # so a rate change only needs to be updated in one place. See mtf_interest.py.
    return flat_fee(conn, broker, plan, "equity_delivery", "brokerage")


def compute_position(conn, position_id, symbol, security_key, broker, plan, open_date,
                      quantity, buy_price, own_amount, borrowed_amount, as_of):
    quantity, buy_price = float(quantity), float(buy_price)
    own_amount, borrowed_amount = float(own_amount), float(borrowed_amount)

    close = latest_close_on_or_before(conn, security_key, as_of)
    if close is None:
        return None
    current_value = quantity * close

    days_held = (as_of - open_date).days
    daily_int = daily_interest(conn, broker, plan, borrowed_amount, as_of)
    cum_int = cumulative_interest(conn, broker, plan, borrowed_amount, open_date, as_of)

    brokerage = delivery_brokerage(conn, broker, plan)
    pledge = flat_fee(conn, broker, plan, "equity_mtf", "pledge_charge")
    fees_so_far = brokerage + pledge  # unpledge/auto-square-off fees only apply at close, not while open

    current_equity = current_value - borrowed_amount
    effective_leverage = (current_value / current_equity) if current_equity > 0 else None

    unrealized_pnl_gross = current_value - (own_amount + borrowed_amount)
    unrealized_pnl_net = unrealized_pnl_gross - cum_int - fees_so_far

    break_even_price = (own_amount + borrowed_amount + cum_int + fees_so_far) / quantity if quantity else None
    days_to_forced_squareoff = 366 - days_held

    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO portfolio.fact_mtf_position_daily
                   (mtf_position_id, date_key, current_price, current_value, days_held,
                    daily_interest, cumulative_interest, effective_leverage,
                    unrealized_pnl_gross, unrealized_pnl_net, break_even_price,
                    days_to_forced_squareoff)
               SELECT %s, dd.date_key, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
               FROM main.dim_date dd WHERE dd.full_date = %s
               ON CONFLICT (mtf_position_id, date_key) DO UPDATE SET
                   current_price = EXCLUDED.current_price, current_value = EXCLUDED.current_value,
                   days_held = EXCLUDED.days_held, daily_interest = EXCLUDED.daily_interest,
                   cumulative_interest = EXCLUDED.cumulative_interest,
                   effective_leverage = EXCLUDED.effective_leverage,
                   unrealized_pnl_gross = EXCLUDED.unrealized_pnl_gross,
                   unrealized_pnl_net = EXCLUDED.unrealized_pnl_net,
                   break_even_price = EXCLUDED.break_even_price,
                   days_to_forced_squareoff = EXCLUDED.days_to_forced_squareoff""",
            (position_id, close, current_value, days_held, daily_int, cum_int, effective_leverage,
             unrealized_pnl_gross, unrealized_pnl_net, break_even_price, days_to_forced_squareoff, as_of),
        )
    conn.commit()

    print(f"mtf_position_id={position_id} ({symbol}) as_of={as_of}: close={close:.2f} "
          f"value={current_value:,.2f} days_held={days_held} "
          f"cumulative_interest={cum_int:,.2f} "
          f"effective_leverage={'n/a (equity<=0)' if effective_leverage is None else f'{effective_leverage:.2f}x'} "
          f"unrealized_pnl_net={unrealized_pnl_net:,.2f} break_even={break_even_price:.2f} "
          f"days_to_forced_squareoff={days_to_forced_squareoff}")
    return {
        "position_id": position_id, "symbol": symbol, "days_to_forced_squareoff": days_to_forced_squareoff,
        "effective_leverage": effective_leverage, "current_value": current_value, "current_equity": current_equity,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(), default=date.today())
    args = ap.parse_args()

    conn = get_conn()
    positions = open_positions(conn)
    if not positions:
        print("No open MTF positions.")
        conn.close()
        return

    for row in positions:
        compute_position(conn, *row, as_of=args.date)

    conn.close()


if __name__ == "__main__":
    main()
