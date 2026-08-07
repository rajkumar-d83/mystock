"""Data quality checks (see MYSTOCK_PRODUCT_SPEC.md §8). Each row-level check's SQL
returns "problem rows" — empty result = pass. Results (status, count, up to 10 examples)
are logged to metadata.data_quality every run, so quality trends are queryable over time,
not just the latest snapshot.

Usage:
    python -m mystock.etl.quality.run_data_quality_checks
"""
import json
import sys

from mystock.db import get_conn, etl_run

# Row-level checks: SQL returns problem rows (empty = pass). warn_at/fail_at are
# thresholds on the *count* of problem rows found.
ROW_CHECKS = [
    {
        "name": "missing_dates_gap",
        "table": "staging.stock_daily",
        "warn_at": 1,
        "fail_at": None,  # gaps happen for legitimately delisted/suspended stocks too — warn, don't fail
        "sql": """
            WITH gaps AS (
                SELECT symbol, trade_date,
                       trade_date - LAG(trade_date) OVER (PARTITION BY symbol ORDER BY trade_date) AS gap_days
                FROM staging.stock_daily
            )
            SELECT symbol, max(gap_days) AS max_gap_days
            FROM gaps
            GROUP BY symbol
            HAVING max(gap_days) > 15
            ORDER BY max_gap_days DESC
        """,
    },
    {
        "name": "cross_source_duplicate_dates",
        "table": "staging",
        "warn_at": 1,
        "fail_at": 1,  # window design guarantees zero overlap — any hit means a real bug
        "sql": """
            SELECT symbol, trade_date FROM staging.nse_stock_history_raw
            INTERSECT
            SELECT symbol, trade_date FROM staging.nse_bhavcopy_raw
        """,
    },
    {
        "name": "invalid_prices",
        "table": "staging.stock_daily",
        "warn_at": 1,
        "fail_at": 100,
        "sql": """
            SELECT symbol, trade_date, open, high, low, close
            FROM staging.stock_daily
            WHERE high < low
               OR open < 0 OR high < 0 OR low < 0 OR close < 0
               OR (close > 0 AND (close > high OR close < low))
        """,
    },
    {
        "name": "invalid_volume_delivery",
        "table": "staging.stock_daily",
        "warn_at": 1,
        "fail_at": 100,
        "sql": """
            SELECT symbol, trade_date, volume, delivery_qty, delivery_pct
            FROM staging.stock_daily
            WHERE volume < 0
               OR delivery_qty < 0
               OR delivery_pct < 0 OR delivery_pct > 100
               OR (delivery_qty IS NOT NULL AND volume IS NOT NULL AND delivery_qty > volume)
        """,
    },
    {
        "name": "missing_symbols",
        "table": "staging.equity_master",
        "warn_at": 1,
        "fail_at": None,  # expected to be large mid-backfill — informational, not a failure
        "sql": """
            SELECT em.symbol
            FROM staging.equity_master em
            WHERE NOT EXISTS (SELECT 1 FROM staging.stock_daily sd WHERE sd.symbol = em.symbol)
        """,
    },
    {
        "name": "schema_change_unknown_keys",
        "table": "staging.nse_bhavcopy_raw",
        "warn_at": 1,
        "fail_at": None,
        "sql": """
            WITH known_keys AS (
                SELECT unnest(ARRAY[
                    'SYMBOL','SERIES','DATE1','PREV_CLOSE','OPEN_PRICE','HIGH_PRICE','LOW_PRICE',
                    'LAST_PRICE','CLOSE_PRICE','AVG_PRICE','TTL_TRD_QNTY','TURNOVER_LACS',
                    'NO_OF_TRADES','DELIV_QTY','DELIV_PER',
                    'Src','ISIN','Rmks','Sgmt','BizDt','Rsvd1','Rsvd2','Rsvd3','Rsvd4','SsnId',
                    'LwPric','OptnTp','TradDt','XpryDt','ClsPric','HghPric','OpnPric','SctySrs',
                    'LastPric','StrkPric','TckrSymb','OpnIntrst','SttlmPric','TtlTrfVal',
                    'FinInstrmId','FinInstrmNm','FinInstrmTp','TtlTradgVol','UndrlygPric',
                    'NewBrdLotQty','PrvsClsgPric','ChngInOpnIntrst','TtlNbOfTxsExctd',
                    'FininstrmActlXpryDt'
                ]) AS k
            )
            SELECT DISTINCT bhr.trade_date, key AS unknown_key
            FROM staging.nse_bhavcopy_raw bhr, jsonb_object_keys(bhr.raw_payload) AS key
            WHERE key NOT IN (SELECT k FROM known_keys)
              AND bhr.trade_date >= current_date - 3
        """,
    },
    {
        "name": "referential_integrity",
        "table": "main.fact_daily_prices",
        "warn_at": 1,
        "fail_at": 1,  # FK constraints should make this structurally impossible — any hit is a real bug
        "sql": """
            SELECT fdp.security_key, fdp.date_key
            FROM main.fact_daily_prices fdp
            WHERE NOT EXISTS (SELECT 1 FROM main.dim_security ds WHERE ds.security_key = fdp.security_key)
               OR NOT EXISTS (SELECT 1 FROM main.dim_date dd WHERE dd.date_key = fdp.date_key)
        """,
    },
]

