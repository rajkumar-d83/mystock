"""Loads staging.sector_map from NSE's NIFTY Total Market constituent list.

Usage:
    python -m mystock.etl.staging.load_sector_map
"""
import csv
import io

import psycopg2.extras
from jugaad_data.nse import NSEArchives

from mystock.db import get_conn

SOURCE_URL = "https://nsearchives.nseindia.com/content/indices/ind_niftytotalmarket_list.csv"
SOURCE_NAME = "ind_niftytotalmarket_list"


def fetch_rows():
    archives = NSEArchives()
    resp = archives.s.get(SOURCE_URL, timeout=15)
    resp.raise_for_status()
    reader = csv.DictReader(io.StringIO(resp.text))
    return [{k.strip(): v.strip() for k, v in row.items()} for row in reader]


def main():
    rows = fetch_rows()
    if not rows:
        raise RuntimeError("Sector map fetch returned zero rows")

    values = [(r["Symbol"], r["Company Name"], r["Industry"], SOURCE_NAME) for r in rows]
    conn = get_conn()
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """INSERT INTO staging.sector_map (symbol, company_name, industry, index_source)
               VALUES %s
               ON CONFLICT (symbol) DO UPDATE
                   SET company_name = EXCLUDED.company_name,
                       industry = EXCLUDED.industry,
                       index_source = EXCLUDED.index_source,
                       loaded_at = now()""",
            values,
        )
    conn.commit()
    conn.close()
    print(f"Loaded {len(values)} symbol->industry mappings into staging.sector_map")


if __name__ == "__main__":
    main()
