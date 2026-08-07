"""Private MCP server for the mystock warehouse.

Read-only tools only — connects as mcp_reader (SELECT-only grants at the DB level,
enforced independently of the keyword guard in run_sql below), scoped to
staging/main/metadata/portfolio (see sql/roles/mcp_reader.sql). portfolio was widened
into scope on 2026-08-06 — user's own explicit decision, single-user personal data, no
other users on this system. Write/administrative tools are out of scope for mystock (see
MYSTOCK_PRODUCT_SPEC.md — AI Agent Architecture was dropped from scope entirely; chat +
these read-only tools is the whole AI surface).

Run:
    python -m mystock.mcp.server
"""
import json
import logging
import os
import re

from mcp.server.mcpserver import MCPServer

from mystock.db import get_reader_conn

mcp = MCPServer(
    "mystock",
    instructions=(
        "Read-only access to a personal Indian stock market intelligence warehouse "
        "(Staging/Main layers plus Portfolio holdings/trades/value/health in Postgres — "
        "see MYSTOCK_PRODUCT_SPEC.md). Use "
        "list_tables/describe_table/get_metadata to explore structure, search_dictionary "
        "to find things by keyword, search_docs for semantic search over the product spec "
        "and schema metadata (better than search_dictionary for conceptual questions like "
        "'why is X null' rather than exact name matches), get_stock_history for a specific "
        "symbol's daily prices, show_data_quality for known data issues, and run_sql for "
        "anything else — SELECT/WITH only, enforced both here and at the database role "
        "level. Before writing a non-trivial SQL query, consider calling search_docs first "
        "to check for known gaps/caveats (e.g. NULL patterns, scope limitations) that would "
        "otherwise silently produce a misleading answer."
    ),
)

# Lazy-loaded on first search_docs() call — importing sentence_transformers at module
# level would slow down every server startup even for sessions that never search docs.
_embedding_model = None


def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        # Model is already cached locally after the first run
        # (mystock.etl.rag.build_doc_embeddings) — HF_HUB_OFFLINE skips the network
        # re-check that otherwise adds ~15s and a wall of HTTP log noise to every server
        # start.
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
        logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model

FORBIDDEN_SQL = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|GRANT|REVOKE|CREATE|COPY)\b",
    re.IGNORECASE,
)
MAX_ROWS = 500


def _query(sql, params=None):
    conn = get_reader_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
        return [dict(zip(cols, r)) for r in rows]
    finally:
        conn.close()


def _to_json(rows):
    return json.dumps(rows, default=str, indent=2)


@mcp.tool()
def list_tables(schema: str = "") -> str:
    """List tables in the warehouse, optionally filtered to one schema
    (staging/main/metadata/portfolio), with row counts and descriptions."""
    if schema:
        rows = _query(
            "SELECT schema_name, table_name, layer, row_count, description "
            "FROM metadata.tables WHERE schema_name = %s ORDER BY table_name",
            (schema,),
        )
    else:
        rows = _query(
            "SELECT schema_name, table_name, layer, row_count, description "
            "FROM metadata.tables ORDER BY schema_name, table_name"
        )
    return _to_json(rows)


@mcp.tool()
def describe_table(schema: str, table: str) -> str:
    """Describe a table's columns: name, type, nullability, and description if known."""
    rows = _query(
        "SELECT column_name, data_type, is_nullable, description "
        "FROM metadata.columns WHERE schema_name = %s AND table_name = %s "
        "ORDER BY ordinal_position",
        (schema, table),
    )
    if not rows:
        return f"No such table in metadata.columns: {schema}.{table}"
    return _to_json(rows)


@mcp.tool()
def get_metadata(schema: str = "", table: str = "") -> str:
    """Get lineage and data-quality context for a table: where it comes from
    (metadata.lineage) and its most recent data quality check results."""
    result = {}
    if table:
        result["lineage"] = _query(
            "SELECT target_schema, target_table, source_schema, source_table, "
            "transform_script, notes FROM metadata.lineage "
            "WHERE target_table = %s AND (%s = '' OR target_schema = %s)",
            (table, schema, schema),
        )
        result["recent_quality_checks"] = _query(
            "SELECT check_name, status, metric_value, checked_at FROM metadata.data_quality "
            "WHERE table_name LIKE %s ORDER BY checked_at DESC LIMIT 10",
            (f"%{table}%",),
        )
    else:
        result["tables"] = _query("SELECT schema_name, table_name, layer FROM metadata.tables ORDER BY 1, 2")
    return _to_json(result)


@mcp.tool()
def show_data_quality(check_name: str = "", limit: int = 20) -> str:
    """Show recent data quality check results, optionally filtered to one check name
    (e.g. 'invalid_prices', 'missing_dates_gap', 'null_percentage')."""
    limit = min(limit, MAX_ROWS)
    if check_name:
        rows = _query(
            "SELECT check_name, table_name, status, metric_value, details, checked_at "
            "FROM metadata.data_quality WHERE check_name = %s "
            "ORDER BY checked_at DESC LIMIT %s",
            (check_name, limit),
        )
    else:
        rows = _query(
            "SELECT DISTINCT ON (check_name) check_name, table_name, status, metric_value, checked_at "
            "FROM metadata.data_quality ORDER BY check_name, checked_at DESC"
        )
    return _to_json(rows)