NULL_PCT_SQL = """
    SELECT
        count(*) AS total_rows,
        round(100.0 * count(*) FILTER (WHERE open IS NULL) / greatest(count(*), 1), 2) AS pct_null_open,
        round(100.0 * count(*) FILTER (WHERE close IS NULL) / greatest(count(*), 1), 2) AS pct_null_close,
        round(100.0 * count(*) FILTER (WHERE volume IS NULL) / greatest(count(*), 1), 2) AS pct_null_volume,
        round(100.0 * count(*) FILTER (WHERE vwap IS NULL) / greatest(count(*), 1), 2) AS pct_null_vwap,
        round(100.0 * count(*) FILTER (WHERE delivery_qty IS NULL) / greatest(count(*), 1), 2) AS pct_null_delivery_qty
    FROM staging.stock_daily
"""


def run_row_check(conn, check):
    with conn.cursor() as cur:
        cur.execute(check["sql"])
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
    n = len(rows)
    if check["fail_at"] is not None and n >= check["fail_at"]:
        status = "fail"
    elif n >= check["warn_at"]:
        status = "warn"
    else:
        status = "pass"
    examples = [dict(zip(cols, r)) for r in rows[:10]]
    return status, n, examples


def log_result(conn, check_name, table_name, status, metric_value, details):
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO metadata.data_quality (check_name, table_name, status, metric_value, details)
               VALUES (%s, %s, %s, %s, %s)""",
            (check_name, table_name, status, metric_value, json.dumps(details, default=str)),
        )
    conn.commit()


def run_null_percentage_check(conn):
    with conn.cursor() as cur:
        cur.execute(NULL_PCT_SQL)
        cols = [d[0] for d in cur.description]
        row = dict(zip(cols, cur.fetchone()))
    # open/close should basically never be null; volume/vwap/delivery can legitimately be
    # null (VWAP/delivery missing for UDIFF-format days)
    status = "fail" if (row["pct_null_open"] > 1 or row["pct_null_close"] > 1) else "pass"
    log_result(conn, "null_percentage", "staging.stock_daily", status, row["pct_null_open"], row)
    print(f"  null_percentage: {status} | {row}")


def main():
    conn = get_conn()
    with etl_run("data_quality_checks", {}) as run:
        fails = 0
        for check in ROW_CHECKS:
            status, n, examples = run_row_check(conn, check)
            log_result(conn, check["name"], check["table"], status, n, examples)
            print(f"  {check['name']}: {status} ({n} problem rows)")
            if status == "fail":
                fails += 1
        run_null_percentage_check(conn)
        run["rows"] = len(ROW_CHECKS) + 1

    conn.close()
    if fails:
        print(f"\n{fails} check(s) FAILED — see metadata.data_quality for details.")
        sys.exit(1)
    print("\nAll checks passed or within warn tolerance.")


if __name__ == "__main__":
    main()
