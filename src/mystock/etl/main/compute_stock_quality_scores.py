"""Stock quality scoring engine — 8-category weighted model (see
MYSTOCK_PRODUCT_SPEC.md §9 for the full sub-metric spec and rationale).

Every individual sub-metric is written to main.fact_stock_quality_metric (EAV: one row
per security x date x metric) rather than only a final rolled-up number — this makes it
possible to add/remove metrics without a schema change, inspect exactly why a stock
scored the way it did, and support multiple scoring "lenses" from the same underlying
data. main.fact_stock_quality_score is a DERIVED rollup computed FROM the metric table
(kept for fast top-level queries, not independently computed).

8-factor weight model:
  Business Quality & Moat 20%, Financial Strength 15%, Growth & Consistency 20%,
  Cash Flow & Capital Allocation 15%, Balance Sheet 10%, Governance 10%, Valuation 5%,
  Market Behaviour 5%.

A sub-metric with no data (promoter pledge, true qualitative moat, etc.) is EXCLUDED
from its category's average, not scored as 0 — missing information isn't evidence of a
problem.

Usage:
    python -m mystock.etl.main.compute_stock_quality_scores
"""
import json
import statistics
import sys
from datetime import date, timedelta

from mystock.db import get_conn, etl_run

WEIGHTS = {
    "business_quality": 0.20,
    "financial_strength": 0.15,
    "growth_consistency": 0.20,
    "cash_flow_capital_allocation": 0.15,
    "balance_sheet": 0.10,
    "governance": 0.10,
    "valuation": 0.05,
    "market_behaviour": 0.05,
}

# Best-effort mapping from our sector classification to a NIFTY sector index for
# relative-strength comparison. Sectors with no good dedicated index (Diversified,
# Forest Materials, Services, Telecommunication, Textiles) fall back to NIFTY 500.
SECTOR_INDEX_MAP = {
    "Automobile and Auto Components": "Nifty Auto",
    "Capital Goods": "Nifty Capital Goods",
    "Chemicals": "Nifty Chemicals",
    "Construction": "Nifty Construction",
    "Construction Materials": "Nifty Cement",
    "Consumer Durables": "Nifty Consumer Durables",
    "Consumer Services": "Nifty Consumer Services",
    "Fast Moving Consumer Goods": "Nifty FMCG",
    "Financial Services": "Nifty Financial Services",
    "Healthcare": "Nifty Healthcare Index",
    "Information Technology": "Nifty IT",
    "Media Entertainment & Publication": "Nifty Media",
    "Metals & Mining": "Nifty Metal",
    "Oil Gas & Consumable Fuels": "Nifty Oil & Gas",
    "Power": "Nifty Energy",
    "Realty": "Nifty Realty",
    "Utilities": "Nifty Energy",
}


# ---- Generic helpers ---------------------------------------------------------------

def band(value, bands, default=0.0):
    """bands: list of (threshold, score), sorted descending by threshold."""
    if value is None:
        return None
    for threshold, score in bands:
        if value >= threshold:
            return score
    return default


def cagr(first, last, years):
    # CAGR is undefined for negative endpoints — (negative/positive)**(fractional power)
    # silently returns a `complex` number in Python rather than raising, which then
    # blows up downstream comparisons (`>=` isn't defined between complex and int).
    # Guard BOTH endpoints, not just `first`.
    if first is None or last is None or first <= 0 or last <= 0 or years <= 0:
        return None
    try:
        result = (float(last) / float(first)) ** (1 / years) - 1
    except (ValueError, ZeroDivisionError):
        return None
    return result if isinstance(result, float) else None


def cagr_from_points(points):
    """points: list of (date, value). Uses the oldest/newest points that actually HAVE
    a value — not blind list indexing (yfinance's oldest period sometimes has a null
    field even when later periods are populated)."""
    usable = sorted((d, float(v)) for d, v in points if v is not None)
    if len(usable) < 2:
        return None
    oldest_date, oldest_val = usable[0]
    newest_date, newest_val = usable[-1]
    years = (newest_date - oldest_date).days / 365.25
    return cagr(oldest_val, newest_val, years)


def stddev(values):
    vals = [float(v) for v in values if v is not None]
    if len(vals) < 2:
        return None
    return statistics.stdev(vals)


def avg_available(metrics):
    """metrics: list of (name, score, weight) where score may be None. Returns
    (weighted_avg, completeness_pct)."""
    available = [(s, w) for _, s, w in metrics if s is not None]
    if not available:
        return None, 0.0
    weighted_sum = sum(s * w for s, w in available)
    weight_sum = sum(w for _, w in available)
    return weighted_sum / weight_sum, 100.0 * len(available) / len(metrics)