@mcp.tool()
def search_dictionary(keyword: str) -> str:
    """Search table and column names/descriptions in the data dictionary for a keyword."""
    like = f"%{keyword}%"
    tables = _query(
        "SELECT schema_name, table_name, description FROM metadata.tables "
        "WHERE table_name ILIKE %s OR description ILIKE %s",
        (like, like),
    )
    columns = _query(
        "SELECT schema_name, table_name, column_name, description FROM metadata.columns "
        "WHERE column_name ILIKE %s OR description ILIKE %s LIMIT %s",
        (like, like, MAX_ROWS),
    )
    return _to_json({"tables": tables, "columns": columns})


@mcp.tool()
def search_docs(query: str, top_k: int = 5) -> str:
    """Semantic search over the product spec and schema metadata descriptions
    (metadata.doc_embeddings — local embeddings, sentence-transformers all-MiniLM-L6-v2).
    Use this for conceptual questions ('why is X null', 'what's the scope of Y') where
    search_dictionary's exact-name matching would miss the relevant explanation. Returns
    the top_k most similar chunks with a 0-1 cosine similarity score."""
    top_k = min(top_k, 20)
    model = _get_embedding_model()
    query_embedding = model.encode(query).tolist()
    rows = _query(
        """SELECT source_type, source_ref, chunk_text, 1 - (embedding <=> %s::vector) AS similarity
           FROM metadata.doc_embeddings
           ORDER BY embedding <=> %s::vector
           LIMIT %s""",
        (query_embedding, query_embedding, top_k),
    )
    for r in rows:
        r["similarity"] = round(r["similarity"], 3)
    return _to_json(rows)


@mcp.tool()
def get_stock_history(symbol: str, from_date: str = "", to_date: str = "") -> str:
    """Daily OHLC/volume/delivery history for one symbol from the Main layer.
    Dates are 'YYYY-MM-DD'; omit to get the full range on file."""
    # NULL, not '', for an omitted bound -- ''::date is a cast error in Postgres, so an
    # empty-string placeholder blows up as soon as it's actually cast (independent of
    # whatever the OR condition would otherwise short-circuit to).
    from_bound = from_date or None
    to_bound = to_date or None
    rows = _query(
        """SELECT dd.full_date AS trade_date, fdp.open, fdp.high, fdp.low, fdp.close,
                  fdp.ltp, fdp.vwap, fv.volume, fv.turnover, fv.num_trades,
                  fde.delivery_qty, fde.delivery_pct
           FROM main.fact_daily_prices fdp
           JOIN main.dim_security ds ON ds.security_key = fdp.security_key
           JOIN main.dim_date dd ON dd.date_key = fdp.date_key
           LEFT JOIN main.fact_volume fv ON fv.security_key = fdp.security_key AND fv.date_key = fdp.date_key
           LEFT JOIN main.fact_delivery fde ON fde.security_key = fdp.security_key AND fde.date_key = fdp.date_key
           WHERE ds.symbol = %s
             AND (%s::date IS NULL OR dd.full_date >= %s::date)
             AND (%s::date IS NULL OR dd.full_date <= %s::date)
           ORDER BY dd.full_date""",
        (symbol.upper(), from_bound, from_bound, to_bound, to_bound),
    )
    if not rows:
        return f"No data for symbol {symbol!r} in that range."
    return _to_json(rows)


@mcp.tool()
def run_sql(query: str, limit: int = 200) -> str:
    """Run a read-only SQL query (SELECT/WITH only) against the warehouse. Rejected if
    it contains any write/DDL keyword, and enforced independently by the DB role too
    (mcp_reader has SELECT-only grants). Results are capped at `limit` rows."""
    stripped = query.strip().rstrip(";")
    if not re.match(r"^\s*(SELECT|WITH)\b", stripped, re.IGNORECASE):
        return "Rejected: only SELECT/WITH queries are allowed."
    if FORBIDDEN_SQL.search(stripped):
        return "Rejected: query contains a write/DDL keyword."

    limit = min(int(limit), MAX_ROWS)
    conn = get_reader_conn()
    try:
        with conn.cursor() as cur:
            # limit is inlined, not passed as a %s param -- stripped is arbitrary user SQL
            # and may itself contain literal '%' (e.g. LIKE/ILIKE patterns), which would
            # collide with psycopg2's %-style parameter substitution if we mixed the two.
            cur.execute(f"SELECT * FROM ({stripped}) AS q LIMIT {limit}")
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
        return _to_json([dict(zip(cols, r)) for r in rows])
    except Exception as e:
        return f"Query error: {e}"
    finally:
        conn.close()


if __name__ == "__main__":
    mcp.run()
