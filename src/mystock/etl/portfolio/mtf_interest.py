"""Slab-rate interest math for MTF (Margin Trade Facility) positions.

A broker's MTF interest plan is a marginal-rate table, not one flat rate — e.g. Upstox's
Plus plan charges Rs 20/day per Rs 50,000 for the first Rs 1,00,000 borrowed, then
Rs 20/day per Rs 40,000 (the Basic-plan rate) for the amount above that. Interest on a
given borrowed amount is the sum, across every slab that amount reaches, of the rate
applied to the portion of the amount falling in that slab — the same marginal-tax-bracket
shape, not "look up one rate for the total."

Interest accrues on calendar days, not trading days — it's a loan cost, not a trading
one, so callers must pass real calendar-day counts (as_of - open_date), never a
main.dim_date trading-day count.

Usage (as a library — no __main__, this is imported by compute_mtf_interest.py and
import_mtf_position.py, and is unit-tested directly in tests/):
    from mystock.etl.portfolio.mtf_interest import daily_interest
    daily_interest(conn, "upstox", "basic", 8664.85, date(2026, 9, 28))
"""


def get_slabs(conn, broker, plan, as_of):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT min_borrowed, max_borrowed, charge_amount, per_amount
               FROM portfolio.mtf_interest_slabs
               WHERE broker = %s AND plan = %s
                 AND effective_from <= %s AND (effective_to IS NULL OR effective_to >= %s)
               ORDER BY min_borrowed""",
            (broker, plan, as_of, as_of),
        )
        return cur.fetchall()


def daily_interest(conn, broker, plan, borrowed_amount, as_of):
    """Interest for one calendar day on `borrowed_amount`, under `broker`/`plan`'s slab
    table as of `as_of`. Returns 0.0 if borrowed_amount <= 0 or no slabs are defined."""
    borrowed_amount = float(borrowed_amount)
    if borrowed_amount <= 0:
        return 0.0

    slabs = get_slabs(conn, broker, plan, as_of)
    total = 0.0
    for min_borrowed, max_borrowed, charge_amount, per_amount in slabs:
        min_borrowed = float(min_borrowed)
        if borrowed_amount <= min_borrowed:
            continue
        slab_top = float(max_borrowed) if max_borrowed is not None else borrowed_amount
        portion = min(borrowed_amount, slab_top) - min_borrowed
        total += float(charge_amount) * portion / float(per_amount)
    return round(total, 4)


def cumulative_interest(conn, broker, plan, borrowed_amount, open_date, as_of):
    """Interest accrued from open_date (exclusive) through as_of (inclusive), assuming
    borrowed_amount stayed constant over the window (no partial-repayment modeling yet —
    see docs/STATUS.md). Uses today's slab table for the whole window; slabs are looked
    up per historical effective_from/effective_to if the rate ever changes mid-window."""
    days_held = (as_of - open_date).days
    if days_held <= 0:
        return 0.0
    # Rate could change mid-window if a slab's effective range ends; sum day-by-day only
    # if that's actually possible (rare), otherwise the fast path (rate * days) is exact.
    slabs_at_open = get_slabs(conn, broker, plan, open_date)
    slabs_at_close = get_slabs(conn, broker, plan, as_of)
    if slabs_at_open == slabs_at_close:
        return round(daily_interest(conn, broker, plan, borrowed_amount, as_of) * days_held, 2)
    total = 0.0
    for n in range(1, days_held + 1):
        from datetime import timedelta
        total += daily_interest(conn, broker, plan, borrowed_amount, open_date + timedelta(days=n))
    return round(total, 2)
