INSERT INTO main.dim_index (index_name)
SELECT DISTINCT index_name FROM staging.index_daily
ON CONFLICT (index_name) DO NOTHING;