class MetricSink:
    """Collects (metric_name, raw_value, score, weight, notes) tuples for one category
    so they can be written to the EAV table and rolled up in one pass."""

    def __init__(self):
        self.rows = []

    def add(self, name, raw_value, score, weight=1.0, notes=None):
        self.rows.append((name, raw_value, score, weight, notes))

    def rollup(self):
        return avg_available([(n, s, w) for n, _, s, w, _ in self.rows])


# ---- Data access --------------------------------------------------------------------

def fetch_symbols(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT symbol FROM staging.company_fundamentals_snapshot")
        return [r[0] for r in cur.fetchall()]


def fetch_snapshot(conn, symbol):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT trailing_pe, forward_pe, price_to_book, debt_to_equity,
                      return_on_equity, return_on_assets, profit_margin, operating_margin,
                      dividend_yield, payout_ratio, market_cap, current_ratio, quick_ratio
               FROM staging.company_fundamentals_snapshot
               WHERE symbol = %s ORDER BY snapshot_date DESC LIMIT 1""",
            (symbol,),
        )
        row = cur.fetchone()
    if not row:
        return None
    cols = ["trailing_pe", "forward_pe", "price_to_book", "debt_to_equity", "return_on_equity",
            "return_on_assets", "profit_margin", "operating_margin", "dividend_yield",
            "payout_ratio", "market_cap", "current_ratio", "quick_ratio"]
    return dict(zip(cols, row))


def fetch_annual_financials(conn, symbol):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT period_end_date, total_revenue, net_income, ebitda, ebit,
                      interest_expense, cost_of_revenue, total_debt, stockholders_equity,
                      invested_capital, current_liabilities, inventory, accounts_receivable,
                      accounts_payable, cash_and_equivalents, free_cash_flow, operating_cash_flow,
                      shares_outstanding, total_assets, net_share_issuance
               FROM staging.company_financials
               WHERE symbol = %s AND period_type = 'annual'
               ORDER BY period_end_date DESC""",
            (symbol,),
        )
        rows = cur.fetchall()
    cols = ["period_end_date", "total_revenue", "net_income", "ebitda", "ebit",
            "interest_expense", "cost_of_revenue", "total_debt", "stockholders_equity",
            "invested_capital", "current_liabilities", "inventory", "accounts_receivable",
            "accounts_payable", "cash_and_equivalents", "free_cash_flow", "operating_cash_flow",
            "shares_outstanding", "total_assets", "net_share_issuance"]
    return [dict(zip(cols, r)) for r in rows]


def fetch_dividends(conn, symbol):
    with conn.cursor() as cur:
        cur.execute("SELECT ex_date, dividend FROM staging.company_dividends WHERE symbol=%s ORDER BY ex_date", (symbol,))
        return cur.fetchall()


def fetch_sector_avg_pe(conn):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT ds.sector_key, avg(s.trailing_pe)
               FROM staging.company_fundamentals_snapshot s
               JOIN main.dim_security ds ON ds.symbol = s.symbol
               WHERE s.trailing_pe IS NOT NULL AND s.trailing_pe > 0
               GROUP BY ds.sector_key"""
        )
        return dict(cur.fetchall())


def fetch_symbol_meta(conn, symbol):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT ds.security_key, ds.sector_key, dsec.industry
               FROM main.dim_security ds LEFT JOIN main.dim_sector dsec ON dsec.sector_key = ds.sector_key
               WHERE ds.symbol = %s""",
            (symbol,),
        )
        return cur.fetchone()


def fetch_price_series(conn, symbol, since_date):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT dd.full_date, fdp.close, fv.volume, fde.delivery_pct
               FROM main.fact_daily_prices fdp
               JOIN main.dim_security ds ON ds.security_key = fdp.security_key
               JOIN main.dim_date dd ON dd.date_key = fdp.date_key
               LEFT JOIN main.fact_volume fv ON fv.security_key=fdp.security_key AND fv.date_key=fdp.date_key
               LEFT JOIN main.fact_delivery fde ON fde.security_key=fdp.security_key AND fde.date_key=fdp.date_key
               WHERE ds.symbol = %s AND dd.full_date >= %s
               ORDER BY dd.full_date""",
            (symbol, since_date),
        )
        return cur.fetchall()


def fetch_index_series(conn, index_name, since_date):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT dd.full_date, fid.close_value
               FROM main.fact_index_daily fid
               JOIN main.dim_index di ON di.index_key = fid.index_key
               JOIN main.dim_date dd ON dd.date_key = fid.date_key
               WHERE di.index_name = %s AND dd.full_date >= %s
               ORDER BY dd.full_date""",
            (index_name, since_date),
        )
        return cur.fetchall()


