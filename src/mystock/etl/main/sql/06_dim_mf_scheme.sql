INSERT INTO main.dim_mf_scheme (scheme_code, scheme_name, fund_house, scheme_type, scheme_category, isin_growth, is_active)
SELECT scheme_code, scheme_name, fund_house, scheme_type, scheme_category, isin_growth, is_active
FROM staging.mf_scheme_master
ON CONFLICT (scheme_code) DO UPDATE SET
    scheme_name = EXCLUDED.scheme_name,
    fund_house = EXCLUDED.fund_house,
    scheme_type = EXCLUDED.scheme_type,
    scheme_category = EXCLUDED.scheme_category,
    isin_growth = EXCLUDED.isin_growth,
    is_active = EXCLUDED.is_active;
