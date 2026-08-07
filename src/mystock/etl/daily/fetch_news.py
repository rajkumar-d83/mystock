"""Fetches recent news headlines for every security currently held in any portfolio
(not the whole scored universe — this is a holdings-scoped feature), via Google News RSS.
Free, no API key, one query per holding.

RSS feeds return overlapping recent items on every run by design (it's a rolling
window, not a delta feed) — staging.news_raw dedupes on (security_key, link) via
ON CONFLICT DO NOTHING, so re-running daily is safe and cheap after the first backfill.

Usage:
    python -m mystock.etl.daily.fetch_news
    python -m mystock.etl.daily.fetch_news --sleep 1.0
"""
import argparse
import re
import sys
import time
import urllib.parse
import uuid
from datetime import timezone
from email.utils import parsedate_to_datetime

import feedparser
import psycopg2.extras

from mystock.db import get_conn, etl_run

RSS_URL = "https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"

# A lot of what Google News RSS returns for a stock query isn't news at all -- it's a
# live price-tracker widget page (scanx.trade, Value Research, upstox.com, HDFC Sky etc.
# all republish these with a near-identical title on every crawl: "X Share Price Today |
# Live NSE/BSE"). These carry no actual information and would just dilute the sentiment
# signal with noise. Genuine news that happens to use "share price today" phrasing
# (e.g. "...Stocks Plunge Over 9% in Early Trade") always names the actual move or event,
# so: drop only titles matching the generic widget pattern AND lacking any such signal.
GENERIC_WIDGET_RE = re.compile(r"share price.*(live|today|nse|bse|chart|rates)", re.IGNORECASE)
HAS_SIGNAL_RE = re.compile(
    r"%|\bcrash|\bsurge|\bplunge|\brise|\brises|\bfall|\bfalls|\bjump|\bslide|\bdemerger|\bdividend|"
    r"\bresult|\bacquisition|\bacquire|\bipo\b|\bbuyback|\bsplit|\bbonus|\bfraud|\bresign|\bban\b|"
    r"\bprobe|\braid|\border\b|\bcontract|\bdeal\b|\bstake\b|\brally|\bslump|\bdowngrade|\bupgrade|"
    r"target price|\bwhy\b", re.IGNORECASE)


def is_boilerplate(title):
    return bool(title and GENERIC_WIDGET_RE.search(title) and not HAS_SIGNAL_RE.search(title))


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


def build_query(symbol, company_name):
    name = company_name.strip() if company_name else symbol
    return f'"{name}" NSE share'


def parse_published(entry):
    raw = entry.get("published")
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def insert_news_item(conn, security_key, entry, batch_id):
    source_name = entry.get("source", {}).get("title") if entry.get("source") else None
    payload = {
        "title": entry.get("title"),
        "link": entry.get("link"),
        "summary": entry.get("summary"),
        "published": entry.get("published"),
        "source_name": source_name,
    }
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO staging.news_raw (security_key, link, raw_payload, published_at, batch_id)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (security_key, link) DO NOTHING
               RETURNING id""",
            (security_key, entry.get("link"), psycopg2.extras.Json(payload), parse_published(entry), batch_id),
        )
        return cur.fetchone() is not None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sleep", type=float, default=0.5, help="seconds between RSS requests")
    args = ap.parse_args()

    conn = get_conn()
    holdings = current_holdings(conn)
    print(f"{len(holdings)} current holdings to fetch news for", flush=True)

    batch_id = str(uuid.uuid4())
    with etl_run("fetch_news", {"holdings": len(holdings)}) as run:
        total_new = 0
        for security_key, symbol, company_name in holdings:
            query = urllib.parse.quote(build_query(symbol, company_name))
            url = RSS_URL.format(query=query)
            try:
                feed = feedparser.parse(url)
                real_entries = [e for e in feed.entries if not is_boilerplate(e.get("title"))]
                new_count = sum(
                    1 for entry in real_entries if insert_news_item(conn, security_key, entry, batch_id)
                )
                conn.commit()
                total_new += new_count
                skipped = len(feed.entries) - len(real_entries)
                print(f"{symbol}: {len(feed.entries)} items, {skipped} boilerplate skipped, {new_count} new", flush=True)
            except Exception as e:
                print(f"{symbol}: FAILED - {e}", file=sys.stderr, flush=True)
            time.sleep(args.sleep)
        run["rows"] = total_new

    conn.close()
    print(f"Done. {total_new} new news items inserted.")


if __name__ == "__main__":
    main()
