"""Computes one day's portfolio health snapshot (portfolio.fact_portfolio_health) per
portfolio: a holdings-value-weighted rollup of main.fact_stock_quality_score across the
portfolio's current equity holdings (from OPENING_BALANCE — same "current holdings"
convention as compute_portfolio_value_history.py). holdings_with_score_pct tracks what
fraction of holdings actually had a quality score to weight (some equities have
incomplete fundamentals data — see MYSTOCK_PRODUCT_SPEC.md §9, "Handling missing data").

Usage:
    python -m mystock.etl.portfolio.compute_portfolio_health                  # today, all portfolios
    python -m mystock.etl.portfolio.compute_portfolio_health --date 2026-08-03
    python -m mystock.etl.portfolio.compute_portfolio_health --portfolio-id 1
"""
import argparse
from datetime import date, datetime

from mystock.db import get_conn

SCORE_COLUMNS = [
    ("overall_score", "weighted_overall_score"),
    ("business_quality_score", "weighted_business_quality"),
    ("financial_strength_score", "weighted_financial_strength"),
    ("growth_score", "weighted_growth_consistency"),
    ("cash_flow_capital_allocation_score", "weighted_cash_flow_capital_allocation"),
    ("balance_sheet_score", "weighted_balance_sheet"),
    ("governance_score", "weighted_governance"),
    ("valuation_score", "weighted_valuation"),
    ("market_behaviour_score", "weighted_market_behaviour"),
]


def latest_trading_date_on_or_before(conn, target_date):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT max(dd.full_date) FROM main.dim_date dd
               WHERE dd.full_date <= %s
                 AND EXISTS (SELECT 1 FROM main.fact_daily_prices p WHERE p.date_key = dd.date_key)""",
            (target_date,),
        )
        return cur.fetchone()[0]


def latest_score_date_on_or_before(conn, target_date):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT max(dd.full_date) FROM main.dim_date dd
               WHERE dd.full_date <= %s
                 AND EXISTS (SELECT 1 FROM main.fact_stock_quality_score s WHERE s.score_date_key = dd.date_key)""",
            (target_date,),
        )
        return cur.fetchone()[0]


def compute_health(conn, portfolio_id, price_as_of, score_as_of):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT t.security_key, t.quantity, d.sector_key,
                      coalesce(fdp.close, t.price) AS price,
                      s.overall_score, s.business_quality_score, s.financial_strength_score,
                      s.growth_score, s.cash_flow_capital_allocation_score, s.balance_sheet_score,
                      s.governance_score, s.valuation_score, s.market_behaviour_score
               FROM portfolio.transactions t
               JOIN main.dim_security d ON d.security_key = t.security_key
               LEFT JOIN main.fact_daily_prices fdp
                      ON fdp.security_key = t.security_key
                     AND fdp.date_key = (SELECT date_key FROM main.dim_date WHERE full_date = %s)
               LEFT JOIN main.fact_stock_quality_score s
                      ON s.security_key = t.security_key
                     AND s.score_date_key = (SELECT date_key FROM main.dim_date WHERE full_date = %s)
               WHERE t.portfolio_id = %s AND t.transaction_type = 'OPENING_BALANCE'""",
            (price_as_of, score_as_of, portfolio_id),
        )
        holdings = cur.fetchall()

    if not holdings:
        return None

    values = [(row[0], float(row[1]) * float(row[3]), row[2], row[4:]) for row in holdings]
    total_value = sum(v for _, v, _, _ in values)
    if total_value <= 0:
        return None

    weighted = {col: 0.0 for _, col in SCORE_COLUMNS}
    weighted_weight = {col: 0.0 for _, col in SCORE_COLUMNS}
    scored_value = 0.0
    sector_totals = {}

    for security_key, value, sector_key, scores in values:
        sector_totals[sector_key] = sector_totals.get(sector_key, 0.0) + value
        overall = scores[0]
        if overall is not None:
            scored_value += value
        for (col_name, target_col), score in zip(SCORE_COLUMNS, scores):
            if score is not None:
                weighted[target_col] += value * float(score)
                weighted_weight[target_col] += value

    result = {
        col: round(weighted[col] / weighted_weight[col], 2) if weighted_weight[col] > 0 else None
        for _, col in SCORE_COLUMNS
    }
    top_holding_pct = round(100.0 * max(v for _, v, _, _ in values) / total_value, 2)
    top_sector_pct = round(100.0 * max(sector_totals.values()) / total_value, 2)
    holdings_with_score_pct = round(100.0 * scored_value / total_value, 2)
    return result, top_holding_pct, top_sector_pct, holdings_with_score_pct


def write_snapshot(conn, portfolio_id, as_of, result, top_holding_pct, top_sector_pct, holdings_with_score_pct):
    cols = ", ".join(col for _, col in SCORE_COLUMNS)
    placeholders = ", ".join(["%s"] * len(SCORE_COLUMNS))
    update_clause = ", ".join(f"{col} = EXCLUDED.{col}" for _, col in SCORE_COLUMNS)
    with conn.cursor() as cur:
        cur.execute(
            f"""INSERT INTO portfolio.fact_portfolio_health
                    (portfolio_id, date_key, {cols}, top_holding_pct, top_sector_pct, holdings_with_score_pct)
                SELECT %s, dd.date_key, {placeholders}, %s, %s, %s
                FROM main.dim_date dd WHERE dd.full_date = %s
                ON CONFLICT (portfolio_id, date_key) DO UPDATE SET
                    {update_clause}, top_holding_pct = EXCLUDED.top_holding_pct,
                    top_sector_pct = EXCLUDED.top_sector_pct,
                    holdings_with_score_pct = EXCLUDED.holdings_with_score_pct""",
            [portfolio_id] + [result[col] for _, col in SCORE_COLUMNS]
            + [top_holding_pct, top_sector_pct, holdings_with_score_pct, as_of],
        )
    conn.commit()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(), default=date.today())
    ap.add_argument("--portfolio-id", type=int, default=None)
    args = ap.parse_args()

    conn = get_conn()
    price_as_of = latest_trading_date_on_or_before(conn, args.date)
    score_as_of = latest_score_date_on_or_before(conn, args.date)
    if price_as_of is None or score_as_of is None:
        print(f"No price/score data on or before {args.date}; nothing to compute.")
        return

    with conn.cursor() as cur:
        if args.portfolio_id:
            cur.execute("SELECT portfolio_id, portfolio_name FROM portfolio.portfolios WHERE portfolio_id = %s",
                        (args.portfolio_id,))
        else:
            cur.execute("SELECT portfolio_id, portfolio_name FROM portfolio.portfolios")
        portfolios = cur.fetchall()

    for portfolio_id, name in portfolios:
        computed = compute_health(conn, portfolio_id, price_as_of, score_as_of)
        if computed is None:
            print(f"portfolio_id={portfolio_id} ({name}): no equity holdings, skipped")
            continue
        result, top_holding_pct, top_sector_pct, holdings_with_score_pct = computed
        write_snapshot(conn, portfolio_id, price_as_of, result, top_holding_pct, top_sector_pct, holdings_with_score_pct)
        print(f"portfolio_id={portfolio_id} ({name}) as_of={price_as_of} (scores as_of={score_as_of}): "
              f"overall={result['weighted_overall_score']} top_holding={top_holding_pct}% "
              f"top_sector={top_sector_pct}% coverage={holdings_with_score_pct}%")

    conn.close()


if __name__ == "__main__":
    main()