def snapshot_raw(conn, symbol):
    with conn.cursor() as cur:
        cur.execute("SELECT raw_payload FROM staging.yf_company_snapshot_raw WHERE symbol=%s ORDER BY snapshot_date DESC LIMIT 1", (symbol,))
        row = cur.fetchone()
    return row[0] if row else {}


# ---- Category scorers ----------------------------------------------------------------

def score_business_quality(annuals):
    m = MetricSink()
    margins = [(a["period_end_date"], float(a["ebit"]) / float(a["total_revenue"]))
               for a in annuals if a.get("ebit") and a.get("total_revenue")]
    if len(margins) >= 2:
        vals = [v for _, v in margins]
        min_margin = min(vals)
        m.add("sustained_margin_proxy", min_margin * 100,
              band(min_margin * 100, [(15, 100), (8, 60)], default=20))
        sd = stddev(vals)
        if sd is not None:
            m.add("margin_stability", sd * 100,
                  band(-sd * 100, [(-2, 100), (-4, 75), (-6, 50), (-10, 25)], default=10))
    else:
        m.add("sustained_margin_proxy", None, None)
        m.add("margin_stability", None, None)

    roce_points = [(a["period_end_date"], float(a["ebit"]) / float(a["invested_capital"]))
                   for a in annuals if a.get("ebit") and a.get("invested_capital")]
    if len(roce_points) >= 2:
        vals = [v for _, v in roce_points]
        min_roce, sd = min(vals), stddev(vals)
        stability_penalty = band(-sd * 100, [(-3, 0), (-6, 10), (-10, 20)], default=30) if sd is not None else 15
        base = band(min_roce * 100, [(20, 100), (12, 70), (6, 40)], default=15)
        m.add("roce_stability", min_roce * 100, max(0, base - stability_penalty))
    else:
        m.add("roce_stability", None, None)

    m.add("brand_moat", None, None, notes="qualitative, not computable from current sources")
    m.add("industry_leadership", None, None, notes="no market-share data source identified")

    score, completeness = m.rollup()
    return score, completeness, m.rows


def score_financial_strength(snap, annuals):
    m = MetricSink()
    latest = annuals[0] if annuals else {}

    roe = snap.get("return_on_equity")
    m.add("roe", roe * 100 if roe is not None else None,
          band(roe * 100 if roe is not None else None, [(20, 100), (15, 75), (10, 50), (5, 25)], default=10))

    roce = None
    if latest.get("ebit") and latest.get("invested_capital"):
        roce = float(latest["ebit"]) / float(latest["invested_capital"])
    m.add("roce", roce * 100 if roce is not None else None,
          band(roce * 100 if roce is not None else None, [(25, 100), (18, 75), (12, 50), (6, 25)], default=10))

    opm = snap.get("operating_margin")
    m.add("operating_margin", opm * 100 if opm is not None else None,
          band(opm * 100 if opm is not None else None, [(25, 100), (18, 75), (12, 50), (6, 25)], default=10))

    npm = snap.get("profit_margin")
    m.add("net_profit_margin", npm * 100 if npm is not None else None,
          band(npm * 100 if npm is not None else None, [(20, 100), (15, 75), (10, 50), (5, 25)], default=10))

    ic = None
    if latest.get("ebit") and latest.get("interest_expense"):
        ic = float(latest["ebit"]) / float(latest["interest_expense"])
    m.add("interest_coverage", ic, band(ic, [(10, 100), (5, 70), (2, 40)], default=15))

    score, completeness = m.rollup()
    return score, completeness, m.rows


