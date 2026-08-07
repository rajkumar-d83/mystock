"""Fetch NSE's official currently-listed equity master and upsert into
staging.nse_equity_master. Note: this list is *currently listed* symbols only —
it does not include historically delisted/renamed names.

Upserts (not truncate+reload) so it's safe to call repeatedly — existing symbols get
their payload refreshed in place, new listings get inserted. refresh_equity_master()
is reused by the historical batch backfill to pick up newly listed symbols mid-run.

Usage:
    python -m mystock.etl.historical.fetch_equity_master
"""
import csv
import io
import json
import uuid

import psycopg2.extras
from jugaad_data.nse import NSEArchives

from mystock.db import get_conn, etl_run

EQUITY_LIST_URL = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"


def fetch_equity_list():
    archives = NSEArchives()
    resp = archives.s.get(EQUITY_LIST_URL, timeout=15)
    resp.raise_for_status()
    reader = csv.DictReader(io.StringIO(resp.text))
    return [{k.strip(): v.strip() for k, v in row.items()} for row in reader]


def refresh_equity_master(conn):
    """Fetches the live equity list and upserts it. Returns (total_symbols, new_symbols)."""
    rows = fetch_equity_list()
    if not rows:
        raise RuntimeError("Equity master fetch returned zero rows")

    batch_id = str(uuid.uuid4())
    with conn.cursor() as cur:
        cur.execute("SELECT symbol FROM staging.nse_equity_master")
        existing = {r[0] for r in cur.fetchall()}

        values = [(row["SYMBOL"], json.dumps(row), batch_id) for row in rows]
        psycopg2.extras.execute_values(
            cur,
            """INSERT INTO staging.nse_equity_master (symbol, raw_payload, batch_id)
               VALUES %s
               ON CONFLICT (symbol) DO UPDATE
                   SET raw_payload = EXCLUDED.raw_payload,
                       batch_id = EXCLUDED.batch_id,
                       fetched_at = now()""",
            values,
        )
    conn.commit()

    new_symbols = {row["SYMBOL"] for row in rows} - existing
    if new_symbols:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO metadata.audit (event_type, target, details)
                   VALUES (%s, %s, %s)""",
                ("new_symbols_discovered", "staging.nse_equity_master",
                 json.dumps({"symbols": sorted(new_symbols), "count": len(new_symbols)})),
            )
        conn.commit()

    return len(rows), new_symbols


def main():
    conn = get_conn()
    with etl_run("historical_equity_master", {"url": EQUITY_LIST_URL}) as run:
        total, new_symbols = refresh_equity_master(conn)
        run["rows"] = total
    conn.close()
    print(f"Refreshed {total} symbols ({len(new_symbols)} new: {sorted(new_symbols)})")


if __name__ == "__main__":
    main()
