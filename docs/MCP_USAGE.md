# MyStock MCP — usage

Private, read-only MCP server over the `mystock` Postgres warehouse (Staging/Main layers
plus Portfolio), plus a bare CLI client for talking to it without an LLM. Source:
`src/mystock/mcp/server.py` (the server) and `src/mystock/mcp/client.py` (the client).

## What it is / isn't

- **Read-only.** Connects to Postgres as `mcp_reader`, a role with `SELECT`-only grants on
  `staging`/`main`/`metadata`/`portfolio` (see `sql/roles/mcp_reader.sql`). `run_sql`
  additionally rejects any query containing `INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|
  GRANT|REVOKE|CREATE|COPY`, or that doesn't start with `SELECT`/`WITH` — enforced twice,
  once in the tool and once at the DB role level (verified directly: connecting as
  `mcp_reader` and issuing a raw `DELETE` fails with `permission denied for table
  transactions`, independent of the app-level guard), so a bug in one doesn't matter.
- **`portfolio` schema was widened into scope on 2026-08-06** (user's own explicit
  decision — single-user personal data, no other users on this system). Originally
  excluded; `sql/roles/mcp_reader.sql` and this doc both record why and when that changed.
- **No write/admin tools at all.** A multi-agent architecture (agents that could
  write/validate/transform data) was deliberately kept out of scope — see
  `MYSTOCK_PRODUCT_SPEC.md`. Chat (Claude Code) + these 8 read-only tools is the whole
  AI surface.
- **Fully offline-capable on the server side.** Every tool queries local Postgres
  (`localhost`) — no network needed. `search_docs` uses a local `sentence-transformers`
  model (`all-MiniLM-L6-v2`) that's cached after first run and forced offline via
  `HF_HUB_OFFLINE=1`, so it never phones home to check for updates. The one thing that is
  *not* offline is an LLM chatting with you about the results — Claude Code itself needs a
  network connection, same as any hosted-model session.

## The 8 tools

| Tool | Args | What it does |
|---|---|---|
| `list_tables` | `schema=""` | List tables (optionally filtered to one schema) with row counts and descriptions, from `metadata.tables`. |
| `describe_table` | `schema`, `table` | Columns: name, type, nullability, description, from `metadata.columns`. |
| `get_metadata` | `schema=""`, `table=""` | Lineage (`metadata.lineage`) + recent data-quality checks for a table; with no table, lists all tables/schemas/layers. |
| `show_data_quality` | `check_name=""`, `limit=20` | Recent `metadata.data_quality` check results, optionally filtered to one check name (e.g. `invalid_prices`, `missing_dates_gap`). |
| `search_dictionary` | `keyword` | Exact-ish keyword search over table/column names and descriptions. |
| `search_docs` | `query`, `top_k=5` | Semantic search (cosine similarity) over `metadata.doc_embeddings` — the product spec + schema metadata, embedded locally. Better than `search_dictionary` for conceptual questions ("why is X null") where the answer isn't in an exact name match. |
| `get_stock_history` | `symbol`, `from_date=""`, `to_date=""` | Daily OHLC/volume/delivery for one symbol from Main. Omit either date bound for an open range. |
| `run_sql` | `query`, `limit=200` | Any `SELECT`/`WITH` query against the warehouse, capped at `limit` rows (max 500). Everything else is rejected. |

`show_data_quality` and `run_sql` cap results at `MAX_ROWS = 500` regardless of the
requested limit.

## Using it through Claude Code

Not registered by default — the `claude` CLI needs to be on your PATH and run interactively
(it can't be done from inside a non-interactive Claude Code session). One-time setup:

```bash
claude mcp add mystock -- /Users/raj/projects/mystock/.venv/bin/python -m mystock.mcp.server
```

After that, Claude Code can call the 8 tools directly in any session in this project.

## Using it without Claude Code — the bare client

`src/mystock/mcp/client.py` is a thin CLI over the real MCP protocol — no LLM involved, just
a scripted client that spawns `mystock.mcp.server` as a subprocess over stdio (the same
transport any MCP host uses) and calls tools directly. Useful for offline/scripted queries
when you don't want (or can't reach) Claude Code.

**Note:** this is deliberately *not* paired with a local LLM to make it "chat"-like — that
would reintroduce the local-LLM-answers-questions architecture piece the product spec
explicitly dropped in favor of Claude Code being the only AI surface. It's a raw tool caller.

Three modes:

```bash
# Interactive REPL
python -m mystock.mcp.client
> tools
> list_tables schema=main
> search_docs query="why is delivery percent null" top_k=3
> quit

# List available tools, non-interactively
python -m mystock.mcp.client tools

# One-shot call: <tool> key=value key=value ...
python -m mystock.mcp.client run_sql query="SELECT count(*) FROM main.dim_security"
python -m mystock.mcp.client get_stock_history symbol=RELIANCE from_date=2026-08-01 to_date=2026-08-03
python -m mystock.mcp.client describe_table schema=main table=fact_daily_prices
```

Argument values are parsed as `int`, then `float`, then left as a string — so
`top_k=3` becomes an int automatically, no quoting needed. String values with spaces need
shell quoting as usual (`query="SELECT ..."`).

Output is whatever the tool returns — JSON for most tools, plain text for rejections
(`run_sql` on a write query prints `Rejected: only SELECT/WITH queries are allowed.`
instead of raising).

## Keeping `search_docs` current

`search_docs` reads from `metadata.doc_embeddings`, built by:

```bash
python -m mystock.etl.rag.build_doc_embeddings
```

This embeds `docs/*.md` (currently just `MYSTOCK_PRODUCT_SPEC.md`) plus every
`metadata.tables`/`metadata.columns` description. It's idempotent (clears and rebuilds each
source type every run), so re-run it whenever the product spec or a table/column
description changes — it's not on any automated schedule, since docs don't change often
enough to warrant one. If you add a new doc under `docs/`, it's picked up automatically on
the next run (no code change needed).

## Data freshness note

Everything queryable here reflects whatever `run_daily_job.py` last loaded. Company
fundamentals ratios (`main.fact_company_fundamentals`, surfaced via `get_stock_history`
joins or `run_sql`) refresh daily; full financial statements/dividends refresh weekly
(Sundays, `com.mystock.weeklyfundamentals` — see `docs/STATUS.md`). There's no "as of"
parameter on the MCP tools themselves; they always show the latest loaded state.