def score_growth_consistency(annuals):
    m = MetricSink()
    revenue_points = [(a["period_end_date"], a.get("total_revenue")) for a in annuals]
    profit_points = [(a["period_end_date"], a.get("net_income")) for a in annuals]

    rev_cagr = cagr_from_points(revenue_points)
    m.add("revenue_cagr", rev_cagr * 100 if rev_cagr is not None else None,
          band(rev_cagr * 100 if rev_cagr is not None else None, [(15, 100), (12, 80), (8, 60), (4, 40)], default=15))

    profit_cagr_val = cagr_from_points(profit_points)
    m.add("profit_cagr", profit_cagr_val * 100 if profit_cagr_val is not None else None,
          band(profit_cagr_val * 100 if profit_cagr_val is not None else None, [(20, 100), (15, 80), (10, 60), (5, 40)], default=15))

    # Earnings Consistency Score: fraction of YoY periods with positive revenue growth,
    # positive profit growth, and positive operating cash flow simultaneously.
    sorted_annuals = sorted(annuals, key=lambda a: a["period_end_date"])
    yoy_checks = []
    for prev, curr in zip(sorted_annuals, sorted_annuals[1:]):
        rev_grew = curr.get("total_revenue") is not None and prev.get("total_revenue") is not None and curr["total_revenue"] > prev["total_revenue"]
        profit_grew = curr.get("net_income") is not None and prev.get("net_income") is not None and curr["net_income"] > prev["net_income"]
        ocf_positive = curr.get("operating_cash_flow") is not None and curr["operating_cash_flow"] > 0
        yoy_checks.append(rev_grew and profit_grew and ocf_positive)
    if yoy_checks:
        consistency_frac = sum(yoy_checks) / len(yoy_checks)
        consistency_score = 100 if consistency_frac >= 1.0 else (80 if consistency_frac >= 0.75 else (60 if consistency_frac >= 0.5 else 30))
        m.add("earnings_consistency", consistency_frac * 100, consistency_score,
              notes=f"{sum(yoy_checks)}/{len(yoy_checks)} YoY periods with simultaneous revenue+profit growth and positive OCF")
    else:
        m.add("earnings_consistency", None, None)

    score, completeness = m.rollup()
    return score, completeness, m.rows, profit_cagr_val


def score_cash_flow_capital_allocation(annuals, dividends):
    m = MetricSink()
    latest = annuals[0] if annuals else {}

    fcf_years = [a for a in annuals if a.get("free_cash_flow") is not None]
    if fcf_years:
        positive_frac = sum(1 for a in fcf_years if a["free_cash_flow"] > 0) / len(fcf_years)
        m.add("fcf_consistency", positive_frac * 100, positive_frac * 100)
    else:
        m.add("fcf_consistency", None, None)

    fcf_cagr_val = cagr_from_points([(a["period_end_date"], a.get("free_cash_flow")) for a in annuals])
    m.add("fcf_cagr", fcf_cagr_val * 100 if fcf_cagr_val is not None else None,
          band(fcf_cagr_val * 100 if fcf_cagr_val is not None else None, [(15, 100), (8, 70), (0, 50)], default=20))

    ocf_np_ratios = [float(a["operating_cash_flow"]) / float(a["net_income"])
                     for a in annuals if a.get("operating_cash_flow") and a.get("net_income") and a["net_income"] != 0]
    if ocf_np_ratios:
        avg_ratio = sum(ocf_np_ratios) / len(ocf_np_ratios)
        m.add("ocf_vs_net_profit", avg_ratio, band(avg_ratio, [(1.2, 100), (1.0, 80), (0.8, 50), (0.5, 25)], default=10))
    else:
        m.add("ocf_vs_net_profit", None, None)

    accrual_ratio = None
    if latest.get("net_income") is not None and latest.get("operating_cash_flow") is not None and latest.get("total_assets"):
        accrual_ratio = (float(latest["net_income"]) - float(latest["operating_cash_flow"])) / float(latest["total_assets"])
    m.add("accrual_ratio", accrual_ratio,
          band(-accrual_ratio if accrual_ratio is not None else None, [(0.0, 100), (-0.03, 70), (-0.06, 40)], default=15) if accrual_ratio is not None else None,
          notes="(Net Income - OCF) / Total Assets — lower/negative is better, high positive suggests profits not backed by cash")

    debt_points = [(a["period_end_date"], a.get("total_debt")) for a in annuals]
    debt_cagr_val = cagr_from_points(debt_points)
    debt_trend_score = None
    if debt_cagr_val is not None:
        debt_trend_score = band(-debt_cagr_val * 100, [(5, 100), (0, 75), (-10, 50)], default=25)
    m.add("debt_trend", debt_cagr_val * 100 if debt_cagr_val is not None else None, debt_trend_score,
          notes="CAGR of total debt — negative (shrinking debt) scores higher")

    shares_points = [(a["period_end_date"], a.get("shares_outstanding")) for a in annuals]
    shares_cagr_val = cagr_from_points(shares_points)
    dilution_score = None
    if shares_cagr_val is not None:
        dilution_score = band(-shares_cagr_val * 100, [(0, 100), (-2, 70), (-5, 40)], default=15)
    m.add("share_dilution", shares_cagr_val * 100 if shares_cagr_val is not None else None, dilution_score,
          notes="CAGR of shares outstanding — growth (dilution) scores lower")

    # Capital Allocation Score: composite of the debt/dilution/FCF trend signals above —
    # kept as its own explicit metric even though it overlaps with debt_trend/
    # share_dilution/fcf_cagr individually.
    composite_inputs = [s for s in (debt_trend_score, dilution_score,
                                     band(fcf_cagr_val * 100, [(10, 100), (0, 70)], default=30) if fcf_cagr_val is not None else None)
                         if s is not None]
    capital_allocation_score = sum(composite_inputs) / len(composite_inputs) if composite_inputs else None
    m.add("capital_allocation_composite", None, capital_allocation_score,
          notes="composite of debt trend + dilution + FCF trend")

    if dividends:
        years_with_dividend = len({d.year for d, _ in dividends})
        div_cagr_val = None
        by_year = {}
        for d, amt in dividends:
            by_year.setdefault(d.year, 0.0)
            by_year[d.year] += float(amt)
        if len(by_year) >= 2:
            years_sorted = sorted(by_year)
            div_cagr_val = cagr(by_year[years_sorted[0]], by_year[years_sorted[-1]], years_sorted[-1] - years_sorted[0]) \
                if years_sorted[-1] > years_sorted[0] else None
        dq_score = band(years_with_dividend, [(10, 100), (5, 70), (2, 40)], default=20)
        m.add("dividend_quality", years_with_dividend, dq_score,
              notes=f"{years_with_dividend} distinct years with a dividend on file; dividend amount CAGR={div_cagr_val}")
    else:
        m.add("dividend_quality", 0, 20, notes="no dividend history on file — could be a genuine non-payer, not necessarily bad")

    score, completeness = m.rollup()
    return score, completeness, m.rows


