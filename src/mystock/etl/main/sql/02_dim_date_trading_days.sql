-- Keep dim_date.is_trading_day in sync with what actually has price data in staging, in both
-- directions: a date that turns out to be a mislabeled duplicate must stop counting as a trading day.
UPDATE main.dim_date dd
SET is_trading_day = EXISTS (SELECT 1 FROM staging.stock_daily sd WHERE sd.trade_date = dd.full_date)
WHERE dd.is_trading_day IS DISTINCT FROM EXISTS (SELECT 1 FROM staging.stock_daily sd WHERE sd.trade_date = dd.full_date);
