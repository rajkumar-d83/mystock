INSERT INTO staging.index_daily (index_name, trade_date, open_value, high_value, low_value, close_value, pe_ratio, pb_ratio, dividend_yield)
SELECT
    index_name, trade_date,
    NULLIF(NULLIF(raw_payload->>'Open Index Value', ''), '-')::numeric,
    NULLIF(NULLIF(raw_payload->>'High Index Value', ''), '-')::numeric,
    NULLIF(NULLIF(raw_payload->>'Low Index Value', ''), '-')::numeric,
    NULLIF(NULLIF(raw_payload->>'Closing Index Value', ''), '-')::numeric,
    NULLIF(NULLIF(raw_payload->>'P/E', ''), '-')::numeric,
    NULLIF(NULLIF(raw_payload->>'P/B', ''), '-')::numeric,
    NULLIF(NULLIF(raw_payload->>'Div Yield', ''), '-')::numeric
FROM staging.nse_indices_bhavcopy_raw
ON CONFLICT (index_name, trade_date) DO UPDATE SET
    open_value = EXCLUDED.open_value, high_value = EXCLUDED.high_value,
    low_value = EXCLUDED.low_value, close_value = EXCLUDED.close_value,
    pe_ratio = EXCLUDED.pe_ratio, pb_ratio = EXCLUDED.pb_ratio,
    dividend_yield = EXCLUDED.dividend_yield, loaded_at = now();
