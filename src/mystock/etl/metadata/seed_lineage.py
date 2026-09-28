"""Seeds metadata.lineage with the known raw -> staging -> main dependencies.
This is reference data describing the pipeline's actual structure (matches the
transform scripts in etl/staging and etl/main), not something introspected — update
this file by hand if the pipeline's data flow changes.

Usage:
    python -m mystock.etl.metadata.seed_lineage
"""
import psycopg2.extras

from mystock.db import get_conn

NO_SOURCE = "n/a"  # metadata.lineage's PK is NOT NULL on all 4 key columns, so a sentinel
                    # is used instead of NULL for tables with no raw source (generated or
                    # externally-fetched) — keeps ON CONFLICT idempotent.

LINEAGE = [
    ("staging", "equity_master", "staging", "nse_equity_master",
     "src/mystock/etl/staging/sql/01_equity_master.sql", "Typed/cleaned copy."),
    ("staging", "stock_daily", "staging", "nse_stock_history_raw",
     "src/mystock/etl/staging/sql/02_stock_daily_from_stock_history.sql", "Pre-2019-10 historical, EQ series only."),
    ("staging", "stock_daily", "staging", "nse_bhavcopy_raw",
     "src/mystock/etl/staging/sql/03_stock_daily_from_bhavcopy.sql", "2019-10 onward, EQ series only, reconciles BHAVDATA-FULL/UDIFF shapes."),
    ("staging", "sector_map", NO_SOURCE, NO_SOURCE,
     "src/mystock/etl/staging/load_sector_map.py", "External source: NSE's ind_niftytotalmarket_list.csv, not a raw table."),
    ("main", "dim_security", "staging", "equity_master",
     "src/mystock/etl/main/sql/01_dim_security.sql", "Type 1 SCD."),
    ("main", "dim_security", "staging", "sector_map",
     "src/mystock/etl/main/sql/01_dim_security.sql", "Joined in for sector_key."),
    ("main", "dim_security", "staging", "stock_daily",
     "src/mystock/etl/main/sql/01_dim_security.sql", "Source of placeholder rows for symbols missing from equity_master."),
    ("main", "dim_date", NO_SOURCE, NO_SOURCE,
     "src/mystock/etl/main/generate_dim_date.py", "Generated calendar, not derived from any source table."),
    ("main", "dim_sector", "staging", "sector_map",
     "manual (see MYSTOCK_PRODUCT_SPEC.md)", "Distinct industries, loaded once at setup."),
    ("main", "fact_daily_prices", "staging", "stock_daily",
     "src/mystock/etl/main/sql/03_fact_daily_prices.sql", None),
    ("main", "fact_volume", "staging", "stock_daily",
     "src/mystock/etl/main/sql/04_fact_volume.sql", None),
    ("main", "fact_delivery", "staging", "stock_daily",
     "src/mystock/etl/main/sql/05_fact_delivery.sql", "NULL delivery on UDIFF-sourced days."),
    ("staging", "company_fundamentals_snapshot", "staging", "yf_company_snapshot_raw",
     "src/mystock/etl/staging/sql/04_company_fundamentals_snapshot.sql", "Source: Yahoo Finance, not NSE."),
    ("staging", "company_financials", "staging", "yf_financials_raw",
     "src/mystock/etl/staging/sql/05_company_financials.sql", "Curated subset of ~50+ raw line items."),
    ("staging", "company_dividends", "staging", "yf_dividends_raw",
     "src/mystock/etl/staging/sql/06_company_dividends.sql", None),
    ("main", "fact_company_fundamentals", "staging", "company_fundamentals_snapshot",
     "src/mystock/etl/main/sql/06_fact_company_fundamentals.sql", "Joined to the existing main.dim_security, not a new company dimension."),
    ("main", "fact_company_financials", "staging", "company_financials",
     "src/mystock/etl/main/sql/07_fact_company_financials.sql", None),
    ("main", "fact_company_dividends", "staging", "company_dividends",
     "src/mystock/etl/main/sql/08_fact_company_dividends.sql", None),
    ("main", "fact_stock_quality_metric", "staging", "company_fundamentals_snapshot",
     "src/mystock/etl/main/compute_stock_quality_scores.py", "Also reads staging.company_financials, staging.company_dividends, main.fact_daily_prices/fact_index_daily."),
    ("main", "fact_stock_quality_score", "main", "fact_stock_quality_metric",
     "src/mystock/etl/main/compute_stock_quality_scores.py", "Derived rollup, never independently computed."),
    ("staging", "news_sentiment", "staging", "news_raw",
     "src/mystock/etl/staging/score_news_sentiment.py", "Local FinBERT inference."),
    ("main", "fact_news_sentiment_daily", "staging", "news_sentiment",
     "src/mystock/etl/main/compute_news_price_signal.py", "Byproduct of the price/sentiment signal computation."),
    ("main", "fact_price_sentiment_signal", "main", "fact_daily_prices",
     "src/mystock/etl/main/compute_news_price_signal.py", "Also reads staging.news_sentiment."),
    ("main", "fact_sector_signal", "main", "fact_daily_prices",
     "src/mystock/etl/main/compute_sector_signal.py", None),
    ("staging", "shareholding_pattern", "staging", "nse_shareholding_raw",
     "src/mystock/etl/staging/sql/08_shareholding_pattern.sql", "Source: NSE corporate filings (XBRL), currently-held securities only."),
    ("portfolio", "fact_mtf_position_daily", "portfolio", "mtf_positions",
     "src/mystock/etl/portfolio/compute_mtf_interest.py", "Also reads main.fact_daily_prices, portfolio.mtf_interest_slabs, portfolio.broker_fee_schedule."),
    ("main", "fact_shareholding_pattern", "staging", "shareholding_pattern",
     "src/mystock/etl/main/sql/11_fact_shareholding_pattern.sql", None),
]


def main():
    conn = get_conn()
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """INSERT INTO metadata.lineage
                   (target_schema, target_table, source_schema, source_table, transform_script, notes)
               VALUES %s
               ON CONFLICT (target_schema, target_table, source_schema, source_table) DO UPDATE SET
                   transform_script = EXCLUDED.transform_script,
                   notes = EXCLUDED.notes""",
            LINEAGE,
        )
    conn.commit()
    conn.close()
    print(f"Seeded {len(LINEAGE)} lineage rows")


if __name__ == "__main__":
    main()