def score_balance_sheet(snap, annuals):
    m = MetricSink()
    latest = annuals[0] if annuals else {}

    de = snap.get("debt_to_equity")
    m.add("debt_to_equity", de, band(-float(de) if de is not None else None, [(-0.5, 100), (-1.0, 70), (-1.5, 40)], default=15) if de is not None else None)

    ccc = None
    if latest.get("inventory") and latest.get("cost_of_revenue") and latest.get("accounts_receivable") \
            and latest.get("total_revenue") and latest.get("accounts_payable"):
        inv_days = float(latest["inventory"]) / float(latest["cost_of_revenue"]) * 365
        debtor_days = float(latest["accounts_receivable"]) / float(latest["total_revenue"]) * 365
        creditor_days = float(latest["accounts_payable"]) / float(latest["cost_of_revenue"]) * 365
        ccc = inv_days + debtor_days - creditor_days
    m.add("cash_conversion_cycle", ccc, band(-ccc if ccc is not None else None, [(-30, 100), (-60, 75), (-90, 50), (-120, 25)], default=10) if ccc is not None else None)

    ccc_series = []
    for a in annuals:
        if a.get("inventory") and a.get("cost_of_revenue") and a.get("accounts_receivable") and a.get("total_revenue") and a.get("accounts_payable"):
            inv_d = float(a["inventory"]) / float(a["cost_of_revenue"]) * 365
            deb_d = float(a["accounts_receivable"]) / float(a["total_revenue"]) * 365
            cred_d = float(a["accounts_payable"]) / float(a["cost_of_revenue"]) * 365
            ccc_series.append((a["period_end_date"], inv_d + deb_d - cred_d))
    wc_trend_cagr = cagr_from_points(ccc_series) if len(ccc_series) >= 2 else None
    m.add("working_capital_trend", wc_trend_cagr * 100 if wc_trend_cagr is not None else None,
          band(-wc_trend_cagr * 100 if wc_trend_cagr is not None else None, [(0, 100), (-10, 70), (-25, 40)], default=20) if wc_trend_cagr is not None else None,
          notes="CAGR of cash conversion cycle — shrinking CCC (negative) scores higher; sudden deterioration (rising) often precedes stress")

    score, completeness = m.rollup()
    return score, completeness, m.rows


def score_governance(snap_raw):
    m = MetricSink()
    insiders = snap_raw.get("heldPercentInsiders")
    insider_score = None
    if insiders is not None:
        pct = insiders * 100
        insider_score = 100 if 40 <= pct <= 75 else (60 if 25 <= pct < 90 else 20)
    m.add("promoter_holding_proxy", insiders * 100 if insiders is not None else None, insider_score,
          notes="Yahoo's 'insider' classification, an approximation of SEBI's Promoter category")

    institutions = snap_raw.get("heldPercentInstitutions")
    m.add("institutional_holding_proxy", institutions * 100 if institutions is not None else None,
          band(institutions * 100 if institutions is not None else None, [(30, 100), (15, 70), (5, 40)], default=20))

    m.add("institutional_trend", None, None,
          notes="mechanism supported (snapshot table is dated), but too few repeated snapshots exist yet to compute a real trend")
    m.add("promoter_pledge", None, None, notes="not available from any current source")
    m.add("governance_red_flags", None, None, notes="requires reading filings/annual reports — not available from current sources")

    score, completeness = m.rollup()
    return score, completeness, m.rows


