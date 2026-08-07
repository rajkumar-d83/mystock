"""Imports an ELSS folio-statement export (Upstox-style 'ELSS_MF' sheet: Order Date,
Folio Number, Scheme Name, Units, Amount) as BUY mf_transactions. Unlike the holdings-
snapshot imports, this file is genuine order-level history, so it lands as real BUY
transactions (price derived as Amount / Units), not OPENING_BALANCE.

Scheme Name is matched against main.dim_mf_scheme by exact (case-insensitive) name, then
a loose substring fallback if that's ambiguous-free. Unmatched rows are reported, not
guessed at.

Usage:
    python -m mystock.etl.portfolio.import_elss --file ~/Downloads/elss_2526_FZ6961.xlsx \\
        --user raj --portfolio "Upstox"
"""
import argparse
from pathlib import Path

import openpyxl

from mystock.db import get_conn
from mystock.etl.portfolio.db_helpers import get_or_create_user, get_or_create_portfolio, match_mf_scheme_by_name


def find_header_row(rows):
    for i, r in enumerate(rows):
        if r and r[0] == "Order Date":
            return i
    raise ValueError("could not find header row starting with 'Order Date'")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--sheet", default="ELSS_MF")
    ap.add_argument("--user", required=True)
    ap.add_argument("--portfolio", required=True)
    args = ap.parse_args()

    wb = openpyxl.load_workbook(Path(args.file).expanduser(), data_only=True)
    ws = wb[args.sheet]
    rows = list(ws.iter_rows(values_only=True))
    header_idx = find_header_row(rows)
    data_rows = [r for r in rows[header_idx + 1:] if r and r[0]]

    conn = get_conn()
    user_id = get_or_create_user(conn, args.user)
    portfolio_id = get_or_create_portfolio(conn, user_id, args.portfolio)

    inserted = skipped = 0
    skipped_rows = []

    with conn.cursor() as cur:
        for r in data_rows:
            order_date, folio, scheme_name, units, amount = r[0], r[1], r[2], r[3], r[4]
            units = float(units or 0)
            amount = float(amount or 0)
            if units <= 0:
                continue
            match = match_mf_scheme_by_name(conn, str(scheme_name))
            if not match:
                skipped += 1
                skipped_rows.append((scheme_name, "no unambiguous match in main.dim_mf_scheme"))
                continue
            scheme_key, _ = match
            cur.execute(
                """INSERT INTO portfolio.mf_transactions
                   (portfolio_id, scheme_key, folio_number, transaction_type, transaction_date, units, price, amount, source_file)
                   VALUES (%s, %s, %s, 'BUY', %s, %s, %s, %s, %s)
                   ON CONFLICT (portfolio_id, scheme_key, transaction_type, transaction_date, folio_number, units, amount)
                   DO NOTHING""",
                (portfolio_id, scheme_key, str(folio), order_date.date() if hasattr(order_date, "date") else order_date,
                 units, amount / units, amount, Path(args.file).name),
            )
            inserted += 1

    conn.commit()
    conn.close()

    print(f"portfolio_id={portfolio_id}: {inserted} ELSS buy transactions inserted, {skipped} skipped")
    for scheme_name, reason in skipped_rows:
        print(f"  SKIPPED '{scheme_name}': {reason}")


if __name__ == "__main__":
    main()
