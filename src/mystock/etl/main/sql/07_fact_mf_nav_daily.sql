INSERT INTO main.fact_mf_nav_daily (scheme_key, date_key, nav)
SELECT dms.scheme_key, dd.date_key, mnd.nav
FROM staging.mf_nav_daily mnd
JOIN main.dim_mf_scheme dms ON dms.scheme_code = mnd.scheme_code
JOIN main.dim_date dd ON dd.full_date = mnd.nav_date
ON CONFLICT (scheme_key, date_key) DO UPDATE SET nav = EXCLUDED.nav;
