"""Records an MTF (Margin Trade Facility) position by hand — mystock has no automated
feed for these (Upstox's holdings export only lists settled DP holdings, and MTF
positions don't appear there until the broker converts/settles them; see
portfolio.mtf_positions vs portfolio.transactions for why they're kept separate).

Two modes: open a new position, or close/square-off an existing one.

Usage:
    python -m mystock.etl.portfolio.import_mtf_position \\
        --portfolio-id 1 --symbol IRFC --quantity 150 --buy-price 78.55 \\
        --own-amount 3117.65 --broker upstox --plan basic --open-date 2026-09-28

    python -m mystock.etl.portfolio.import_mtf_position \\
        --close --position-id 1 --close-price 82.00 --close-date 2026-10-15
    python -m mystock.etl.portfolio.import_mtf_position \\
        --close --position-id 1 --close-price 70.00 --close-date 2027-09-30 --squared-off
"""
import argparse
from datetime import datetime

from mystock.db import get_conn


def parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


def open_position(conn, args):
    with conn.cursor() as cur:
        cur.execute("SELECT security_key FROM main.dim_security WHERE symbol = %s", (args.symbol,))
        row = cur.fetchone()
        if not row:
            raise SystemExit(f"Unknown symbol: {args.symbol}")
        security_key = row[0]

        position_value = args.quantity * args.buy_price
        borrowed_amount = round(position_value - args.own_amount, 2)
        if borrowed_amount < 0:
            raise SystemExit(
                f"own-amount ({args.own_amount}) exceeds the position value "
                f"({position_value:.2f} = {args.quantity} x {args.buy_price}) -- nothing borrowed, this isn't MTF"
            )

        cur.execute(
            """INSERT INTO portfolio.mtf_positions
                   (portfolio_id, security_key, broker, plan, open_date, quantity, buy_price,
                    own_amount, borrowed_amount, notes)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING mtf_position_id""",
            (args.portfolio_id, security_key, args.broker, args.plan, args.open_date,
             args.quantity, args.buy_price, args.own_amount, borrowed_amount, args.notes),
        )
        position_id = cur.fetchone()[0]
    conn.commit()
    print(f"Opened mtf_position_id={position_id}: {args.symbol} {args.quantity} @ {args.buy_price} "
          f"(own={args.own_amount:.2f}, borrowed={borrowed_amount:.2f}, plan={args.plan})")


def close_position(conn, args):
    status = "squared_off" if args.squared_off else "closed"
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE portfolio.mtf_positions
               SET status = %s, close_date = %s, close_price = %s
               WHERE mtf_position_id = %s AND status = 'open'
               RETURNING quantity, buy_price, own_amount, borrowed_amount, open_date""",
            (status, args.close_date, args.close_price, args.position_id),
        )
        row = cur.fetchone()
        if not row:
            raise SystemExit(f"mtf_position_id={args.position_id} not found or not open")
        qty, buy_price, own_amount, borrowed_amount, open_date = row
    conn.commit()
    gross_pnl = float(qty) * (args.close_price - float(buy_price))
    print(f"Closed mtf_position_id={args.position_id} as {status}: "
          f"held {(args.close_date - open_date).days} days, gross P&L (excl. interest/fees) = {gross_pnl:.2f}. "
          f"Run compute_mtf_interest.py one more time for {open_date}..{args.close_date} first if you want "
          f"the final cumulative interest recorded before this closes out of future daily runs.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--close", action="store_true", help="close/square-off an existing position instead of opening one")

    # open-mode args
    ap.add_argument("--portfolio-id", type=int, default=1)
    ap.add_argument("--symbol")
    ap.add_argument("--quantity", type=float)
    ap.add_argument("--buy-price", type=float)
    ap.add_argument("--own-amount", type=float)
    ap.add_argument("--broker", default="upstox")
    ap.add_argument("--plan", default="basic", choices=["basic", "plus"])
    ap.add_argument("--open-date", type=parse_date)
    ap.add_argument("--notes")

    # close-mode args
    ap.add_argument("--position-id", type=int)
    ap.add_argument("--close-price", type=float)
    ap.add_argument("--close-date", type=parse_date)
    ap.add_argument("--squared-off", action="store_true", help="Upstox force-closed this at the 366-day limit")

    args = ap.parse_args()
    conn = get_conn()

    if args.close:
        missing = [n for n, v in [("--position-id", args.position_id), ("--close-price", args.close_price),
                                   ("--close-date", args.close_date)] if v is None]
        if missing:
            raise SystemExit(f"--close requires: {', '.join(missing)}")
        close_position(conn, args)
    else:
        missing = [n for n, v in [("--symbol", args.symbol), ("--quantity", args.quantity),
                                   ("--buy-price", args.buy_price), ("--own-amount", args.own_amount),
                                   ("--open-date", args.open_date)] if v is None]
        if missing:
            raise SystemExit(f"Opening a position requires: {', '.join(missing)}")
        open_position(conn, args)

    conn.close()


if __name__ == "__main__":
    main()
