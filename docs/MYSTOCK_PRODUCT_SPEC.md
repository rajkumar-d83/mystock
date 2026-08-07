# MyStock — Product Spec

**Version:** 1.0 (2026-08-04)
**Status:** v1 scope is fully built and describes the system as it actually stands today,
not aspirationally — every feature, weight, and count in this document was verified against
the live database while writing it. See §17 for what's explicitly out of v1 scope and
queued for v2.

## 1. Vision

A personal stock market intelligence system: a single database that knows everything about
Indian equities and mutual funds relevant to one investor's decision-making — prices, company
fundamentals, a computed quality score per stock, real portfolio holdings and their
performance, brokerage/tax costs, and news sentiment — queryable in plain SQL or plain English,
with no dashboard to maintain and no manual spreadsheet to update. A daily digest answers
"does anything need my attention today" without checking multiple tables by hand.

**Primary use case:** find multibagger candidates (small/mid-cap stocks with strong quality +
growth + still-reasonable valuation), track what's actually been invested, and know the real
cost of buying/selling.

## 2. Design Principles

These are the rules that should decide any future design question, not just describe the
current system — when a new feature request doesn't obviously fit, check it against these
before building:

- **Store facts once.** Current holdings live in exactly one place (the latest
  `OPENING_BALANCE` row), never summed with transaction history that would double-count
  it; every score's inputs are normalized rows, not repeated across tables. If a value can
  be derived, derive it — don't store it twice and risk the copies disagreeing.
- **Every calculated score must be explainable.** The stock quality score, the news/price
  signal, the sector signal — none of them exist only as a final number. Each stores its
  inputs (individual weighted metrics, the z-score and its trailing window, the sentiment
  score behind a flag) so "why is this 61.5" always has a real answer, not a shrug.
- **Prefer free public data.** NSE bhavcopy, AMFI/mfapi.in, Yahoo Finance, Google News RSS —
  no paid data subscription anywhere in the pipeline. A paid source is a last resort, not a
  first reach, and needs a real justification when proposed.
- **Local-first AI whenever possible.** Embeddings (RAG) and sentiment scoring (FinBERT) run
  locally, specifically so scheduled/unattended jobs never carry a per-run cloud API cost.
  A cloud LLM call is fine for something a human triggers and reviews (like this chat); it's
  the wrong default for something that runs on its own every day.
- **SQL remains the source of truth.** Every feature — screener, alert, portfolio value — is
  ultimately a query over Main. The chat interface writes and runs SQL; it doesn't maintain
  separate application state that could drift from what the database actually says.
- **A human can reproduce every AI answer.** Any answer given through chat should trace back
  to a SQL query the user could run themselves and get the same result — no computation that
  only exists inside a model's reasoning and can't be checked.
- **Daily automation over real-time complexity.** One batch job, once a day, is enough for
  every decision this system supports. Real-time/streaming infrastructure is a cost with no
  matching benefit here (see Non-Goals) — this principle is *why* that non-goal exists, not
  just a restatement of it.

## 3. User Workflow

Almost none of this needs the user to do anything. There are two flows — one that runs
itself every day, and one occasional manual step:

**Every day, automatically (no action needed):**

```
Prices (bhavcopy) + index snapshots
              │
   MF NAV + company fundamentals ── same universe re-fetched daily, not cached
              │
      Staging → Main refresh ── clean, type, dedupe, then load the query-ready layer
              │
       Data quality checks ── 8 automated checks, logged pass/warn/fail
              │
          Quality Score ── recomputed for every scored stock
              │
       News + sentiment ── currently-held stocks only, scored locally
              │
   Stock signal + sector signal ── flag genuinely abnormal moves, corroborated or not
              │
    Portfolio value & health ── today's snapshot, using current holdings
              │
          Daily alert digest ── one row, plain-English summary, ready to query
```

**Then, whenever you want an answer:**

```
Ask Chat (or query directly) → SQL runs against Main → answer, traceable back to the query
```

