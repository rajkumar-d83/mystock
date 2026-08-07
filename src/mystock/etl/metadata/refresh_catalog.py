"""Refreshes metadata.tables and metadata.columns by introspecting the actual
Postgres catalog for the staging/main/portfolio/metadata schemas — the warehouse
describing itself. Curated descriptions for the highest-value (mostly Main) columns
are layered on top of the introspected structure; everything else gets structure with
no description yet, to be filled in over time.

Idempotent — safe to re-run after any DDL change to pick up new/changed columns.

Usage:
    python -m mystock.etl.metadata.refresh_catalog
"""
import psycopg2.extras

from mystock.db import get_conn

SCHEMAS = ("staging", "main", "metadata", "portfolio")

TABLE_DESCRIPTIONS = {
    ("staging", "nse_equity_master"): "Raw NSE currently-listed equity master, as fetched (JSONB, schema-on-read).",
    ("staging", "nse_stock_history_raw"): "Raw per-symbol daily history from jugaad_data.stock_df (JSONB, schema-on-read).",
    ("staging", "nse_bhavcopy_raw"): "Raw whole-market daily bhavcopy, either BHAVDATA-FULL or UDIFF format (JSONB, schema-on-read).",
    ("staging", "equity_master"): "Cleaned, typed equity master.",
    ("staging", "stock_daily"): "Cleaned, typed daily OHLCV+delivery, EQ series only, reconciled from both raw sources.",
    ("staging", "sector_map"): "Symbol -> industry mapping from NSE's NIFTY Total Market constituent list.",
    ("main", "dim_date"): "Standard calendar dimension, 2000-2030, generated (not NSE-sourced).",
    ("main", "dim_security"): "One row per symbol (Type 1 SCD, no history tracking).",
    ("main", "dim_sector"): "Distinct industries from staging.sector_map.",
    ("main", "dim_exchange"): "Single-row NSE placeholder dimension.",
    ("main", "fact_daily_prices"): "Daily OHLC + LTP/VWAP at security x date grain.",
    ("main", "fact_volume"): "Daily volume/turnover/trade-count at security x date grain.",
    ("main", "fact_delivery"): "Daily delivery qty/pct at security x date grain. NULL on UDIFF-format days (no delivery data in that source format).",
    ("metadata", "etl_runs"): "Every ETL job run: start/end/status/rows/error.",
    ("metadata", "data_quality"): "Data quality check results, logged every run for trend tracking.",
    ("staging", "amfi_mf_scheme_master"): "Mutual fund scheme metadata from mfapi.in (wraps AMFI), scoped to Direct+Growth plans across the top 10 AMCs by AUM plus Parag Parikh and one allowlisted Tata scheme.",
    ("staging", "amfi_mf_nav_history_raw"): "Raw daily NAV history per scheme, as received (JSONB, schema-on-read).",
    ("staging", "mf_scheme_master"): "Cleaned, typed mutual fund scheme metadata.",
    ("staging", "mf_nav_daily"): "Cleaned, typed daily NAV per scheme.",
    ("main", "dim_mf_scheme"): "One row per mutual fund scheme (Direct+Growth, target AMCs only).",
    ("main", "fact_mf_nav_daily"): "Daily NAV at scheme x date grain. No exchange_key — mutual funds (other than ETFs) aren't exchange-traded.",
    ("staging", "yf_company_snapshot_raw"): "Raw daily fundamentals snapshot (P/E, P/B, D/E, margins, etc.) from Yahoo Finance, NIFTY Total Market constituents.",
    ("staging", "yf_financials_raw"): "Raw annual/quarterly financial statements (income, balance sheet, cash flow) from Yahoo Finance, one row per symbol x statement_type x period_type x period.",
    ("staging", "yf_dividends_raw"): "Raw dividend payment history from Yahoo Finance.",
    ("staging", "company_fundamentals_snapshot"): "Cleaned, typed fundamentals ratios (P/E, D/E, ROE, margins, dividend yield, etc.).",
    ("staging", "company_financials"): "Cleaned, typed curated financial statement line items (revenue, net income, EBITDA, debt, equity, cash flow) — staging.yf_financials_raw has the full raw statement, this is a curated subset.",
    ("staging", "company_dividends"): "Cleaned, typed dividend payment history.",
    ("main", "fact_company_fundamentals"): "Daily fundamentals ratios at security x date grain, joined to the same dim_security as price/volume facts.",
    ("main", "fact_company_financials"): "Financial statement line items at security x statement_type x period_type x period grain.",
    ("main", "fact_company_dividends"): "Dividend payments at security x ex_date grain.",
    ("main", "fact_stock_quality_metric"): "EAV table: one row per security x date x sub-metric, the explainable inputs behind the quality score (see MYSTOCK_PRODUCT_SPEC.md §9).",
    ("main", "fact_stock_quality_score"): "Derived rollup of fact_stock_quality_metric — 8 category scores + overall score + percentile ranks. Never independently computed.",
    ("staging", "news_raw"): "Raw news headlines from Google News RSS, scoped to currently-held securities only.",
    ("staging", "news_sentiment"): "FinBERT-scored headlines (local inference) — sentiment_label + signed sentiment_score.",
    ("main", "fact_news_sentiment_daily"): "Per-security daily news aggregation (count, avg sentiment) — byproduct of compute_news_price_signal.",
    ("main", "fact_price_sentiment_signal"): "Per-security daily signal: abnormal price move (z-score vs trailing 20-day) corroborated (or not) by news sentiment.",
    ("main", "fact_sector_signal"): "Sector-level signal: abnormal equal-weighted return across a sector's held stocks.",
    ("portfolio", "portfolios"): "One row per broker/portfolio (e.g. 'Upstox').",
    ("portfolio", "users"): "Single-user system — one row, the portfolio owner.",
    ("portfolio", "transactions"): "Equity trades: OPENING_BALANCE (current holding snapshot, never summed with BUY/SELL — see MYSTOCK_PRODUCT_SPEC.md 'store facts once'), BUY, SELL, DIVIDEND rows.",
    ("portfolio", "mf_transactions"): "Mutual fund transactions, same OPENING_BALANCE/BUY/SELL pattern as transactions but at scheme grain.",
    ("portfolio", "mf_scheme_cost"): "Cost-basis tracking for mutual fund holdings.",
    ("portfolio", "import_staging_trades"): "Fuzzy-matched trade imports held for manual review before promotion — never auto-promoted to transactions (see import_trades_fuzzy.py safety design).",
    ("portfolio", "fact_portfolio_value_daily"): "Daily market value/cost basis/unrealized+realized P&L per portfolio, computed from OPENING_BALANCE holdings x that day's prices.",
    ("portfolio", "fact_portfolio_health"): "Daily weighted quality-score rollup + concentration metrics (top holding/sector %, score coverage %) per portfolio.",
    ("portfolio", "daily_alert"): "One human-readable daily digest per portfolio: value change, flagged stock/sector signals, plain-English summary — see compute_daily_alert.py.",
    ("portfolio", "broker_fee_schedule"): "Brokerage/fee rates used when computing realized P&L on sells.",
}

