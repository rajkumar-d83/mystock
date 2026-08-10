INSERT INTO main.fact_company_financials
    (security_key, period_type, period_end_date_key,
     total_revenue, net_income, ebitda, ebit, interest_expense, cost_of_revenue,
     total_debt, stockholders_equity, invested_capital, current_liabilities, inventory,
     accounts_receivable, accounts_payable, cash_and_equivalents,
     free_cash_flow, operating_cash_flow,
     shares_outstanding, total_assets, net_share_issuance)
SELECT
    ds.security_key, cf.period_type, dd.date_key,
    cf.total_revenue, cf.net_income, cf.ebitda, cf.ebit, cf.interest_expense, cf.cost_of_revenue,
    cf.total_debt, cf.stockholders_equity, cf.invested_capital, cf.current_liabilities, cf.inventory,
    cf.accounts_receivable, cf.accounts_payable, cf.cash_and_equivalents,
    cf.free_cash_flow, cf.operating_cash_flow,
    cf.shares_outstanding, cf.total_assets, cf.net_share_issuance
FROM staging.company_financials cf
JOIN main.dim_security ds ON ds.symbol = cf.symbol
JOIN main.dim_date dd ON dd.full_date = cf.period_end_date
ON CONFLICT (security_key, period_type, period_end_date_key) DO UPDATE SET
    total_revenue = EXCLUDED.total_revenue, net_income = EXCLUDED.net_income,
    ebitda = EXCLUDED.ebitda, ebit = EXCLUDED.ebit, interest_expense = EXCLUDED.interest_expense,
    cost_of_revenue = EXCLUDED.cost_of_revenue, total_debt = EXCLUDED.total_debt,
    stockholders_equity = EXCLUDED.stockholders_equity, invested_capital = EXCLUDED.invested_capital,
    current_liabilities = EXCLUDED.current_liabilities, inventory = EXCLUDED.inventory,
    accounts_receivable = EXCLUDED.accounts_receivable, accounts_payable = EXCLUDED.accounts_payable,
    cash_and_equivalents = EXCLUDED.cash_and_equivalents,
    free_cash_flow = EXCLUDED.free_cash_flow, operating_cash_flow = EXCLUDED.operating_cash_flow,
    shares_outstanding = EXCLUDED.shares_outstanding, total_assets = EXCLUDED.total_assets,
    net_share_issuance = EXCLUDED.net_share_issuance;
