"""Shared lookups for portfolio import scripts: user/portfolio get-or-create, and
security resolution by ISIN or symbol against the existing Main dimensions."""


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
