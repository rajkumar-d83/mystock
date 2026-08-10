INSERT INTO staging.company_dividends (symbol, ex_date, dividend)
SELECT symbol, ex_date, dividend
FROM staging.yf_dividends_raw
ON CONFLICT (symbol, ex_date) DO UPDATE SET
    dividend = EXCLUDED.dividend, loaded_at = now();
