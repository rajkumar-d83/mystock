"""Imports a broker trade-history export that identifies instruments by BSE scrip code +
truncated company name, not ISIN (Upstox-style 'TRADE' sheet: Date, Company, Amount,
Exchange, Segment, Scrip Code, Instrument Type, ..., Side, Quantity, Price). Only EQ
segment / Equity instrument_type rows are considered — F&O rows in the same file (if any)
are skipped, since this warehouse's equity dimension has no options identifiers to match
against.

Because there's no reliable ID to join on, every row is fuzzy-matched against
main.dim_security (by company name similarity, with a same-day-suffix-stripped
comparison, plus a "symbol appears as a token in the raw name" strong-signal check) and
written to portfolio.import_staging_trades — nothing is inserted into
portfolio.transactions directly. High-confidence matches are marked reviewed=true
automatically; everything else needs a human look via manage_staged_trades.py before
promotion, so a wrong fuzzy guess can't silently corrupt real transaction data.

Usage:
    python -m mystock.etl.portfolio.import_trades_fuzzy --file ~/Downloads/trade_20250401_20260331_FZ6961.xlsx \\
        --user raj --portfolio "Upstox"
"""
import argparse
import re
from difflib import SequenceMatcher
from pathlib import Path

import openpyxl

from mystock.db import get_conn
from mystock.etl.portfolio.db_helpers import get_or_create_user, get_or_create_portfolio

SUFFIXES = {"LIMITED", "LTD", "LT", "CORPORATION", "CORP", "COMPANY", "CO", "L", "IND", "INDIA", "PVT", "PRIVATE"}


def normalize(name):
    name = re.sub(r"[^A-Z0-9 ]", " ", name.upper())
    tokens = [t for t in name.split() if t not in SUFFIXES]
    return " ".join(tokens)


def load_securities(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT security_key, symbol, coalesce(company_name, '') FROM main.dim_security")
        return [(key, symbol, normalize(company_name)) for key, symbol, company_name in cur.fetchall()]


def best_match(company_raw, securities):
    """A symbol appearing as a literal word inside the raw name (e.g. "TECH" inside
    "ZEN TECH") is NOT trustworthy on its own — short/generic symbols coincidentally
    collide with unrelated tickers (HDFC BANK LT -> symbol "HDFC", a different,
    unfetched-name security; ZEN TECH -> symbol "TECH", ditto). It's only strong
    evidence when it agrees with the best company-name fuzzy match, so both signals are
    computed and only trusted at full confidence when they point at the same security."""
    norm_raw = normalize(company_raw)
    best_fuzzy = (None, None, 0.0)
    symbol_hits = []
    for security_key, symbol, norm_name in securities:
        if len(symbol) >= 4 and re.search(rf"\b{re.escape(symbol)}\b", company_raw.upper()):
            symbol_hits.append((security_key, symbol))
        if norm_name:
            score = SequenceMatcher(None, norm_raw, norm_name).ratio()
            if score > best_fuzzy[2]:
                best_fuzzy = (security_key, symbol, score)

    if len(symbol_hits) == 1:
        sec_key, symbol = symbol_hits[0]
        if best_fuzzy[0] == sec_key:
            return sec_key, symbol, 1.0, "symbol_in_name+fuzzy_name"
        return sec_key, symbol, 0.7, "symbol_in_name_only"  # uncorroborated, needs review

    if best_fuzzy[0] is not None:
        return best_fuzzy[0], best_fuzzy[1], best_fuzzy[2], "fuzzy_name"
    return None, None, 0.0, None


def find_header_row(rows):
    for i, r in enumerate(rows):
        if r and r[0] == "Date":
            return i
    raise ValueError("could not find header row starting with 'Date'")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--sheet", default="TRADE")
    ap.add_argument("--user", required=True)
    ap.add_argument("--portfolio", required=True)
    ap.add_argument("--auto-approve-threshold", type=float, default=0.9)
    args = ap.parse_args()

    wb = openpyxl.load_workbook(Path(args.file).expanduser(), data_only=True)
    ws = wb[args.sheet]
    rows = list(ws.iter_rows(values_only=True))
    header_idx = find_header_row(rows)
    data_rows = [r for r in rows[header_idx + 1:] if r and r[0] and r[5] is not None]

    conn = get_conn()
    user_id = get_or_create_user(conn, args.user)
    portfolio_id = get_or_create_portfolio(conn, user_id, args.portfolio)
    securities = load_securities(conn)

    auto_reviewed = needs_review = skipped_non_eq = 0

    with conn.cursor() as cur:
        for r in data_rows:
            trade_date, company, amount, exchange, segment, scrip_code, instrument_type = r[0:7]
            side, quantity, price = r[11], r[12], r[13]
            if segment != "EQ" or instrument_type != "Equity":
                skipped_non_eq += 1
                continue
            security_key, symbol, score, method = best_match(str(company), securities)
            reviewed = score >= args.auto_approve_threshold
            if reviewed:
                auto_reviewed += 1
            else:
                needs_review += 1
            cur.execute(
                """INSERT INTO portfolio.import_staging_trades
                   (portfolio_id, source_file, trade_date, company_raw, scrip_code_raw, side, quantity, price,
                    matched_security_key, match_method, match_confidence, reviewed)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (portfolio_id, Path(args.file).name, trade_date.date() if hasattr(trade_date, "date") else trade_date,
                 str(company), str(scrip_code), side.upper(), quantity, price,
                 security_key, method, round(score, 3), reviewed),
            )

    conn.commit()
    conn.close()

    print(f"portfolio_id={portfolio_id}: {len(data_rows) - skipped_non_eq} EQ trade rows staged "
          f"({auto_reviewed} auto-approved >= {args.auto_approve_threshold}, {needs_review} need manual review), "
          f"{skipped_non_eq} non-EQ rows skipped")
    print("Run manage_staged_trades.py list --portfolio-id "
          f"{portfolio_id} to see rows needing review, then promote once satisfied.")


if __name__ == "__main__":
    main()
