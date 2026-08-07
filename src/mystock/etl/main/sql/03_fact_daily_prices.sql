INSERT INTO main.fact_daily_prices
    (security_key, date_key, exchange_key, open, high, low, close, prev_close, ltp, vwap)
SELECT ds.security_key, dd.date_key, ex.exchange_key,
       sd.open, sd.high, sd.low, sd.close, sd.prev_close, sd.ltp, sd.vwap
FROM staging.stock_daily sd
JOIN main.dim_security ds ON ds.symbol = sd.symbol
JOIN main.dim_date dd ON dd.full_date = sd.trade_date
JOIN main.dim_exchange ex ON ex.exchange_code = 'NSE'
ON CONFLICT (security_key, date_key) DO UPDATE SET
    open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low, close = EXCLUDED.close,
    prev_close = EXCLUDED.prev_close, ltp = EXCLUDED.ltp, vwap = EXCLUDED.vwap;
