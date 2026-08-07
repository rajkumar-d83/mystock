"""Shared lookups for portfolio import scripts: user/portfolio get-or-create, and
security/scheme resolution by ISIN or symbol against the existing Main dimensions."""
import re
from difflib import SequenceMatcher


def _normalize_scheme_name(name):
    name = re.sub(r"[^A-Z0-9 ]", " ", name.upper())
    return re.sub(r"\s+", " ", name).strip()


def get_or_create_user(conn, username, display_name=None):
    with conn.cursor() as cur:
        cur.execute("SELECT user_id FROM portfolio.users WHERE username = %s", (username,))
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute(
            "INSERT INTO portfolio.users (username, display_name) VALUES (%s, %s) RETURNING user_id",
            (username, display_name or username),
        )
        user_id = cur.fetchone()[0]
    conn.commit()
    return user_id


def get_or_create_portfolio(conn, user_id, portfolio_name, broker=None, description=None):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT portfolio_id FROM portfolio.portfolios WHERE user_id = %s AND portfolio_name = %s",
            (user_id, portfolio_name),
        )
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute(
            """INSERT INTO portfolio.portfolios (user_id, portfolio_name, broker, description)
               VALUES (%s, %s, %s, %s) RETURNING portfolio_id""",
            (user_id, portfolio_name, broker, description),
        )
        portfolio_id = cur.fetchone()[0]
    conn.commit()
    return portfolio_id


def match_security_by_isin(conn, isin):
    with conn.cursor() as cur:
        cur.execute("SELECT security_key, symbol FROM main.dim_security WHERE isin = %s", (isin,))
        return cur.fetchone()


def match_security_by_symbol(conn, symbol):
    with conn.cursor() as cur:
        cur.execute("SELECT security_key, symbol FROM main.dim_security WHERE symbol = %s", (symbol,))
        return cur.fetchone()


def match_mf_scheme_by_isin(conn, isin):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT scheme_key, scheme_name FROM main.dim_mf_scheme
               WHERE scheme_code IN (
                   SELECT scheme_code FROM staging.mf_scheme_master
                   WHERE isin_growth = %s OR isin_div_reinv = %s
               )""",
            (isin, isin),
        )
        return cur.fetchone()


def match_mf_scheme_by_name(conn, scheme_name, min_confidence=0.85):
    """Exact (case-insensitive) match first, then fuzzy match on a normalized
    (punctuation/whitespace-collapsed) name — broker statements often format the same
    AMFI scheme name with different dash/space spacing (e.g. 'Fund -Direct Plan-Growth'
    vs 'Fund - Direct Plan - Growth')."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT scheme_key, scheme_name FROM main.dim_mf_scheme WHERE lower(scheme_name) = lower(%s)",
            (scheme_name,),
        )
        row = cur.fetchone()
        if row:
            return row
        cur.execute("SELECT scheme_key, scheme_name FROM main.dim_mf_scheme")
        norm_target = _normalize_scheme_name(scheme_name)
        best = None
        best_score = 0.0
        for scheme_key, candidate_name in cur.fetchall():
            score = SequenceMatcher(None, norm_target, _normalize_scheme_name(candidate_name)).ratio()
            if score > best_score:
                best, best_score = (scheme_key, candidate_name), score
        return best if best_score >= min_confidence else None