**Occasionally, when it's actually needed (not part of the daily flow):**

```
New broker statement downloaded
              │
     Import holdings (CLI script, ISIN-matched)
              │
  Reflected in tomorrow's value/health/alert — no separate "sync" step required
```

Holdings import is deliberately *not* in the daily sequence — nothing infers a new trade,
so nothing runs until you actually have a new statement to bring in (see Design Principles,
"store facts once", and Data Freshness).

## 4. Non-Goals (deliberately excluded)

- **F&O (futures & options).** Adds a whole extra data domain (options chains, Greeks, expiry
  cycles) with no bearing on the long-term-investing use case this is built for.
- **Dashboards.** No Power BI/Superset maintenance burden. All output is a SQL query result or
  a chat answer — faster to get a number today than to keep a chart correct forever.
- **Real-time/live quotes.** End-of-day data is enough for the decisions this system supports
  (portfolio review, screening, sentiment trend) — no justification for the complexity of a
  streaming/live-tick pipeline.
- **Bond/NCD tracking.** Out of scope for now; flagged as a known gap when it shows up in
  imported broker holdings, not silently dropped.

## 5. Architecture

Two layers, named for what each actually does rather than generic medallion terminology:

```
NSE / AMFI / Yahoo Finance / Google News
              │
        Collection jobs (daily + on-demand)
              │
          ┌───────────┐
          │  STAGING  │   land it, clean it, type it, dedupe it
          └───────────┘
              │
          ┌───────────┐
          │   MAIN    │   the single query-ready layer — dimensions, facts, computed scores
          └───────────┘
              │
    ┌─────────┼─────────┐
    │         │          │
   SQL      Chat/RAG    MCP tools
 (direct)  (English →   (list_tables, describe_table, run_sql,
            SQL, local   search_docs, get_stock_history, ...)
            embeddings)
```

- **Staging**: everything lands here close to raw first, then gets cleaned/typed/validated in
  the same conceptual step — deduped, standardized across sources, schema drift caught early.
- **Main**: the single source of truth everything downstream reads from — dimension tables
  (security, date, sector, MF scheme), fact tables (daily prices, MF NAV, dividends,
  fundamentals), and computed features (stock quality score, portfolio value/health, news
  sentiment signal). Plus `portfolio`, for user-entered/imported data. No consumer — SQL,
  chat, or MCP — ever reads Staging directly.

## 6. Data Domains

| Domain | Coverage | Source |
|---|---|---|
| Equity prices/volume/delivery | All 2,415 NSE-listed equities, 10-year history | NSE bhavcopy (`jugaad-data`) |
| Company fundamentals + quality score | NIFTY Total Market, 750 symbols scored | Yahoo Finance (`yfinance`) |
| Mutual funds | 12 AMCs (10 major + Parag Parikh + one allowlisted Tata scheme), NAV history | AMFI (`mfapi.in`) |
| MF AMC costs | Expense ratio, exit load — manually maintained, held schemes only | Web research (no reliable free feed exists) |
| Index snapshots | Whole-market daily close | `niftyindices.com` |
| Broker costs | Brokerage/STT/exchange charges/GST/stamp duty, by segment | Broker's published pricing |
| Portfolio | Multi-user, multi-broker, real imported holdings + trades | Broker export files (Upstox etc.) |
| News + sentiment | Currently-held stocks only, daily | Google News RSS + local FinBERT |

## 7. Data Freshness

The question everything above eventually gets asked: how current is this, actually?

| Data | Frequency |
|---|---|
| Equity prices/volume/delivery | Daily |
| Index snapshots | Daily |
| MF NAV | Daily |
| Company fundamentals | Daily |
| Quality Score | Daily |
| News | Daily |
| Sentiment | Daily |
| News/price signal (per-stock) | Daily |
| Sector signal | Daily |
| Portfolio value & health | Daily |
| Daily alert digest | Daily |
| Holdings & transactions | On import (manual) |
| Broker fee schedule | Manual, on rate change |
| MF AMC cost (expense ratio/exit load) | Manual, periodic |

