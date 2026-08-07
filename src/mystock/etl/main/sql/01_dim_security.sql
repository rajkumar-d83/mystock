-- staging.equity_master + staging.sector_map -> main.dim_security (Type 1 SCD: overwrite)
INSERT INTO main.dim_security
    (symbol, company_name, isin, listing_date, face_value, market_lot, sector_key, is_active)
SELECT
    em.symbol, em.company_name, em.isin, em.listing_date, em.face_value, em.market_lot,
    ds.sector_key, em.is_active
FROM staging.equity_master em
LEFT JOIN staging.sector_map sm ON sm.symbol = em.symbol
LEFT JOIN main.dim_sector ds ON ds.industry = sm.industry
ON CONFLICT (symbol) DO UPDATE SET
    company_name = EXCLUDED.company_name,
    isin = EXCLUDED.isin,
    listing_date = EXCLUDED.listing_date,
    face_value = EXCLUDED.face_value,
    market_lot = EXCLUDED.market_lot,
    sector_key = EXCLUDED.sector_key,
    is_active = EXCLUDED.is_active,
    loaded_at = now();

-- Symbols present in fact source data but absent from the (currently-listed-only) equity
-- master — almost certainly delisted/renamed names. Insert a minimal placeholder row so
-- fact loads always have a security_key to join to; marked is_active = FALSE.
INSERT INTO main.dim_security (symbol, is_active)
SELECT DISTINCT sd.symbol, FALSE
FROM staging.stock_daily sd
LEFT JOIN main.dim_security ds ON ds.symbol = sd.symbol
WHERE ds.symbol IS NULL
ON CONFLICT (symbol) DO NOTHING;
