"""Fetches mutual fund scheme metadata + full NAV history from mfapi.in (wraps AMFI's
official data, free, no auth). Scoped to Direct+Growth plans across the top 10 AMCs by
AUM, plus Parag Parikh and one allowlisted Tata scheme (see MYSTOCK_PRODUCT_SPEC.md §6).

Unlike NSE, a single call per scheme returns its ENTIRE NAV history at once (often back
to inception) — there's no per-date-range chunking needed, only the choice of which
schemes to include.

Usage:
    python -m mystock.etl.historical.fetch_mf_nav_history
    python -m mystock.etl.historical.fetch_mf_nav_history --sleep 0.5
"""
import argparse
import json
import sys
import time
import uuid
from datetime import date, datetime

import psycopg2.extras
import requests

from mystock.db import get_conn, etl_run

SCHEME_LIST_URL = "https://api.mfapi.in/mf"
SCHEME_DETAIL_URL = "https://api.mfapi.in/mf/{code}"

# 10-year retention cutoff (matches etl/historical/fetch_stock_history.py's). mfapi.in
# always returns a scheme's ENTIRE history with no date-range parameter, so without this
# filter, simply re-running this script (e.g. to pick up a newly-added scheme) would
# silently re-insert pre-cutoff rows.
RETENTION_CUTOFF = date(2016, 8, 3)

TARGET_AMCS = [
    "HDFC", "SBI", "ICICI Prudential", "Nippon India", "Kotak",
    "Aditya Birla Sun Life", "Axis", "UTI", "DSP", "Mirae Asset",
    "Parag Parikh",
]

# Individual schemes pulled in outside the AMC-wide filter. Tata Mutual Fund names ALL
# its products the same "...Direct Plan-Growth" way, including ~150 closed-end Fixed
# Maturity Plans/series funds — unlike the AMCs above, whose closed-end products use a
# different naming pattern that the is_target_scheme() suffix check naturally excludes.
# Specific schemes actually held are allowlisted by code instead of expanding Tata into
# the AMC-wide filter (see MYSTOCK_PRODUCT_SPEC.md §15 risk register).
EXTRA_SCHEME_CODES = [
    132756,  # Tata ELSS Fund-Growth-Direct Plan
]


def is_target_scheme(scheme_name):
    name_upper = scheme_name.upper()
    if not any(name_upper.startswith(amc.upper()) for amc in TARGET_AMCS):
        return False
    n = scheme_name.lower().rstrip()
    return "direct" in n and (n.endswith("growth") or n.endswith("growth option"))


def fetch_candidate_schemes():
    resp = requests.get(SCHEME_LIST_URL, timeout=30)
    resp.raise_for_status()
    all_schemes = resp.json()
    candidates = [s for s in all_schemes if is_target_scheme(s["schemeName"])]
    candidates_by_code = {s["schemeCode"]: s for s in candidates}
    for s in all_schemes:
        if s["schemeCode"] in EXTRA_SCHEME_CODES:
            candidates_by_code[s["schemeCode"]] = s
    return list(candidates_by_code.values())


def fetch_scheme_detail(scheme_code, retries=2, retry_sleep=3.0):
    for attempt in range(retries + 1):
        try:
            resp = requests.get(SCHEME_DETAIL_URL.format(code=scheme_code), timeout=20)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            if attempt == retries:
                raise
            time.sleep(retry_sleep)


def parse_nav_date(s):
    return datetime.strptime(s, "%d-%m-%Y").date()


def upsert_scheme_master(conn, scheme_code, meta, batch_id):
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO staging.amfi_mf_scheme_master (scheme_code, raw_payload, batch_id)
               VALUES (%s, %s, %s)
               ON CONFLICT (scheme_code) DO UPDATE
                   SET raw_payload = EXCLUDED.raw_payload, batch_id = EXCLUDED.batch_id,
                       fetched_at = now()""",
            (scheme_code, json.dumps(meta), batch_id),
        )
    conn.commit()


def insert_nav_history(conn, scheme_code, nav_rows, batch_id):
    if not nav_rows:
        return 0
    values = [
        (scheme_code, parse_nav_date(r["date"]), json.dumps(r), batch_id)
        for r in nav_rows
        if parse_nav_date(r["date"]) >= RETENTION_CUTOFF
    ]
    if not values:
        return 0
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """INSERT INTO staging.amfi_mf_nav_history_raw (scheme_code, nav_date, raw_payload, batch_id)
               VALUES %s
               ON CONFLICT (scheme_code, nav_date, source) DO NOTHING""",
            values,
        )
    conn.commit()
    return len(values)


def already_loaded_codes(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT scheme_code FROM staging.amfi_mf_scheme_master")
        return {r[0] for r in cur.fetchall()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sleep", type=float, default=0.3, help="seconds between schemes")
    ap.add_argument("--force", action="store_true", help="re-fetch schemes already loaded (default: skip them)")
    args = ap.parse_args()

    candidates = fetch_candidate_schemes()
    print(f"{len(candidates)} candidate schemes matched (target AMCs, Direct+Growth)", flush=True)

    conn = get_conn()
    if not args.force:
        loaded = already_loaded_codes(conn)
        before = len(candidates)
        candidates = [s for s in candidates if s["schemeCode"] not in loaded]
        if before != len(candidates):
            print(f"Skipping {before - len(candidates)} schemes already loaded (pass --force to re-fetch)", flush=True)

    batch_id = str(uuid.uuid4())

    with etl_run("historical_mf_nav_history", {"candidates": len(candidates)}) as run:
        for i, scheme in enumerate(candidates, 1):
            code = scheme["schemeCode"]
            try:
                detail = fetch_scheme_detail(code)
                upsert_scheme_master(conn, code, detail["meta"], batch_id)
                n = insert_nav_history(conn, code, detail["data"], batch_id)
                run["rows"] += n
                print(f"[{i}/{len(candidates)}] {code} {scheme['schemeName'][:60]}: {n} NAV rows", flush=True)
            except Exception as e:
                print(f"[{i}/{len(candidates)}] {code}: FAILED - {e}", file=sys.stderr, flush=True)
            time.sleep(args.sleep)

    conn.close()


if __name__ == "__main__":
    main()
