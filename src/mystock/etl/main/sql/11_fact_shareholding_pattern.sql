INSERT INTO main.fact_shareholding_pattern
    (security_key, date_key, promoter_pct, public_pct, institutions_domestic_pct,
     institutions_foreign_pct, non_institutions_pct, mutual_funds_pct, insurance_pct,
     fpi_category_1_pct, fpi_category_2_pct)
SELECT
    ds.security_key, dd.date_key,
    sp.promoter_pct, sp.public_pct, sp.institutions_domestic_pct,
    sp.institutions_foreign_pct, sp.non_institutions_pct, sp.mutual_funds_pct,
    sp.insurance_pct, sp.fpi_category_1_pct, sp.fpi_category_2_pct
FROM staging.shareholding_pattern sp
JOIN main.dim_security ds ON ds.symbol = sp.symbol
JOIN main.dim_date dd ON dd.full_date = sp.period_end_date
ON CONFLICT (security_key, date_key) DO UPDATE SET
    promoter_pct = EXCLUDED.promoter_pct,
    public_pct = EXCLUDED.public_pct,
    institutions_domestic_pct = EXCLUDED.institutions_domestic_pct,
    institutions_foreign_pct = EXCLUDED.institutions_foreign_pct,
    non_institutions_pct = EXCLUDED.non_institutions_pct,
    mutual_funds_pct = EXCLUDED.mutual_funds_pct,
    insurance_pct = EXCLUDED.insurance_pct,
    fpi_category_1_pct = EXCLUDED.fpi_category_1_pct,
    fpi_category_2_pct = EXCLUDED.fpi_category_2_pct;