def score_valuation(snap, sector_avg_pe, sector_key, profit_cagr_val):
    m = MetricSink()
    pe = snap.get("trailing_pe")
    sector_avg = sector_avg_pe.get(sector_key) if sector_key else None
    pe_score = None
    if pe is not None and pe > 0 and sector_avg:
        ratio = float(pe) / float(sector_avg)
        pe_score = band(-ratio, [(-0.7, 100), (-0.9, 75), (-1.1, 50), (-1.3, 25)], default=10)
    m.add("pe_vs_sector", pe, pe_score)

    pb = snap.get("price_to_book")
    m.add("price_to_book", pb, band(-float(pb) if pb is not None and pb > 0 else None, [(-1, 100), (-3, 70), (-5, 40)], default=20) if pb is not None and pb > 0 else None)

    peg = None
    if pe is not None and pe > 0 and profit_cagr_val is not None and profit_cagr_val > 0:
        peg = float(pe) / (profit_cagr_val * 100)
    m.add("peg_ratio", peg, band(-peg if peg is not None else None, [(-1.0, 100), (-1.5, 70), (-2.0, 40)], default=20) if peg is not None else None,
          notes="uses profit_cagr as the growth-rate input")

    score, completeness = m.rollup()
    return score, completeness, m.rows


def score_market_behaviour(conn, symbol, sector_key, industry):
    m = MetricSink()
    today = date.today()

    windows = {"6m": 182, "1y": 365, "3y": 365 * 3}
    index_name = SECTOR_INDEX_MAP.get(industry, "Nifty 500")

    stock_series = fetch_price_series(conn, symbol, today - timedelta(days=365 * 3 + 30))
    nifty50_series = fetch_index_series(conn, "Nifty 50", today - timedelta(days=365 * 3 + 30))
    sector_series = fetch_index_series(conn, index_name, today - timedelta(days=365 * 3 + 30))

    def return_over(series, days):
        if not series:
            return None
        cutoff = today - timedelta(days=days)
        in_window = [(d, v) for d, v in series if d >= cutoff and v is not None]
        if len(in_window) < 2:
            return None
        return float(in_window[-1][1]) / float(in_window[0][1]) - 1

    rel_strength_scores = []
    for label, days in windows.items():
        stock_ret = return_over([(d, c) for d, c, *_ in stock_series], days)
        nifty_ret = return_over(nifty50_series, days)
        if stock_ret is not None and nifty_ret is not None:
            outperformance = stock_ret - nifty_ret
            s = band(outperformance * 100, [(10, 100), (0, 70), (-10, 40)], default=15)
            rel_strength_scores.append(s)
            m.add(f"relative_strength_vs_nifty50_{label}", outperformance * 100, s)
        else:
            m.add(f"relative_strength_vs_nifty50_{label}", None, None)

    if rel_strength_scores:
        m.add("relative_strength_composite", None, sum(rel_strength_scores) / len(rel_strength_scores),
              notes=f"vs sector index {index_name}")
    else:
        m.add("relative_strength_composite", None, None)

    closes = [float(c) for _, c, *_ in stock_series if c is not None]
    if len(closes) >= 30:
        daily_returns = [(closes[i] / closes[i - 1] - 1) for i in range(1, len(closes)) if closes[i - 1]]
        vol = stddev(daily_returns)
        annualized_vol = vol * (252 ** 0.5) if vol is not None else None
        peak = closes[0]
        max_dd = 0.0
        for c in closes:
            peak = max(peak, c)
            max_dd = min(max_dd, (c / peak - 1))
        vol_score = band(-annualized_vol * 100 if annualized_vol is not None else None, [(-25, 100), (-40, 70), (-60, 40)], default=20) if annualized_vol is not None else None
        dd_score = band(max_dd * 100, [(-15, 100), (-30, 70), (-50, 40)], default=20)
        combined_vol_score = (vol_score + dd_score) / 2 if vol_score is not None else dd_score
        m.add("volatility_annualized", annualized_vol * 100 if annualized_vol is not None else None, vol_score)
        m.add("max_drawdown_3y", max_dd * 100, dd_score)
    else:
        m.add("volatility_annualized", None, None)
        m.add("max_drawdown_3y", None, None)

    recent = stock_series[-60:] if len(stock_series) >= 60 else stock_series
    delivery_vals = [float(dp) for _, _, _, dp in recent if dp is not None]
    if delivery_vals:
        avg_delivery = sum(delivery_vals) / len(delivery_vals)
        half = len(recent) // 2
        if half >= 5:
            first_half_delivery = [float(dp) for _, _, _, dp in recent[:half] if dp is not None]
            second_half_delivery = [float(dp) for _, _, _, dp in recent[half:] if dp is not None]
            first_half_close = [float(c) for _, c, _, _ in recent[:half] if c is not None]
            second_half_close = [float(c) for _, c, _, _ in recent[half:] if c is not None]
            delivery_rising = second_half_delivery and first_half_delivery and \
                (sum(second_half_delivery) / len(second_half_delivery)) > (sum(first_half_delivery) / len(first_half_delivery))
            price_rising = second_half_close and first_half_close and \
                (sum(second_half_close) / len(second_half_close)) > (sum(first_half_close) / len(first_half_close))
            accumulation_signal = delivery_rising and price_rising
            m.add("delivery_trend_score", avg_delivery, 100 if accumulation_signal else (60 if delivery_rising or price_rising else 40),
                  notes="delivery% and price both rising together suggests institutional accumulation, not just speculative volume")
        else:
            m.add("delivery_trend_score", avg_delivery, band(avg_delivery, [(60, 100), (40, 70), (25, 50)], default=30))
    else:
        m.add("delivery_trend_score", None, None)

    score, completeness = m.rollup()
    return score, completeness, m.rows


