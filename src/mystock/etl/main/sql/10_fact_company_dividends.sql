INSERT INTO main.fact_company_dividends (security_key, ex_date_key, dividend)
SELECT ds.security_key, dd.date_key, cd.dividend
FROM staging.company_dividends cd
JOIN main.dim_security ds ON ds.symbol = cd.symbol
JOIN main.dim_date dd ON dd.full_date = cd.ex_date
ON CONFLICT (security_key, ex_date_key) DO UPDATE SET dividend = EXCLUDED.dividend;
