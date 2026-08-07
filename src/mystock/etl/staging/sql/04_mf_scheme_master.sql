INSERT INTO staging.mf_scheme_master
    (scheme_code, scheme_name, fund_house, scheme_type, scheme_category, isin_growth, isin_div_reinv, is_active)
SELECT
    scheme_code,
    raw_payload->>'scheme_name',
    raw_payload->>'fund_house',
    raw_payload->>'scheme_type',
    raw_payload->>'scheme_category',
    raw_payload->>'isin_growth',
    raw_payload->>'isin_div_reinvestment',
    TRUE
FROM staging.amfi_mf_scheme_master
ON CONFLICT (scheme_code) DO UPDATE SET
    scheme_name = EXCLUDED.scheme_name,
    fund_house = EXCLUDED.fund_house,
    scheme_type = EXCLUDED.scheme_type,
    scheme_category = EXCLUDED.scheme_category,
    isin_growth = EXCLUDED.isin_growth,
    isin_div_reinv = EXCLUDED.isin_div_reinv,
    is_active = TRUE,
    loaded_at = now();
