"""Review and promote fuzzy-matched trade rows staged by import_trades_fuzzy.py into
real portfolio.transactions rows. Nothing gets promoted without reviewed = true, so a
bad automatic match can't silently corrupt transaction history.

Usage:
    python -m mystock.etl.portfolio.manage_staged_trades list --portfolio-id 1
    python -m mystock.etl.portfolio.manage_staged_trades approve --staging-id 42 --security-key 517
    python -m mystock.etl.portfolio.manage_staged_trades reject --staging-id 42
    python -m mystock.etl.portfolio.manage_staged_trades promote --portfolio-id 1
"""
import argparse

from mystock.db import get_conn


def cmd_list(conn, args):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT s.staging_id, s.trade_date, s.company_raw, s.scrip_code_raw, s.side,
                      s.quantity, s.price, s.matched_security_key, d.symbol, s.match_method, s.match_confidence
               FROM portfolio.import_staging_trades s
               LEFT JOIN main.dim_security d ON d.security_key = s.matched_security_key
               WHERE s.portfolio_id = %s AND s.promoted = false
                 AND (%s OR s.reviewed = false)
               ORDER BY s.reviewed, s.match_confidence NULLS FIRST, s.trade_date""",
            (args.portfolio_id, args.all),
        )
        rows = cur.fetchall()
    if not rows:
        print("Nothing pending review.")
        return
    for r in rows:
        staging_id, trade_date, company_raw, scrip_code, side, qty, price, sec_key, symbol, method, conf = r
        matched = f"{symbol} (key={sec_key}, {method}, conf={conf})" if sec_key else "NO MATCH"
        print(f"[{staging_id}] {trade_date} {side} {qty}@{price}  raw='{company_raw}' scrip={scrip_code}  -> {matched}")


def cmd_approve(conn, args):
    with conn.cursor() as cur:
        if args.security_key:
            cur.execute(
                """UPDATE portfolio.import_staging_trades
                   SET matched_security_key = %s, match_method = 'manual', match_confidence = 1.0, reviewed = true
                   WHERE staging_id = %s""",
                (args.security_key, args.staging_id),
            )
        else:
            cur.execute(
                "UPDATE portfolio.import_staging_trades SET reviewed = true WHERE staging_id = %s",
                (args.staging_id,),
            )
    conn.commit()
    print(f"staging_id={args.staging_id} approved.")


def cmd_reject(conn, args):
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE portfolio.import_staging_trades
               SET reviewed = true, matched_security_key = NULL, match_method = 'unmatched'
               WHERE staging_id = %s""",
            (args.staging_id,),
        )
    conn.commit()
    print(f"staging_id={args.staging_id} rejected (will not be promoted).")


def cmd_promote(conn, args):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT staging_id, matched_security_key, side, trade_date, quantity, price, source_file
               FROM portfolio.import_staging_trades
               WHERE portfolio_id = %s AND reviewed = true AND promoted = false AND matched_security_key IS NOT NULL""",
            (args.portfolio_id,),
        )
        rows = cur.fetchall()
        for staging_id, security_key, side, trade_date, quantity, price, source_file in rows:
            cur.execute(
                """INSERT INTO portfolio.transactions
                   (portfolio_id, security_key, transaction_type, transaction_date, quantity, price, source_file, notes)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (portfolio_id, security_key, transaction_type, transaction_date, quantity, price)
                   DO NOTHING""",
                (args.portfolio_id, security_key, side, trade_date, quantity, price, source_file,
                 f"promoted from staging_id {staging_id}"),
            )
            cur.execute(
                "UPDATE portfolio.import_staging_trades SET promoted = true WHERE staging_id = %s",
                (staging_id,),
            )
    conn.commit()
    print(f"Promoted {len(rows)} staged trades into portfolio.transactions.")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list")
    p.add_argument("--portfolio-id", type=int, required=True)
    p.add_argument("--all", action="store_true", help="include already-reviewed rows too")

    p = sub.add_parser("approve")
    p.add_argument("--staging-id", type=int, required=True)
    p.add_argument("--security-key", type=int, help="override the matched security (looked up manually)")

    p = sub.add_parser("reject")
    p.add_argument("--staging-id", type=int, required=True)

    p = sub.add_parser("promote")
    p.add_argument("--portfolio-id", type=int, required=True)

    args = ap.parse_args()
    conn = get_conn()
    {"list": cmd_list, "approve": cmd_approve, "reject": cmd_reject, "promote": cmd_promote}[args.cmd](conn, args)
    conn.close()


if __name__ == "__main__":
    main()
