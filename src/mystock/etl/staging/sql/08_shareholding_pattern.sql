-- staging.nse_shareholding_raw (raw) -> staging.shareholding_pattern (clean)
INSERT INTO staging.shareholding_pattern
    (symbol, period_end_date, promoter_pct, public_pct, institutions_domestic_pct,
     institutions_foreign_pct, non_institutions_pct, mutual_funds_pct, insurance_pct,
     fpi_category_1_pct, fpi_category_2_pct)
SELECT
    symbol,
    period_end_date,
    NULLIF(raw_payload->>'promoter_pct', '')::numeric,
    NULLIF(raw_payload->>'public_pct', '')::numeric,
    NULLIF(raw_payload->>'institutions_domestic_pct', '')::numeric,
    NULLIF(raw_payload->>'institutions_foreign_pct', '')::numeric,
    NULLIF(raw_payload->>'non_institutions_pct', '')::numeric,
    NULLIF(raw_payload->>'mutual_funds_pct', '')::numeric,
    NULLIF(raw_payload->>'insurance_pct', '')::numeric,
    NULLIF(raw_payload->>'fpi_category_1_pct', '')::numeric,
    NULLIF(raw_payload->>'fpi_category_2_pct', '')::numeric
FROM staging.nse_shareholding_raw
ON CONFLICT (symbol, period_end_date) DO UPDATE SET
    promoter_pct = EXCLUDED.promoter_pct,
    public_pct = EXCLUDED.public_pct,
    institutions_domestic_pct = EXCLUDED.institutions_domestic_pct,
    institutions_foreign_pct = EXCLUDED.institutions_foreign_pct,
    non_institutions_pct = EXCLUDED.non_institutions_pct,
    mutual_funds_pct = EXCLUDED.mutual_funds_pct,
    insurance_pct = EXCLUDED.insurance_pct,
    fpi_category_1_pct = EXCLUDED.fpi_category_1_pct,
    fpi_category_2_pct = EXCLUDED.fpi_category_2_pct,
    loaded_at = now();