Two things "Daily" doesn't mean here:

- **Not weekly, not cached.** Fundamentals in particular are re-fetched every day, not
  backfilled once and left stale — several Quality Score inputs (PEG, P/E-vs-own-history,
  ownership trend) need a real time series of daily snapshots to mean anything, not a single
  point-in-time pull.
- **Only on a genuine "today" run.** Fundamentals, quality score, news, sentiment, and the
  two signal tables all refresh only when the daily job runs for the actual current date —
  reprocessing a past date (`--date 2026-07-10`, e.g. to backfill a gap) does *not* also
  re-pull today's news or fundamentals as a side effect, since sources like Google News RSS
  or a live fundamentals snapshot have no concept of "as of that past date" to begin with.
  Prices, NAV, and index snapshots don't have this restriction — those genuinely can be
  backfilled for any past date.
- **Holdings only change when you tell it to.** Nothing infers a new trade or holding — a
  broker export has to be imported for a portfolio to reflect it. This is deliberate (see
  Design Principles, "store facts once") — guessing at a holding from indirect signals would
  risk a wrong guess in a place where being wrong actually costs money.

## 8. Data Quality Rules

The question behind "how fresh is this" is really "how do I know today's update actually
worked" — every pipeline run and every load is tracked so that's always answerable without
re-deriving it from scratch.

