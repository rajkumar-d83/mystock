-- Raw's unique key is (scheme_code, nav_date, source) -- the same scheme+date can
-- legitimately appear from both 'mfapi' (historical backfill) and 'amfi_navall' (daily
-- fetch), which is fine in the raw table but would collide twice on the clean table's
-- (scheme_code, nav_date) key within one INSERT ("ON CONFLICT DO UPDATE command cannot
-- affect row a second time" -- Postgres can't reconcile two candidate rows for the same
-- target key in a single statement). DISTINCT ON picks the most-recently-fetched row per
-- key first.
INSERT INTO staging.mf_nav_daily (scheme_code, nav_date, nav)
SELECT DISTINCT ON (scheme_code, nav_date)
    scheme_code, nav_date, NULLIF(raw_payload->>'nav', '')::numeric
FROM staging.amfi_mf_nav_history_raw
ORDER BY scheme_code, nav_date, fetched_at DESC
ON CONFLICT (scheme_code, nav_date) DO UPDATE SET
    nav = EXCLUDED.nav, loaded_at = now();
