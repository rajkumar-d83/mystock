"""Fetches NSE quarterly shareholding-pattern filings (promoter/FII/DII/public %) for
every security currently held in any portfolio — holdings-scoped, like fetch_news.py,
not the whole scored universe (per-company shareholding data has no bulk/whole-market
download the way bhavcopy does; it's one API call + one XBRL filing per company).

Two-step fetch per symbol: NSE's shareholding-master endpoint lists each quarter's
filing (with a link to the full XBRL), then the XBRL itself is downloaded and parsed for
the percentage breakdown. The master-list endpoint only exposes a Promoter/Public split;
the FII vs DII (and further sub-category) breakdown only exists inside the XBRL.

XBRL parsing note: the percentage value tag (ShareholdingAsAPercentageOfTotalNumberOfShares)
is reused across every category, disambiguated by its contextRef -- but NSE's context IDs
are already human-readable (e.g. InstitutionsForeign_ContextI), so no context->member
indirection is needed, just a fixed contextRef -> field-name lookup. Verified against a
real filing (RELIANCE, Jun-2026): Promoter + Public summed to exactly 100%, and Public's
own sub-parts (DII + FII + Non-Institutions) summed close to Public's total -- confirms
the parse is correct, not coincidental.

Already-fetched (symbol, period_end_date) pairs are skipped before downloading the XBRL,
since re-fetching old quarters' ~500KB filings on every run would be pure waste.

Usage:
    python -m mystock.etl.historical.fetch_shareholding_pattern
"""
import json
import re
import sys
import time
import uuid
from datetime import datetime

import requests

from mystock.db import get_conn, etl_run

MASTER_URL = "https://www.nseindia.com/api/corporate-share-holdings-master"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-shareholding-pattern",
}

# NSE has used at least two XBRL taxonomy versions across the filing history (seen:
# 2022-09-30 and 2025-10-31, embedded in the xmlns:in-bse-shp URI) with different
# context-ID *suffix* conventions for the same concepts -- old filings use a bare "I"
# suffix (e.g. "PublicShareholdingI"), newer ones use "_ContextI" (e.g.
# "PublicShareholding_ContextI"). Matched by stripping whichever suffix is present and
# looking up the remaining concept name, rather than exact-matching the full ID, so both
# eras parse the same way. "Catergory" (sic) is NSE's own typo in the older taxonomy's
# FPI category context IDs -- kept as an alias, not a bug on this side.
CONCEPT_TO_FIELD = {
    "ShareholdingOfPromoterAndPromoterGroup": "promoter_pct",
    "PublicShareholding": "public_pct",
    "InstitutionsDomestic": "institutions_domestic_pct",
    "InstitutionsForeign": "institutions_foreign_pct",
    "NonInstitutions": "non_institutions_pct",
    "MutualFundsOrUTI": "mutual_funds_pct",
    "InsuranceCompanies": "insurance_pct",
    "InstitutionsForeignPortfolioInvestorCategoryOne": "fpi_category_1_pct",
    "InstitutionsForeignPortfolioInvestorCategoryTwo": "fpi_category_2_pct",
    "InstitutionsForeignPortfolioInvestorCatergoryOne": "fpi_category_1_pct",
    "InstitutionsForeignPortfolioInvestorCatergoryTwo": "fpi_category_2_pct",
}
TAG_RE = re.compile(
    r'<in-bse-shp:ShareholdingAsAPercentageOfTotalNumberOfShares contextRef="([^"]+)"[^>]*>([0-9.]+)<'
)


def context_field(context_id):
    if context_id.endswith("_ContextI"):
        concept = context_id[: -len("_ContextI")]
    elif context_id.endswith("I"):
        concept = context_id[:-1]
    else:
        return None
    return CONCEPT_TO_FIELD.get(concept)


def normalize_pct(raw_value):
    """Different filings encode this value inconsistently -- some as a fraction of 1
    (0.5072), some as an already-scaled percentage (50.72) -- with identical unitRef/
    decimals attributes, so there's no metadata to distinguish them. No real
    shareholding category can exceed 100% of shares, so a value already > 1 must be an
    already-scaled percentage; anything <= 1 is a fraction and needs x100."""
    v = float(raw_value)
    return round(v, 3) if v > 1 else round(v * 100, 3)


def make_session():
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        session.get("https://www.nseindia.com/", timeout=15)
    except requests.RequestException:
        pass  # best-effort cookie warm-up; the API call can still succeed without it
    return session


def current_holdings(conn):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT DISTINCT d.security_key, d.symbol, d.company_name
               FROM portfolio.transactions t
               JOIN main.dim_security d ON d.security_key = t.security_key
               WHERE t.transaction_type = 'OPENING_BALANCE'
               ORDER BY d.symbol"""
        )
        return cur.fetchall()


def already_fetched_keys(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT symbol, period_end_date FROM staging.nse_shareholding_raw")
        return {(symbol, period_end) for symbol, period_end in cur.fetchall()}


def parse_shareholding_xbrl(xml_text):
    result = {}
    for context_ref, value in TAG_RE.findall(xml_text):
        field = context_field(context_ref)
        if field:
            result[field] = normalize_pct(value)
    return result


def insert_raw(conn, symbol, period_end_date, raw_payload, submission_date, batch_id):
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO staging.nse_shareholding_raw
                   (symbol, period_end_date, raw_payload, submission_date, batch_id)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (symbol, period_end_date) DO UPDATE
                   SET raw_payload = EXCLUDED.raw_payload, submission_date = EXCLUDED.submission_date,
                       batch_id = EXCLUDED.batch_id, fetched_at = now()""",
            (symbol, period_end_date, json.dumps(raw_payload), submission_date, batch_id),
        )
    conn.commit()


def main():
    conn = get_conn()
    holdings = current_holdings(conn)
    have = already_fetched_keys(conn)
    session = make_session()
    batch_id = str(uuid.uuid4())

    print(f"{len(holdings)} current holdings to check for shareholding filings", flush=True)
    with etl_run("fetch_shareholding_pattern", {"holdings": len(holdings)}) as run:
        for security_key, symbol, company_name in holdings:
            try:
                resp = session.get(MASTER_URL, params={"index": "equities", "symbol": symbol}, timeout=20)
                resp.raise_for_status()
                filings = resp.json()
            except Exception as e:
                print(f"{symbol}: FAILED to fetch filing list - {e}", file=sys.stderr, flush=True)
                continue

            new_for_symbol = 0
            for filing in filings:
                xbrl_url = filing.get("xbrl")
                date_raw = filing.get("date")
                if not xbrl_url or not date_raw:
                    continue
                period_end_date = datetime.strptime(date_raw, "%d-%b-%Y").date()
                if (symbol, period_end_date) in have:
                    continue

                try:
                    xml_resp = session.get(xbrl_url, timeout=30)
                    xml_resp.raise_for_status()
                    parsed = parse_shareholding_xbrl(xml_resp.text)
                except Exception as e:
                    print(f"{symbol} {period_end_date}: FAILED to fetch/parse XBRL - {e}", file=sys.stderr, flush=True)
                    continue

                submission_raw = filing.get("submissionDate")
                submission_date = None
                if submission_raw:
                    try:
                        submission_date = datetime.strptime(submission_raw.split(" ")[0], "%d-%b-%Y").date()
                    except ValueError:
                        pass

                insert_raw(conn, symbol, period_end_date, parsed, submission_date, batch_id)
                have.add((symbol, period_end_date))
                new_for_symbol += 1
                run["rows"] += 1

            print(f"{symbol}: {len(filings)} filings on file, {new_for_symbol} new", flush=True)
            time.sleep(1.0)

    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
