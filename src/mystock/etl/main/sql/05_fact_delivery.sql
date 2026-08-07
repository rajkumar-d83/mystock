-- NULL delivery_qty/delivery_pct for UDIFF-sourced days is expected, not a load bug.
INSERT INTO main.fact_delivery (security_key, date_key, exchange_key, delivery_qty, delivery_pct)
SELECT ds.security_key, dd.date_key, ex.exchange_key,
       sd.delivery_qty, sd.delivery_pct
FROM staging.stock_daily sd
JOIN main.dim_security ds ON ds.symbol = sd.symbol
JOIN main.dim_date dd ON dd.full_date = sd.trade_date
JOIN main.dim_exchange ex ON ex.exchange_code = 'NSE'
ON CONFLICT (security_key, date_key) DO UPDATE SET
    delivery_qty = EXCLUDED.delivery_qty, delivery_pct = EXCLUDED.delivery_pct;
