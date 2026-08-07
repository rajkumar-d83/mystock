-- staging.nse_equity_master (raw) -> staging.equity_master (clean)
INSERT INTO staging.equity_master
    (symbol, company_name, series, listing_date, isin, face_value, market_lot, paid_up_value, is_active)
SELECT
    symbol,
    raw_payload->>'NAME OF COMPANY',
    raw_payload->>'SERIES',
    to_date(NULLIF(raw_payload->>'DATE OF LISTING', ''), 'DD-Mon-YYYY'),
    raw_payload->>'ISIN NUMBER',
    NULLIF(raw_payload->>'FACE VALUE', '')::numeric,
    NULLIF(raw_payload->>'MARKET LOT', '')::int,
    NULLIF(raw_payload->>'PAID UP VALUE', '')::numeric,
    TRUE
FROM staging.nse_equity_master
ON CONFLICT (symbol) DO UPDATE SET
    company_name = EXCLUDED.company_name,
    series = EXCLUDED.series,
    listing_date = EXCLUDED.listing_date,
    isin = EXCLUDED.isin,
    face_value = EXCLUDED.face_value,
    market_lot = EXCLUDED.market_lot,
    paid_up_value = EXCLUDED.paid_up_value,
    is_active = TRUE,
    loaded_at = now();