# ---- Percentile ranking ---------------------------------------------------------------

def percentile_rank(value, all_values):
    if value is None:
        return None
    sorted_vals = sorted(v for v in all_values if v is not None)
    if not sorted_vals:
        return None
    rank = sum(1 for v in sorted_vals if v <= value)
    return 100.0 * rank / len(sorted_vals)


# ---- Main -----------------------------------------------------------------------------

def write_metrics(conn, security_key, score_date, category, rows):
    if not rows:
        return
    with conn.cursor() as cur:
        for name, raw_value, score, weight, notes in rows:
            cur.execute(
                """INSERT INTO main.fact_stock_quality_metric
                       (security_key, score_date_key, category, metric_name, raw_value,
                        normalized_score, weight, data_available, notes)
                   SELECT ds.security_key, dd.date_key, %s, %s, %s, %s, %s, %s, %s
                   FROM main.dim_security ds, main.dim_date dd
                   WHERE ds.security_key = %s AND dd.full_date = %s
                   ON CONFLICT (security_key, score_date_key, metric_name) DO UPDATE SET
                       raw_value = EXCLUDED.raw_value, normalized_score = EXCLUDED.normalized_score,
                       weight = EXCLUDED.weight, data_available = EXCLUDED.data_available,
                       notes = EXCLUDED.notes, computed_at = now()""",
                (category, name, raw_value, score, weight, score is not None, notes,
                 security_key, score_date),
            )
    conn.commit()


