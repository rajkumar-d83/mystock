# MyStock — Status

Last updated: 2026-08-08

## What's built

**Data pipeline** — Staging (raw, schema-on-read JSONB) → Main (star schema: dimensions +
facts) for NSE equity prices/volume/delivery (10-year history, 3,241 symbols), company
fundamentals (750 symbols, NIFTY Total Market), index snapshots, and news. Equities/ETFs
only — mutual funds are deliberately out of scope, see below. 8 automated data-quality
checks logged on every run (`metadata.data_quality`), plus full run tracking
(`metadata.etl_runs`).

**Quality Score** — 8-category weighted score (0–100) per stock: Business Quality,
Growth, Financial Strength, Cash Flow/Capital Allocation, Balance Sheet, Governance,
Valuation, Market Behaviour. ~30 sub-metrics roll up into each category; every sub-metric
stays independently queryable (`main.fact_stock_quality_metric`), not just the final
number. Recomputed daily for all 750 scored symbols.

**Portfolio tracking** — Real holdings imported from broker exports (ISIN-matched
preferred over fuzzy name matching), daily value/cost-basis/P&L snapshot, and a
holdings-weighted "health" rollup of the quality score. Uncertain trade matches are held
in a review table, never auto-promoted.

**News sentiment + signals** — Daily headlines for currently-held stocks (Google News
RSS), scored locally with FinBERT. Price/sentiment signal flags abnormal moves (z-score
vs. trailing 20-day history) and checks whether news corroborates them. Sector-level
signal does the same at the sector average. Daily alert digest combines everything into
one plain-English row per portfolio per day.

**MCP server + client** — 8 read-only tools (`list_tables`, `describe_table`,
`get_metadata`, `show_data_quality`, `search_dictionary`, `search_docs`,
`get_stock_history`, `run_sql`) over Staging/Main/Portfolio/Metadata, enforced read-only
at both the application and database-role level. A standalone CLI client
(`src/mystock/mcp/client.py`) works without any LLM, fully offline. See
`docs/MCP_USAGE.md` for the full reference.

**RAG** — Product spec + schema metadata embedded locally (`sentence-transformers`,
all-MiniLM-L6-v2) for semantic search via `search_docs` — no cloud embedding API.

**Automation** — Three scheduled jobs (macOS `launchd`):
- **6:00 AM** — morning news fetch + sentiment scoring, ready before market open
- **19:07** — full daily pipeline (prices, fundamentals snapshot, quality scores, news,
  signals, portfolio value/health, daily alert)
- **Sundays 8:00 AM** — full fundamentals refresh (financial statements, dividends —
  quarterly-static, doesn't need a daily pull)

## Known gaps

- **No corporate-actions tracking.** A stock split or demerger reads as a false-positive
  "unusual price drop" in the signal engine and can distort cost-basis-derived returns,
  since there's no adjustment logic yet. Real, observed cases: TEMBO's stock split, and
  Vedanta's 5-way demerger (VEDL/VAML/VEDPOWER/VISL/VOGL all inherited broker-assigned
  cost bases at the same nominal date, which don't reflect a fair value split).
- **Broker import scripts** (`import_holdings_isin`, `import_holdings_symbol`,
  `import_trades_fuzzy`) haven't been exercised against a live broker export recently —
  will get real use the next time a statement is downloaded.
- **Universe capped at NIFTY Total Market** (750 symbols) rather than the full ~2,415
  NSE-listed universe — expansion is possible (no architecture change needed) but has a
  real time cost (~15–18hr one-time backfill) and weaker data quality for micro-caps.
- Single local Postgres instance, single machine, no automated backup — a real
  operational risk if this machine is lost.

## Not built (out of scope for now)

- **Mutual fund tracking** — removed on 2026-08-08 (was built and working: AMFI NAV
  pipeline, MF holdings, MF cost modeling). Deliberate scope cut, not a regression — a
  fund manager already does the active-management job for MFs, so mystock's
  quality-scoring/signal machinery doesn't add much there. Will live in a separate,
  purpose-built app if/when needed. See `MYSTOCK_PRODUCT_SPEC.md` §4.
- Any UI beyond SQL/chat (dashboards are an explicit non-goal — see
  `MYSTOCK_PRODUCT_SPEC.md` §4).
- F&O (futures & options) tracking.
- Real-time/live quotes — end-of-day data only.
- A dedicated "research what to buy" engine (watchlists, buy/sell checklists, earnings
  surprise detection) — proposed as v2, not started. See `MYSTOCK_PRODUCT_SPEC.md` §17
  for the full prioritized list.

See `docs/MYSTOCK_PRODUCT_SPEC.md` for the full design rationale and
`docs/TECH_OVERVIEW.md` for a plain-English architecture walkthrough.
