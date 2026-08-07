-- Note: yfinance's dividendYield field has been inconsistent across versions/symbols
-- about whether it's a fraction (0.0046) or already a percentage (0.46) -- stored as-is,
-- not renormalized, since guessing which convention a given row uses would risk being
-- wrong in the other direction. Cross-check against staging.company_dividends if precision
-- matters for a specific analysis.
INSERT INTO staging.company_fundamentals_snapshot
    (symbol, snapshot_date, trailing_pe, forward_pe, price_to_book, debt_to_equity,
     return_on_equity, return_on_assets, profit_margin, operating_margin, dividend_yield,
     payout_ratio, trailing_eps, forward_eps, book_value, market_cap, current_ratio, quick_ratio)
SELECT
    symbol, snapshot_date,
    NULLIF(raw_payload->>'trailingPE', '')::numeric,
    NULLIF(raw_payload->>'forwardPE', '')::numeric,
    NULLIF(raw_payload->>'priceToBook', '')::numeric,
    NULLIF(raw_payload->>'debtToEquity', '')::numeric,
    NULLIF(raw_payload->>'returnOnEquity', '')::numeric,
    NULLIF(raw_payload->>'returnOnAssets', '')::numeric,
    NULLIF(raw_payload->>'profitMargins', '')::numeric,
    NULLIF(raw_payload->>'operatingMargins', '')::numeric,
    NULLIF(raw_payload->>'dividendYield', '')::numeric,
    NULLIF(raw_payload->>'payoutRatio', '')::numeric,
    NULLIF(raw_payload->>'trailingEps', '')::numeric,
    NULLIF(raw_payload->>'forwardEps', '')::numeric,
    NULLIF(raw_payload->>'bookValue', '')::numeric,
    NULLIF(raw_payload->>'marketCap', '')::numeric,
    NULLIF(raw_payload->>'currentRatio', '')::numeric,
    NULLIF(raw_payload->>'quickRatio', '')::numeric
FROM staging.yf_company_snapshot_raw
ON CONFLICT (symbol, snapshot_date) DO UPDATE SET
    trailing_pe = EXCLUDED.trailing_pe, forward_pe = EXCLUDED.forward_pe,
    price_to_book = EXCLUDED.price_to_book, debt_to_equity = EXCLUDED.debt_to_equity,
    return_on_equity = EXCLUDED.return_on_equity, return_on_assets = EXCLUDED.return_on_assets,
    profit_margin = EXCLUDED.profit_margin, operating_margin = EXCLUDED.operating_margin,
    dividend_yield = EXCLUDED.dividend_yield, payout_ratio = EXCLUDED.payout_ratio,
    trailing_eps = EXCLUDED.trailing_eps, forward_eps = EXCLUDED.forward_eps,
    book_value = EXCLUDED.book_value, market_cap = EXCLUDED.market_cap,
    current_ratio = EXCLUDED.current_ratio, quick_ratio = EXCLUDED.quick_ratio,
    loaded_at = now();