COLUMN_DESCRIPTIONS = {
    ("main", "fact_delivery", "delivery_qty"): "NULL on UDIFF-format bhavcopy days — that raw format has no delivery fields at all.",
    ("main", "dim_security", "sector_key"): "Nullable — only symbols covered by the NIFTY Total Market sector source have a value.",
    ("staging", "company_fundamentals_snapshot", "dividend_yield"): "Stored as-is from yfinance — inconsistent across versions/symbols about fraction (0.0046) vs percentage (0.46) convention, not renormalized.",
    ("main", "dim_security", "is_active"): "FALSE for symbols found in fact data but absent from the (currently-listed-only) equity master — likely delisted/renamed.",
    ("main", "dim_date", "is_trading_day"): "Backfilled from whether staging.stock_daily has any row for that date, not an independent NSE holiday calendar.",
    ("staging", "stock_daily", "source_system"): "'stock_df', 'bhavcopy_full', or 'bhavcopy_udiff' — which raw source shape this row was reconciled from.",
    ("main", "fact_stock_quality_score", "data_completeness_pct"): "What fraction of sub-metrics had usable data — a score's completeness matters as much as the score itself (see MYSTOCK_PRODUCT_SPEC.md §9, 'Handling missing data').",
}


def refresh_tables(conn):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT schemaname, relname, n_live_tup
               FROM pg_stat_user_tables
               WHERE schemaname = ANY(%s)""",
            (list(SCHEMAS),),
        )
        rows = cur.fetchall()
        values = [
            (schema, table, schema, TABLE_DESCRIPTIONS.get((schema, table)), row_count)
            for schema, table, row_count in rows
        ]
        psycopg2.extras.execute_values(
            cur,
            """INSERT INTO metadata.tables (schema_name, table_name, layer, description, row_count)
               VALUES %s
               ON CONFLICT (schema_name, table_name) DO UPDATE SET
                   layer = EXCLUDED.layer,
                   description = COALESCE(EXCLUDED.description, metadata.tables.description),
                   row_count = EXCLUDED.row_count,
                   last_refreshed = now()""",
            values,
        )
    conn.commit()
    return len(values)


def refresh_columns(conn):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT table_schema, table_name, column_name, ordinal_position, data_type,
                      is_nullable = 'YES'
               FROM information_schema.columns
               WHERE table_schema = ANY(%s)""",
            (list(SCHEMAS),),
        )
        rows = cur.fetchall()
        values = [
            (schema, table, col, pos, dtype, nullable,
             COLUMN_DESCRIPTIONS.get((schema, table, col)))
            for schema, table, col, pos, dtype, nullable in rows
        ]
        psycopg2.extras.execute_values(
            cur,
            """INSERT INTO metadata.columns
                   (schema_name, table_name, column_name, ordinal_position, data_type,
                    is_nullable, description)
               VALUES %s
               ON CONFLICT (schema_name, table_name, column_name) DO UPDATE SET
                   ordinal_position = EXCLUDED.ordinal_position,
                   data_type = EXCLUDED.data_type,
                   is_nullable = EXCLUDED.is_nullable,
                   description = COALESCE(EXCLUDED.description, metadata.columns.description),
                   last_refreshed = now()""",
            values,
        )
    conn.commit()
    return len(values)


def main():
    conn = get_conn()
    n_tables = refresh_tables(conn)
    n_columns = refresh_columns(conn)
    conn.close()
    print(f"Refreshed {n_tables} tables, {n_columns} columns in metadata.tables/columns")


if __name__ == "__main__":
    main()
