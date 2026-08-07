INSERT INTO main.fact_volume (security_key, date_key, exchange_key, volume, turnover, num_trades)
SELECT ds.security_key, dd.date_key, ex.exchange_key,
       sd.volume, sd.turnover, sd.num_trades
FROM staging.stock_daily sd
JOIN main.dim_security ds ON ds.symbol = sd.symbol
JOIN main.dim_date dd ON dd.full_date = sd.trade_date
JOIN main.dim_exchange ex ON ex.exchange_code = 'NSE'
ON CONFLICT (security_key, date_key) DO UPDATE SET
    volume = EXCLUDED.volume, turnover = EXCLUDED.turnover, num_trades = EXCLUDED.num_trades;