def main():
    conn = get_conn()
    symbols = fetch_symbols(conn)
    sector_avg_pe = fetch_sector_avg_pe(conn)
    today = date.today()

    results = []
    with etl_run("compute_stock_quality_scores", {"symbols": len(symbols)}) as run:
        for symbol in symbols:
            snap = fetch_snapshot(conn, symbol)
            if not snap:
                print(f"{symbol}: no snapshot, skipping", file=sys.stderr)
                continue
            annuals = fetch_annual_financials(conn, symbol)
            dividends = fetch_dividends(conn, symbol)
            meta = fetch_symbol_meta(conn, symbol)
            security_key, sector_key, industry = meta if meta else (None, None, None)
            snap_raw = snapshot_raw(conn, symbol)

            biz_score, biz_c, biz_rows = score_business_quality(annuals)
            fin_score, fin_c, fin_rows = score_financial_strength(snap, annuals)
            growth_score, growth_c, growth_rows, profit_cagr_val = score_growth_consistency(annuals)
            cfca_score, cfca_c, cfca_rows = score_cash_flow_capital_allocation(annuals, dividends)
            bs_score, bs_c, bs_rows = score_balance_sheet(snap, annuals)
            gov_score, gov_c, gov_rows = score_governance(snap_raw)
            val_score, val_c, val_rows = score_valuation(snap, sector_avg_pe, sector_key, profit_cagr_val)
            mkt_score, mkt_c, mkt_rows = score_market_behaviour(conn, symbol, sector_key, industry)

            write_metrics(conn, security_key, today, "business_quality", biz_rows)
            write_metrics(conn, security_key, today, "financial_strength", fin_rows)
            write_metrics(conn, security_key, today, "growth_consistency", growth_rows)
            write_metrics(conn, security_key, today, "cash_flow_capital_allocation", cfca_rows)
            write_metrics(conn, security_key, today, "balance_sheet", bs_rows)
            write_metrics(conn, security_key, today, "governance", gov_rows)
            write_metrics(conn, security_key, today, "valuation", val_rows)
            write_metrics(conn, security_key, today, "market_behaviour", mkt_rows)

            category_scores = {
                "business_quality": (biz_score, biz_c), "financial_strength": (fin_score, fin_c),
                "growth_consistency": (growth_score, growth_c), "cash_flow_capital_allocation": (cfca_score, cfca_c),
                "balance_sheet": (bs_score, bs_c), "governance": (gov_score, gov_c),
                "valuation": (val_score, val_c), "market_behaviour": (mkt_score, mkt_c),
            }
            weighted_sum = sum(s * WEIGHTS[c] for c, (s, _) in category_scores.items() if s is not None)
            weight_sum = sum(WEIGHTS[c] for c, (s, _) in category_scores.items() if s is not None)
            overall = weighted_sum / weight_sum if weight_sum > 0 else None
            overall_completeness = sum(c for _, c in category_scores.values()) / len(category_scores)

            results.append({
                "symbol": symbol, "security_key": security_key, "sector_key": sector_key,
                "biz": biz_score, "fin": fin_score, "growth": growth_score, "cfca": cfca_score,
                "bs": bs_score, "gov": gov_score, "val": val_score, "mkt": mkt_score,
                "overall": overall, "completeness": overall_completeness,
            })
            run["rows"] += 1

        # Percentile ranking needs every company's overall score computed first.
        all_overall = [r["overall"] for r in results]
        by_sector = {}
        for r in results:
            by_sector.setdefault(r["sector_key"], []).append(r["overall"])

        with conn.cursor() as cur:
            for r in results:
                overall_pct = percentile_rank(r["overall"], all_overall)
                sector_pct = percentile_rank(r["overall"], by_sector.get(r["sector_key"], []))
                cur.execute(
                    """INSERT INTO main.fact_stock_quality_score
                           (security_key, score_date_key, business_quality_score,
                            financial_strength_score, growth_score, governance_score,
                            balance_sheet_score, valuation_score,
                            cash_flow_capital_allocation_score, market_behaviour_score,
                            overall_score, data_completeness_pct, sector_percentile,
                            overall_percentile, details)
                       SELECT ds.security_key, dd.date_key, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                       FROM main.dim_security ds, main.dim_date dd
                       WHERE ds.security_key = %s AND dd.full_date = %s
                       ON CONFLICT (security_key, score_date_key) DO UPDATE SET
                           business_quality_score = EXCLUDED.business_quality_score,
                           financial_strength_score = EXCLUDED.financial_strength_score,
                           growth_score = EXCLUDED.growth_score,
                           governance_score = EXCLUDED.governance_score,
                           balance_sheet_score = EXCLUDED.balance_sheet_score,
                           valuation_score = EXCLUDED.valuation_score,
                           cash_flow_capital_allocation_score = EXCLUDED.cash_flow_capital_allocation_score,
                           market_behaviour_score = EXCLUDED.market_behaviour_score,
                           overall_score = EXCLUDED.overall_score,
                           data_completeness_pct = EXCLUDED.data_completeness_pct,
                           sector_percentile = EXCLUDED.sector_percentile,
                           overall_percentile = EXCLUDED.overall_percentile,
                           details = EXCLUDED.details, computed_at = now()""",
                    (r["biz"], r["fin"], r["growth"], r["gov"], r["bs"], r["val"],
                     r["cfca"], r["mkt"], r["overall"], r["completeness"],
                     sector_pct, overall_pct, json.dumps({"note": "details now in main.fact_stock_quality_metric"}),
                     r["security_key"], today),
                )
                overall_str = f"{r['overall']:.1f}" if r["overall"] is not None else "N/A"
                pct_str = f"{overall_pct:.0f}" if overall_pct is not None else "N/A"
                print(f"{r['symbol']}: overall={overall_str} percentile={pct_str} completeness={r['completeness']:.0f}%")
        conn.commit()

    conn.close()


if __name__ == "__main__":
    main()
