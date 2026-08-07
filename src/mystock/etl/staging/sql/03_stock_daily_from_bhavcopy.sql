-- staging.nse_bhavcopy_raw (whole-market daily file, two possible raw shapes:
-- BHAVDATA-FULL columns or the newer UDIFF columns) -> staging.stock_daily.
-- symbol/trade_date already extracted into columns at ingestion; only raw_payload
-- fields need reconciling here. UDIFF has no VWAP/delivery fields at all -- those
-- come through NULL for UDIFF rows.
INSERT INTO staging.stock_daily
    (symbol, trade_date, open, high, low, close, prev_close, ltp, vwap, volume, turnover,
     num_trades, delivery_qty, delivery_pct, source_system)
SELECT
    symbol,
    trade_date,
    COALESCE(NULLIF(raw_payload->>'OPEN_PRICE', '')::numeric, NULLIF(raw_payload->>'OpnPric', '')::numeric),
    COALESCE(NULLIF(raw_payload->>'HIGH_PRICE', '')::numeric, NULLIF(raw_payload->>'HghPric', '')::numeric),
    COALESCE(NULLIF(raw_payload->>'LOW_PRICE', '')::numeric, NULLIF(raw_payload->>'LwPric', '')::numeric),
    COALESCE(NULLIF(raw_payload->>'CLOSE_PRICE', '')::numeric, NULLIF(raw_payload->>'ClsPric', '')::numeric),
    COALESCE(NULLIF(raw_payload->>'PREV_CLOSE', '')::numeric, NULLIF(raw_payload->>'PrvsClsgPric', '')::numeric),
    COALESCE(NULLIF(raw_payload->>'LAST_PRICE', '')::numeric, NULLIF(raw_payload->>'LastPric', '')::numeric),
    NULLIF(raw_payload->>'AVG_PRICE', '')::numeric,  -- NULL for UDIFF, no direct equivalent
    COALESCE(NULLIF(raw_payload->>'TTL_TRD_QNTY', '')::bigint, NULLIF(raw_payload->>'TtlTradgVol', '')::bigint),
    COALESCE(NULLIF(raw_payload->>'TURNOVER_LACS', '')::numeric * 100000, NULLIF(raw_payload->>'TtlTrfVal', '')::numeric),
    COALESCE(NULLIF(raw_payload->>'NO_OF_TRADES', '')::bigint, NULLIF(raw_payload->>'TtlNbOfTxsExctd', '')::bigint),
    NULLIF(NULLIF(raw_payload->>'DELIV_QTY', ''), '-')::bigint,   -- NSE uses '-' as well as '' for "no delivery data"
    NULLIF(NULLIF(raw_payload->>'DELIV_PER', ''), '-')::numeric,
    CASE WHEN raw_payload ? 'TckrSymb' THEN 'bhavcopy_udiff' ELSE 'bhavcopy_full' END
FROM staging.nse_bhavcopy_raw
WHERE COALESCE(raw_payload->>'SERIES', raw_payload->>'SctySrs') = 'EQ'
ON CONFLICT (symbol, trade_date) DO UPDATE SET
    open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low, close = EXCLUDED.close,
    prev_close = EXCLUDED.prev_close, ltp = EXCLUDED.ltp, vwap = EXCLUDED.vwap,
    volume = EXCLUDED.volume, turnover = EXCLUDED.turnover, num_trades = EXCLUDED.num_trades,
    delivery_qty = EXCLUDED.delivery_qty, delivery_pct = EXCLUDED.delivery_pct,
    source_system = EXCLUDED.source_system, loaded_at = now();
