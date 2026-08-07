"""Daily incremental NAV update for mutual funds — uses AMFI's whole-market NAVAll.txt
(one file, every scheme's latest known NAV) rather than re-calling mfapi.in per scheme.

This matters: mfapi.in's per-scheme endpoint returns a scheme's ENTIRE history on every
call — fine for the one-time backfill, but re-fetching full history for 2000+ schemes
every day would take ~36 minutes daily for no benefit. NAVAll.txt is a single request
covering every scheme's most recent NAV, mirroring the NSE whole-market-bhavcopy pattern.

Each row carries its OWN date — the file is not implicitly "today" for every scheme
(defunct/inactive schemes retain stale historical dates, sometimes years old). We only
insert dates we don't already have (unique key: scheme_code, nav_date, source), so this
is safe to run daily regardless of AMFI's exact publish timing — if a scheme's NAV is
still showing yesterday's date when this runs, today's value is simply picked up on the
next run once AMFI publishes it.

Only inserts rows for schemes already in staging.amfi_mf_scheme_master (the Direct+Growth,
top-10-AMC universe established by the historical backfill) — NAVAll.txt covers the
entire industry (~14,000+ rows), most of which is out of scope.

Usage:
    python -m mystock.etl.daily.fetch_mf_daily_nav
"""
import json
import sys
import uuid
from datetime import datetime

import psycopg2.extras
import requests

from mystock.db import get_conn, etl_run

NAVALL_URL = "https://www.amfiindia.com/spages/NAVAll.txt"
SOURCE = "amfi_navall"


def fetch_navall_lines():
    resp = requests.get(NAVALL_URL, timeout=30)
    resp.raise_for_status()
    return resp.text.splitlines()


def parse_data_rows(lines):
    """NAVAll.txt interleaves section headers (category/fund-house names) and blank
    lines with the actual data rows — a data row is identified by having exactly 5
    semicolons and a numeric first field (scheme code)."""
    rows = []
    for line in lines:
        parts = line.split(";")
        if len(parts) != 6 or not parts[0].strip().isdigit():
            continue
        scheme_code, isin_growth, isin_div, name, nav, nav_date = (p.strip() for p in parts)
        rows.append({
            "scheme_code": int(scheme_code),
            "isin_growth": isin_growth,
            "isin_div_reinvestment": isin_div,
            "scheme_name": name,
            "nav": nav,
            "date": nav_date,
        })
    return rows


def target_scheme_codes(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT scheme_code FROM staging.amfi_mf_scheme_master")
        return {r[0] for r in cur.fetchall()}


def insert_rows(conn, rows, batch_id):
    if not rows:
        return 0
    values = [
        (r["scheme_code"], datetime.strptime(r["date"], "%d-%b-%Y").date(), json.dumps(r), SOURCE, batch_id)
        for r in rows
    ]
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """INSERT INTO staging.amfi_mf_nav_history_raw (scheme_code, nav_date, raw_payload, source, batch_id)
               VALUES %s
               ON CONFLICT (scheme_code, nav_date, source) DO NOTHING""",
            values,
        )
    conn.commit()
    return len(values)


def main():
    conn = get_conn()
    targets = target_scheme_codes(conn)
    if not targets:
        print("staging.amfi_mf_scheme_master is empty — run mystock.etl.historical.fetch_mf_nav_history first.")
        return

    with etl_run("daily_mf_nav", {}) as run:
        lines = fetch_navall_lines()
        all_rows = parse_data_rows(lines)
        matched = [r for r in all_rows if r["scheme_code"] in targets]
        print(f"{len(all_rows)} total rows in NAVAll.txt, {len(matched)} match our {len(targets)} target schemes", flush=True)

        n = insert_rows(conn, matched, str(uuid.uuid4()))
        run["rows"] = n
        print(f"{n} new NAV rows inserted (rest were already loaded)", flush=True)

    conn.close()


if __name__ == "__main__":
    main()
