-- Mark trading days in dim_date based on what actually has data in staging.
UPDATE main.dim_date dd
SET is_trading_day = TRUE
WHERE dd.is_trading_day = FALSE
  AND EXISTS (SELECT 1 FROM staging.stock_daily sd WHERE sd.trade_date = dd.full_date);
