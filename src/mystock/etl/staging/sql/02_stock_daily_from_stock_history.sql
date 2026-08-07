-- staging.nse_stock_history_raw (per-symbol stock_df, always EQ-filtered at ingestion,
-- re-validated here defensively) -> staging.stock_daily
INSERT INTO staging.stock_daily
    (symbol, trade_date, open, high, low, close, prev_close, ltp, vwap, volume, turnover,
     num_trades, delivery_qty, delivery_pct, source_system)
SELECT
    symbol,
    trade_date,
    NULLIF(raw_payload->>'OPEN', '')::numeric,
    NULLIF(raw_payload->>'HIGH', '')::numeric,
    NULLIF(raw_payload->>'LOW', '')::numeric,
    NULLIF(raw_payload->>'CLOSE', '')::numeric,
    NULLIF(raw_payload->>'PREV. CLOSE', '')::numeric,
    NULLIF(raw_payload->>'LTP', '')::numeric,
    NULLIF(raw_payload->>'VWAP', '')::numeric,
    NULLIF(raw_payload->>'VOLUME', '')::bigint,
    NULLIF(raw_payload->>'VALUE', '')::numeric,
    NULLIF(raw_payload->>'NO OF TRADES', '')::bigint,
    NULLIF(raw_payload->>'DELIVERY QTY', '')::bigint,
    NULLIF(raw_payload->>'DELIVERY %', '')::numeric,
    'stock_df'
FROM staging.nse_stock_history_raw
WHERE raw_payload->>'SERIES' = 'EQ'
ON CONFLICT (symbol, trade_date) DO UPDATE SET
    open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low, close = EXCLUDED.close,
    prev_close = EXCLUDED.prev_close, ltp = EXCLUDED.ltp, vwap = EXCLUDED.vwap,
    volume = EXCLUDED.volume, turnover = EXCLUDED.turnover, num_trades = EXCLUDED.num_trades,
    delivery_qty = EXCLUDED.delivery_qty, delivery_pct = EXCLUDED.delivery_pct,
    source_system = EXCLUDED.source_system, loaded_at = now();
