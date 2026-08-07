"""Shared Postgres connection helpers and ETL run logging."""
import os
import uuid
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", "config", ".env"))


def get_conn():
    """Full-access connection (PGUSER) for ETL/pipeline code."""
    return psycopg2.connect(
        host=os.environ["PGHOST"],
        port=os.environ["PGPORT"],
        dbname=os.environ["PGDATABASE"],
        user=os.environ["PGUSER"],
        password=os.environ.get("PGPASSWORD") or None,
    )


def get_reader_conn():
    """Read-only connection (mcp_reader role) — used only by src/mystock/mcp/.
    Never use this for anything that writes; use get_conn() instead."""
    return psycopg2.connect(
        host=os.environ["PGHOST"],
        port=os.environ["PGPORT"],
        dbname=os.environ["PGDATABASE"],
        user=os.environ["MCP_PGUSER"],
        password=os.environ["MCP_PGPASSWORD"],
    )


@contextmanager
def etl_run(job_name, params=None):
    """Wraps a job body, logging start/end/status/rows_processed to metadata.etl_runs.

    Usage:
        with etl_run("historical_stock_history", {"symbols": ["RELIANCE"]}) as run:
            ... do work ...
            run["rows"] += 10
    """
    conn = get_conn()
    run_id = str(uuid.uuid4())
    state = {"rows": 0}
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO metadata.etl_runs (run_id, job_name, params) VALUES (%s, %s, %s)",
            (run_id, job_name, psycopg2.extras.Json(params or {})),
        )
    conn.commit()
    try:
        yield state
    except Exception as e:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE metadata.etl_runs
                   SET ended_at = now(), status = 'failed', error = %s, rows_processed = %s
                   WHERE run_id = %s""",
                (str(e)[:2000], state["rows"], run_id),
            )
        conn.commit()
        conn.close()
        raise
    else:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE metadata.etl_runs
                   SET ended_at = now(), status = 'success', rows_processed = %s
                   WHERE run_id = %s""",
                (state["rows"], run_id),
            )
        conn.commit()
        conn.close()
