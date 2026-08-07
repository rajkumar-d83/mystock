"""Imports a broker holdings export keyed by ISIN (Upstox-style: 'HOLDING_MYSQL' /
'MF_HOLDING_MYSQL' sheets with columns ISIN, Scrip Name, Current Qty, ..., Rate,
Valuation) as OPENING_BALANCE transactions — one per holding, dated as of the report's
"Value Date" column (or --as-of if that's missing), using the broker's own reported
average rate as cost basis. This is a snapshot, not real trade history, which is why it
lands as OPENING_BALANCE rather than BUY.

Equity (ISIN prefix INE) and mutual fund (ISIN prefix INF) rows are split automatically
and inserted into portfolio.transactions / portfolio.mf_transactions respectively.
Anything else (e.g. bond/NCD ISINs, or an MF ISIN not present in staging.mf_scheme_master)
is skipped and reported, not guessed at.

Idempotent: re-running with the same --portfolio/--as-of is safe to re-run for a
corrected file, but does NOT dedupe against a different as-of date — an OPENING_BALANCE
import is meant to be run once per portfolio to seed it, not repeatedly.

Usage:
    python -m mystock.etl.portfolio.import_holdings_isin --file ~/Downloads/holdings_20260803_FZ6961.xlsx \\
        --user raj --portfolio "Upstox" --broker upstox
"""
import argparse
import re
from datetime import datetime
from pathlib import Path

import openpyxl

from mystock.db import get_conn
from mystock.etl.portfolio.db_helpers import (
    get_or_create_user,
    get_or_create_portfolio,
    match_security_by_isin,
    match_mf_scheme_by_isin,
)

ISIN_RE = re.compile(r"^IN[EF][0-9A-Z]{9}$")


def find_header_row(rows):
    for i, r in enumerate(rows):
        if r and r[0] == "ISIN":
            return i
    raise ValueError("could not find header row starting with 'ISIN'")


def parse_value_date(v, fallback):
    if v is None:
        return fallback
    if hasattr(v, "date"):
        return v.date()
    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(v), fmt).date()
        except ValueError:
            continue
    return fallback


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--user", required=True)
    ap.add_argument("--portfolio", required=True)
    ap.add_argument("--broker", default=None)
    ap.add_argument("--as-of", default=None, help="fallback date (YYYY-MM-DD) if the file has no Value Date")
    ap.add_argument("--mf-only", action="store_true",
                     help="skip equity (INE) rows entirely. This file's 'Rate' column is the market rate as of "
                          "the report date, NOT average cost -- equity cost basis should come from a source with "
                          "a genuine Avg. Price column instead (see import_holdings_symbol.py). Use this flag "
                          "when re-running just to pick up newly-matchable MF schemes on a portfolio whose equity "
                          "opening balances were already correctly seeded elsewhere.")
    args = ap.parse_args()

    fallback_date = datetime.strptime(args.as_of, "%Y-%m-%d").date() if args.as_of else datetime.today().date()

    wb = openpyxl.load_workbook(Path(args.file).expanduser(), data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = list(ws.iter_rows(values_only=True))
    header_idx = find_header_row(rows)
    data_rows = [r for r in rows[header_idx + 1:] if r and r[0] and ISIN_RE.match(str(r[0]))]

    conn = get_conn()
    user_id = get_or_create_user(conn, args.user)
    portfolio_id = get_or_create_portfolio(conn, user_id, args.portfolio, broker=args.broker)

    equity_inserted = mf_inserted = skipped = 0
    skipped_rows = []

    with conn.cursor() as cur:
        for r in data_rows:
            isin, scrip_name, current_qty = str(r[0]), r[1], r[2]
            value_date_raw, rate, valuation = r[8], r[9], r[10]
            qty = float(current_qty or 0)
            if qty <= 0:
                continue
            price = float(rate) if rate is not None else (float(valuation) / qty if valuation else 0)
            txn_date = parse_value_date(value_date_raw, fallback_date)

            if isin.startswith("INE"):
                if args.mf_only:
                    continue
                match = match_security_by_isin(conn, isin)
                if not match:
                    skipped += 1
                    skipped_rows.append((isin, scrip_name, "equity ISIN not in main.dim_security"))
                    continue
                security_key, symbol = match
                cur.execute(
                    """INSERT INTO portfolio.transactions
                       (portfolio_id, security_key, transaction_type, transaction_date, quantity, price, source_file)
                       VALUES (%s, %s, 'OPENING_BALANCE', %s, %s, %s, %s)
                       ON CONFLICT (portfolio_id, security_key, transaction_type, transaction_date, quantity, price)
                       DO NOTHING""",
                    (portfolio_id, security_key, txn_date, qty, price, Path(args.file).name),
                )
                equity_inserted += 1
            elif isin.startswith("INF"):
                match = match_mf_scheme_by_isin(conn, isin)
                if not match:
                    skipped += 1
                    skipped_rows.append((isin, scrip_name, "MF ISIN not in staging.mf_scheme_master"))
                    continue
                scheme_key, scheme_name = match
                cur.execute(
                    """INSERT INTO portfolio.mf_transactions
                       (portfolio_id, scheme_key, transaction_type, transaction_date, units, price, source_file)
                       VALUES (%s, %s, 'OPENING_BALANCE', %s, %s, %s, %s)
                       ON CONFLICT (portfolio_id, scheme_key, transaction_type, transaction_date, units, price)
                       WHERE transaction_type = 'OPENING_BALANCE'
                       DO NOTHING""",
                    (portfolio_id, scheme_key, txn_date, qty, price, Path(args.file).name),
                )
                mf_inserted += 1
            else:
                skipped += 1
                skipped_rows.append((isin, scrip_name, "unrecognized ISIN prefix (likely bond/NCD)"))

    conn.commit()
    conn.close()

    print(f"portfolio_id={portfolio_id}: {equity_inserted} equity, {mf_inserted} MF opening balances inserted, {skipped} skipped")
    for isin, name, reason in skipped_rows:
        print(f"  SKIPPED {isin} ({name}): {reason}")


if __name__ == "__main__":
    main()
