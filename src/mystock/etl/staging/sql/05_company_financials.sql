-- One row per (symbol, period_type, period_end_date) -- NOT per statement_type. Pivots
-- income/balance/cashflow raw rows for the same period into one wide row, since
-- ratios like ROCE and Cash Conversion Cycle need fields from more than one statement
-- at once.
--
-- current_liabilities/inventory are NULL for banks (e.g. HDFCBANK) -- confirmed, expected.
INSERT INTO staging.company_financials
    (symbol, period_type, period_end_date,
     total_revenue, net_income, ebitda, ebit, interest_expense, cost_of_revenue,
     total_debt, stockholders_equity, invested_capital, current_liabilities, inventory,
     accounts_receivable, accounts_payable, cash_and_equivalents,
     free_cash_flow, operating_cash_flow,
     shares_outstanding, total_assets, net_share_issuance)
SELECT
    symbol, period_type, period_end_date,
    MAX(CASE WHEN statement_type = 'income' THEN NULLIF(raw_payload->>'Total Revenue', '')::numeric END),
    MAX(CASE WHEN statement_type = 'income' THEN NULLIF(raw_payload->>'Net Income', '')::numeric END),
    MAX(CASE WHEN statement_type = 'income' THEN NULLIF(raw_payload->>'EBITDA', '')::numeric END),
    MAX(CASE WHEN statement_type = 'income' THEN NULLIF(raw_payload->>'EBIT', '')::numeric END),
    MAX(CASE WHEN statement_type = 'income' THEN NULLIF(raw_payload->>'Interest Expense', '')::numeric END),
    MAX(CASE WHEN statement_type = 'income' THEN
        COALESCE(NULLIF(raw_payload->>'Cost Of Revenue', '')::numeric, NULLIF(raw_payload->>'Reconciled Cost Of Revenue', '')::numeric)
    END),
    MAX(CASE WHEN statement_type = 'balance' THEN NULLIF(raw_payload->>'Total Debt', '')::numeric END),
    MAX(CASE WHEN statement_type = 'balance' THEN
        COALESCE(NULLIF(raw_payload->>'Stockholders Equity', '')::numeric, NULLIF(raw_payload->>'Common Stock Equity', '')::numeric)
    END),
    MAX(CASE WHEN statement_type = 'balance' THEN NULLIF(raw_payload->>'Invested Capital', '')::numeric END),
    MAX(CASE WHEN statement_type = 'balance' THEN NULLIF(raw_payload->>'Current Liabilities', '')::numeric END),
    MAX(CASE WHEN statement_type = 'balance' THEN NULLIF(raw_payload->>'Inventory', '')::numeric END),
    MAX(CASE WHEN statement_type = 'balance' THEN NULLIF(raw_payload->>'Accounts Receivable', '')::numeric END),
    MAX(CASE WHEN statement_type = 'balance' THEN NULLIF(raw_payload->>'Accounts Payable', '')::numeric END),
    MAX(CASE WHEN statement_type = 'balance' THEN NULLIF(raw_payload->>'Cash And Cash Equivalents', '')::numeric END),
    MAX(CASE WHEN statement_type = 'cashflow' THEN NULLIF(raw_payload->>'Free Cash Flow', '')::numeric END),
    MAX(CASE WHEN statement_type = 'cashflow' THEN NULLIF(raw_payload->>'Operating Cash Flow', '')::numeric END),
    MAX(CASE WHEN statement_type = 'balance' THEN NULLIF(raw_payload->>'Ordinary Shares Number', '')::numeric END),
    MAX(CASE WHEN statement_type = 'balance' THEN NULLIF(raw_payload->>'Total Assets', '')::numeric END),
    MAX(CASE WHEN statement_type = 'cashflow' THEN NULLIF(raw_payload->>'Net Common Stock Issuance', '')::numeric END)
FROM staging.yf_financials_raw
GROUP BY symbol, period_type, period_end_date
ON CONFLICT (symbol, period_type, period_end_date) DO UPDATE SET
    total_revenue = EXCLUDED.total_revenue, net_income = EXCLUDED.net_income,
    ebitda = EXCLUDED.ebitda, ebit = EXCLUDED.ebit, interest_expense = EXCLUDED.interest_expense,
    cost_of_revenue = EXCLUDED.cost_of_revenue, total_debt = EXCLUDED.total_debt,
    stockholders_equity = EXCLUDED.stockholders_equity, invested_capital = EXCLUDED.invested_capital,
    current_liabilities = EXCLUDED.current_liabilities, inventory = EXCLUDED.inventory,
    accounts_receivable = EXCLUDED.accounts_receivable, accounts_payable = EXCLUDED.accounts_payable,
    cash_and_equivalents = EXCLUDED.cash_and_equivalents,
    free_cash_flow = EXCLUDED.free_cash_flow, operating_cash_flow = EXCLUDED.operating_cash_flow,
    shares_outstanding = EXCLUDED.shares_outstanding, total_assets = EXCLUDED.total_assets,
    net_share_issuance = EXCLUDED.net_share_issuance,
    loaded_at = now();