**Every pipeline run** (`metadata.etl_runs`) records: `run_id`, `job_name`, `params` (the
run's own arguments, e.g. which date it processed), `started_at`, `ended_at`, `status`
(running/success/failed), `rows_processed`, and `error` (the actual exception text, on
failure — not just "it failed"). Querying "did today's job succeed" is one query against
this table, not a log file to grep.

**Every Staging/Main refresh** runs a fixed battery of checks (`metadata.data_quality`),
each logged pass/warn/fail with its own metric value and details:

| Check | Catches |
|---|---|
| `missing_dates_gap` | Unexpected gaps in the trading-day sequence |
| `cross_source_duplicate_dates` | The same date landing from two different source pulls |
| `invalid_prices` | Negative/zero/nonsensical OHLC values |
| `invalid_volume_delivery` | Volume or delivery quantity that can't be right (e.g. delivery > volume) |
| `missing_symbols` | A symbol that stopped reporting data unexpectedly |
| `schema_change_unknown_keys` | A source API adding/renaming a field Staging doesn't know about yet |
| `referential_integrity` | A fact row pointing at a dimension key that doesn't exist |
| `null_percentage` | What fraction of key columns are null, trending over time |

**Lineage** (`metadata.lineage`) records which source table feeds which target table via
which transform script — "where did this number actually come from" is a lookup, not
institutional memory.

**Known gap, worth naming rather than glossing over:** today `rows_processed` is one
aggregate number per run, not the finer-grained `rows_fetched` /
`rows_loaded` / `duplicates_removed` breakdown a more mature warehouse would track
separately (e.g. "fetched 750, 2 failed, 748 loaded, 0 duplicates" instead of just
"748"). The dedup logic exists per-pipeline (`ON CONFLICT DO NOTHING`, checked
individually in each import script) but isn't surfaced as its own tracked number yet —
a real improvement, not assumed done by this spec.

## 9. Quality Score

This is the core of the product — everything else (the multibagger screener, portfolio
health, the daily alert) is ultimately built on top of it. Computed daily per stock,
0-100, from 8 weighted categories:

| Category | Weight |
|---|---:|
| Business Quality & Moat | 20 |
| Growth & Consistency | 20 |
| Financial Strength | 15 |
| Cash Flow & Capital Allocation | 15 |
| Balance Sheet | 10 |
| Governance | 10 |
| Valuation | 5 |
| Market Behaviour | 5 |
| **Total** | **100** |

Each category is itself an average of several sub-metrics, each independently banded to a
0-100 score and stored as its own row (`main.fact_stock_quality_metric` — security × date ×
metric), not just rolled into the category number. `main.fact_stock_quality_score` is a
derived summary of that table for fast queries, not a separately-computed number — the two
can never disagree, because one is math on the other.

**Business Quality & Moat (20%)** — is the underlying business actually good, independent of
its current price:
- `sustained_margin_proxy` — the *worst* EBIT margin across all available years (a business
  that stays profitable in a bad year says more than one that's only good on average)
- `margin_stability` — standard deviation of EBIT margin across years (low = pricing power)
- `roce_stability` — minimum ROCE across years, penalized for volatility
- `brand_moat`, `industry_leadership` — genuinely qualitative, no data source computes these
  today; excluded from the average rather than guessed at (see "Handling missing data" below)

**Growth & Consistency (20%)** — is it actually growing, and is that growth real (not one
good year):
- `revenue_cagr`, `profit_cagr` — compound annual growth over the full financials history
  available (typically ~4 years)
- `earnings_consistency` — fraction of year-over-year periods with revenue growth, profit
  growth, *and* positive operating cash flow simultaneously (a company that "grows" only on
  paper, without cash to back it, fails this even with a good CAGR)

**Financial Strength (15%)** — is the business efficient with the capital it has:
- `roe` (return on equity), `roce` (return on capital employed)
- `operating_margin`, `net_profit_margin`
- `interest_coverage` — EBIT ÷ interest expense (can it comfortably service its debt)

**Cash Flow & Capital Allocation (15%)** — does profit turn into real cash, and what does
management do with it:
- `fcf_consistency` — fraction of years with positive free cash flow
- `fcf_cagr` — free cash flow growth
- `ocf_vs_net_profit` — operating cash flow ÷ net income (an earnings-quality check; profit
  without matching cash flow is a red flag)
- `accrual_ratio` — (net income − OCF) ÷ total assets, the same earnings-quality idea from a
  different angle
- `debt_trend` — CAGR of total debt (shrinking is rewarded)
- `share_dilution` — CAGR of shares outstanding (issuing more shares dilutes existing holders)
- `capital_allocation_composite` — a blend of the debt/dilution/FCF trends above, kept as its
  own explicit line even though it overlaps with its inputs, because "how does management
  allocate capital" is a distinct question worth answering directly
- `dividend_quality` — years with a dividend on file (a non-payer isn't penalized outright —
  see "Handling missing data")

**Balance Sheet (10%)** — is the company's financial position sound:
- `debt_to_equity`
- `cash_conversion_cycle` — inventory days + debtor days − creditor days (how long cash is
  tied up before it comes back)
- `working_capital_trend` — is the cash conversion cycle improving or deteriorating over time
  (a sudden deterioration often precedes financial stress, before it shows up anywhere else)

**Governance (10%)** — can management be trusted:
- `promoter_holding_proxy` — Yahoo Finance's "insider" holding %, used as an approximation of
  SEBI's promoter-holding disclosure (noted as a proxy, not the real number, since India's
  exact promoter-holding figure isn't available from the current data sources)
- `institutional_holding_proxy` — institutional ownership %
- `institutional_trend`, `promoter_pledge`, `governance_red_flags` — the mechanism exists for
  the first (needs repeated snapshots over time, not enough history yet) but the data isn't
  there yet; the latter two need filings/annual-report text no current source provides —
  all three excluded from the average rather than scored as if absent were bad

**Valuation (5%)** — deliberately the smallest weight: a great business at a fair price beats
a mediocre one that's merely cheap, so this discourages screening on cheapness alone:
- `pe_vs_sector` — trailing P/E relative to the sector average
- `price_to_book`
- `peg_ratio` — P/E ÷ profit CAGR, valuation adjusted for growth

**Market Behaviour (5%)** — how has the market actually treated this stock recently:
- `relative_strength_vs_nifty50_6m/1y/3y` — outperformance vs. the Nifty 50 over three windows
- `relative_strength_composite` — the same, vs. the stock's own sector index where one exists
- `volatility_annualized`, `max_drawdown_3y` — how rough the ride has been
- `delivery_trend_score` — rising delivery % *together with* rising price is read as a sign of
  real (institutional) accumulation, not just speculative volume

**Handling missing data.** A sub-metric with no usable data (no dividend history, no promoter
pledge disclosure, an early-listed stock without enough years of financials) is *excluded*
from its category's average, not scored as zero — missing information isn't evidence of a
problem, and scoring it as if it were would systematically punish newly-listed or
thinly-covered stocks for a data gap that says nothing about the business. Every score also
carries a `data_completeness_pct`, so "this is a 75, but only 60% complete" is always visible
alongside the number, not hidden behind it.

**Ranking.** Beyond the raw 0-100, every score also gets `overall_percentile` (rank across
the whole scored universe) and `sector_percentile` (rank within its own sector) — a 65 means
something different for a bank than for a small-cap industrial, and the percentile makes
that comparable.

## 10. Core Features (built)

- **Portfolio tracking** — real holdings imported from broker exports (ISIN-matched for
  reliability), daily value/cost-basis/P&L snapshot, and a holdings-weighted rollup of the
  quality score as a portfolio "health" number.
- **Multibagger screener** — a SQL screen over quality score + revenue/earnings CAGR +
  valuation + market-cap bucket, to surface small/mid-cap candidates with real growth at a
  reasonable price. Validated against the expanded universe: surfaced 2 candidates
  (SANOFICONR, DCBBANK) that were invisible at NIFTY 500 scope, confirming the case for
  going beyond it. Ad-hoc news-feed cross-checks (not scheduled) can confirm a qualitative
  "supplying to big industries" narrative behind a candidate's numbers.
- **News sentiment signal** — daily headlines for held stocks, scored locally, correlated
  against each stock's own historical volatility to flag genuinely abnormal moves (not just
  "price went down") and whether news corroborates the move. A boilerplate filter drops
  live price-tracker widget pages (which carry no information) before they reach sentiment
  scoring.
- **Sector-wide signal** — the same abnormal-move detection applied at the sector level
  (equal-weighted average return across a sector's held stocks, for sectors with 2+
  holdings), to catch group moves — e.g. a commodity shock — that no single stock's own
  news would explain.
- **Daily portfolio alert** — one row per portfolio per day combining value change +
  every flagged stock-level and sector-level signal into a plain-English summary
  (`portfolio.daily_alert`). Delivery is query-based, not a push notification, by design.
- **Cost modeling** — brokerage/STT/exchange charges (by broker/segment) and MF expense
  ratio/exit load, so "what does this actually cost me" is answerable, not estimated.

## 11. AI/ML Components — local-first

Every ML component runs locally, no per-query cloud cost, so scheduled daily jobs never incur
API charges:

- **RAG** — warehouse docs + schema metadata embedded locally (`sentence-transformers`,
  all-MiniLM-L6-v2), grounds natural-language-to-SQL with real schema context instead of the
  model guessing table/column names.
- **News sentiment** — FinBERT (`ProsusAI/finbert`), local inference, 1,255 headlines scored
  in seconds on CPU (after a boilerplate filter drops non-news price-widget pages).
- **English chat interface** — Claude Code itself, using the RAG store + MCP tools
  (`search_docs`, `describe_table`, `run_sql`) to answer questions and write ad-hoc SQL against
  Main. This *is* the reporting layer — no separate BI tool.

## 12. MCP Server

A read-only MCP server (`mcp_reader` role, no write access) exposes: `list_tables`,
`describe_table`, `get_metadata`, `show_data_quality`, `search_dictionary`, `search_docs`,
`get_stock_history`, `run_sql`. This is what makes "ask a question, get an answer" possible
from any MCP-compatible client, not just this chat session.

## 13. Example Questions

Since the system is chat-driven, its capability is best shown as questions rather than
tables. Every one of these turns into a real SQL query against Main — the chat interface
doesn't do anything a direct query couldn't (see Design Principles, "SQL remains the
source of truth").

- **"Show my worst quality stocks."** → holdings joined to the latest Quality Score,
  sorted ascending.
- **"Why did my portfolio fall yesterday?"** → `portfolio.daily_alert` for that date; if
  it needs more than the summary, drill into `main.fact_price_sentiment_signal` and
  `main.fact_sector_signal` for that date to see which holdings/sectors were flagged and why.
- **"Show PE < 25 and Quality > 80."** → `main.fact_company_fundamentals` joined to
  `main.fact_stock_quality_score` on the latest date for each, filtered on both. (Verified
  live: 5 results as of this writing, e.g. BAJAJHLDNG at PE 13.4 / score 82.9.)
- **"Which holdings have negative sentiment?"** → `staging.news_sentiment` filtered to
  currently-held stocks, `sentiment_label = 'negative'`, most recent first.
- **"Which sector is strongest?"** → two valid readings, both answerable: highest average
  Quality Score by sector (`main.dim_sector` joined through), or today's best-performing
  sector (`main.fact_sector_signal`, most positive `return_zscore`) — worth asking which
  is meant if it's ambiguous.
- **"Compare TCS and Infosys."** → both symbols' Quality Score components side by side
  (`main.fact_stock_quality_metric`, one row per metric per stock) — a real component-level
  comparison, not just the two overall numbers.
- **"Find companies with ROE > 20 for five years."** → `main.fact_company_financials`,
  annual, computing ROE per year and checking it held across every year on file.
  (Caveat worth surfacing when asked: most stocks only have ~5 years of annual financials
  from Yahoo Finance to begin with, so "for five years" is close to "for as long as we
  have data" for most of the universe, not a deep multi-decade history.)

## 14. Scalability

- **Universe size**: already scaled twice (NIFTY 50 → 500 → Total Market, 750 symbols
  scored today) without any architecture change — the fetch/score pipeline is
  symbol-list-driven, not hardcoded. Further expansion to the full 2,415-symbol NSE
  universe is possible but has a real, known cost: longer backfill (full run was ~1.5hr
  incremental for this jump; the full-universe jump was estimated at 15-18hr one-time), and
  weaker Yahoo Finance data quality for micro-caps/SME-platform stocks.
- **Users/portfolios**: schema is genuinely multi-user and multi-portfolio already (not just
  provisioned for it) — adding a second real person or broker account requires zero schema
  change.
- **Storage/compute**: single local PostgreSQL instance is sufficient at current volume
  (~4M+ price rows, sub-minute query times). If this ever needs to run somewhere other than
  one Mac (e.g. always-on server, multiple household members with independent portfolios),
  the natural next step is a small managed Postgres instance — no architecture change needed
  to get there, just a connection string change.

## 15. Risk Register

Grounded in what's actually happened, not hypotheticals — several of these are real
incidents from this project's own build history, not guesses at what might go wrong:

| Risk | Real incident? | Mitigation | Status |
|---|---|---|---|
| NSE bhavcopy fetch throttled/blocked | Yes — recurring, has a known signature (high wall-clock time, near-zero CPU, empty-message failures) | Pause and resume by hand when the pattern is spotted | **Partial** — no automated backoff/retry yet |
| Yahoo Finance changes format or blocks scripted access | Not yet | None | **Unmitigated** — single source for fundamentals, no fallback provider |
| Google News RSS changes format or blocks access | Not yet | None | **Unmitigated** — single source for news, no fallback feed |
| Broker export misread (wrong column meaning, duplicate account, bad symbol match) | Yes — three real cases in one session: a "Rate" column misread as cost basis instead of market price, the same account imported twice as two "portfolios," and 5 trades fuzzy-matched to the wrong ticker on a coincidental substring | ISIN matching preferred over fuzzy name matching wherever possible; uncertain trade matches held in a staging/review table, never auto-promoted; a reconciliation check (holdings vs. trade netting) before trusting new data; unique-constraint dedup added to every import script after the duplicate-import incident | **Built**, proven against real data |
| Missing fundamentals data | N/A — design decision | A missing sub-metric is excluded from its category average, never scored as zero | **Built** |
| MF universe gaps (an AMC not covered) | Yes — Tata, Parag Parikh, Invesco, and Motilal Oswal all surfaced as real gaps | Specific schemes allowlisted by code when an actual holding needs it, rather than broadening the whole AMC filter (which would've pulled in ~150 irrelevant closed-end Tata funds) | **Built** for schemes actually held; other AMCs remain a known, flagged gap, not a hidden one |
| `main.dim_date` extends years into the future (it's a pre-populated calendar dimension) | Yes — silently made the sector signal compute zero rows, because `max(full_date)` grabbed a future date instead of the latest *priced* date | Fixed at the one spot found (join against `fact_daily_prices` for the true latest date) | **Partial** — no lint/check yet to catch the same mistake recurring elsewhere |
| Single local Postgres, single Mac, no backup | N/A | None | **Unmitigated** — a real operational risk if this machine is lost |
| Silent data quality regression | Ongoing, by nature | 8 automated checks + per-run tracking (see Data Quality Rules) | **Built** |

The pattern worth noticing: every "Built" row exists *because* something real broke first
— this register is as much a record of what to watch for as a plan for what to build next.

## 16. What's Explicitly Not Built Yet

- Full NSE universe (beyond NIFTY Total Market).
- Any UI beyond SQL/chat (explicitly out of scope per §4, revisit only if that changes).

## 17. Version History & Roadmap

**v1.0 (2026-08-04)** — everything in §1-§16: prices/fundamentals/MF pipeline, Quality
Score (8 categories, 30+ sub-metrics), portfolio tracking with real imported holdings,
multibagger screener, news sentiment + stock/sector signals, daily alert digest, broker
and MF cost modeling, MCP server, local-first RAG + FinBERT. Everything described as
"built" in this document is built and was verified against the live database while
writing it — v1 is a snapshot of reality, not a plan.

**v2 (proposed, not started)** — a dedicated **Research Engine**: the shift from "track
what I own" to "research what I might buy." Assessed by real feasibility, not just
listed:

- *Cheap, high-value, buildable on data already collected* — likely v2 priority:
  **Watchlists** (track a candidate before owning it — trivial extension of the portfolio
  schema pattern), **Buy/Sell checklists** (maps directly to the detailed personal
  investment framework behind the Quality Score design), **Promoter holding trend** (the
  scoring code already has the mechanism, just needs the repeated snapshots that are now
  accumulating daily to reach critical mass), **Quarterly earnings surprise** (quarterly
  financials are already fetched, needs a QoQ/YoY comparison layer), **Corporate
  actions** (a real gap surfaced directly by the Tata Motors demerger this session).
- *Real effort, no free clean data source* — needs a real scraping project or a paid
  source, decide deliberately before starting: **MF ownership changes** (would mean
  scraping monthly factsheet PDFs per AMC, not a structured feed), **FII/DII ownership**
  (quarterly shareholding filings, not currently sourced), **annual report embeddings** (a
  genuine new subsystem — PDF sourcing, parsing, chunking, embedding — but the highest-value
  option for the "moat"/governance metrics currently marked not-computable).
- *Likely conflicts with a Design Principle* — flag before building, don't default into
  it: **earnings call transcripts** — reliable free Indian-market sources are scarce,
  meaning this one likely means paying for data, which "prefer free public data" says to
  treat as a last resort requiring real justification, not a default reach.

No v2 item is started. This section exists so the next session picks up the prioritization
already done, instead of re-deriving it.
