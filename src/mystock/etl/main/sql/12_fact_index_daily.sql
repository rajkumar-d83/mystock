INSERT INTO main.fact_index_daily (index_key, date_key, open_value, high_value, low_value, close_value, pe_ratio, pb_ratio, dividend_yield)
SELECT di.index_key, dd.date_key, sid.open_value, sid.high_value, sid.low_value, sid.close_value,
       sid.pe_ratio, sid.pb_ratio, sid.dividend_yield
FROM staging.index_daily sid
JOIN main.dim_index di ON di.index_name = sid.index_name
JOIN main.dim_date dd ON dd.full_date = sid.trade_date
ON CONFLICT (index_key, date_key) DO UPDATE SET
    open_value = EXCLUDED.open_value, high_value = EXCLUDED.high_value,
    low_value = EXCLUDED.low_value, close_value = EXCLUDED.close_value,
    pe_ratio = EXCLUDED.pe_ratio, pb_ratio = EXCLUDED.pb_ratio,
    dividend_yield = EXCLUDED.dividend_yield;
