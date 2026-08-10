INSERT INTO main.fact_company_fundamentals
    (security_key, date_key, trailing_pe, forward_pe, price_to_book, debt_to_equity,
     return_on_equity, return_on_assets, profit_margin, operating_margin, dividend_yield,
     payout_ratio, trailing_eps, forward_eps, book_value, market_cap, current_ratio, quick_ratio)
SELECT
    ds.security_key, dd.date_key,
    cfs.trailing_pe, cfs.forward_pe, cfs.price_to_book, cfs.debt_to_equity,
    cfs.return_on_equity, cfs.return_on_assets, cfs.profit_margin, cfs.operating_margin,
    cfs.dividend_yield, cfs.payout_ratio, cfs.trailing_eps, cfs.forward_eps,
    cfs.book_value, cfs.market_cap, cfs.current_ratio, cfs.quick_ratio
FROM staging.company_fundamentals_snapshot cfs
JOIN main.dim_security ds ON ds.symbol = cfs.symbol
JOIN main.dim_date dd ON dd.full_date = cfs.snapshot_date
ON CONFLICT (security_key, date_key) DO UPDATE SET
    trailing_pe = EXCLUDED.trailing_pe, forward_pe = EXCLUDED.forward_pe,
    price_to_book = EXCLUDED.price_to_book, debt_to_equity = EXCLUDED.debt_to_equity,
    return_on_equity = EXCLUDED.return_on_equity, return_on_assets = EXCLUDED.return_on_assets,
    profit_margin = EXCLUDED.profit_margin, operating_margin = EXCLUDED.operating_margin,
    dividend_yield = EXCLUDED.dividend_yield, payout_ratio = EXCLUDED.payout_ratio,
    trailing_eps = EXCLUDED.trailing_eps, forward_eps = EXCLUDED.forward_eps,
    book_value = EXCLUDED.book_value, market_cap = EXCLUDED.market_cap,
    current_ratio = EXCLUDED.current_ratio, quick_ratio = EXCLUDED.quick_ratio;
