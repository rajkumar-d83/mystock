--
-- PostgreSQL database dump
--

\restrict T5cODfGpL8BxdQ9vzu85sAQigXEN3ofmW0z2uOfpsetXMDIt9KaTgC1JzgggDht

-- Dumped from database version 18.4 (Homebrew)
-- Dumped by pg_dump version 18.4 (Homebrew)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: main; Type: SCHEMA; Schema: -; Owner: raj
--

CREATE SCHEMA main;


ALTER SCHEMA main OWNER TO raj;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: dim_date; Type: TABLE; Schema: main; Owner: raj
--

CREATE TABLE main.dim_date (
    date_key integer NOT NULL,
    full_date date NOT NULL,
    year integer NOT NULL,
    quarter integer NOT NULL,
    month integer NOT NULL,
    month_name text NOT NULL,
    day integer NOT NULL,
    day_of_week integer NOT NULL,
    day_name text NOT NULL,
    is_weekend boolean NOT NULL,
    financial_year text NOT NULL,
    is_trading_day boolean DEFAULT false NOT NULL
);


ALTER TABLE main.dim_date OWNER TO raj;

--
-- Name: dim_exchange; Type: TABLE; Schema: main; Owner: raj
--

CREATE TABLE main.dim_exchange (
    exchange_key integer NOT NULL,
    exchange_code text NOT NULL,
    exchange_name text NOT NULL
);


ALTER TABLE main.dim_exchange OWNER TO raj;

--
-- Name: dim_exchange_exchange_key_seq; Type: SEQUENCE; Schema: main; Owner: raj
--

CREATE SEQUENCE main.dim_exchange_exchange_key_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE main.dim_exchange_exchange_key_seq OWNER TO raj;

--
-- Name: dim_exchange_exchange_key_seq; Type: SEQUENCE OWNED BY; Schema: main; Owner: raj
--

ALTER SEQUENCE main.dim_exchange_exchange_key_seq OWNED BY main.dim_exchange.exchange_key;


--
-- Name: dim_index; Type: TABLE; Schema: main; Owner: raj
--

CREATE TABLE main.dim_index (
    index_key integer NOT NULL,
    index_name text NOT NULL
);


ALTER TABLE main.dim_index OWNER TO raj;

--
-- Name: dim_index_index_key_seq; Type: SEQUENCE; Schema: main; Owner: raj
--

CREATE SEQUENCE main.dim_index_index_key_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE main.dim_index_index_key_seq OWNER TO raj;

--
-- Name: dim_index_index_key_seq; Type: SEQUENCE OWNED BY; Schema: main; Owner: raj
--

ALTER SEQUENCE main.dim_index_index_key_seq OWNED BY main.dim_index.index_key;


--
-- Name: dim_mf_scheme; Type: TABLE; Schema: main; Owner: raj
--

CREATE TABLE main.dim_mf_scheme (
    scheme_key integer NOT NULL,
    scheme_code bigint NOT NULL,
    scheme_name text,
    fund_house text,
    scheme_type text,
    scheme_category text,
    isin_growth text,
    is_active boolean DEFAULT true NOT NULL
);


ALTER TABLE main.dim_mf_scheme OWNER TO raj;

--
-- Name: dim_mf_scheme_scheme_key_seq; Type: SEQUENCE; Schema: main; Owner: raj
--

CREATE SEQUENCE main.dim_mf_scheme_scheme_key_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE main.dim_mf_scheme_scheme_key_seq OWNER TO raj;

--
-- Name: dim_mf_scheme_scheme_key_seq; Type: SEQUENCE OWNED BY; Schema: main; Owner: raj
--

ALTER SEQUENCE main.dim_mf_scheme_scheme_key_seq OWNED BY main.dim_mf_scheme.scheme_key;


--
-- Name: dim_option_contract; Type: TABLE; Schema: main; Owner: raj
--

CREATE TABLE main.dim_option_contract (
    contract_key integer NOT NULL,
    underlying_symbol text NOT NULL,
    expiry_date date NOT NULL,
    strike_price numeric(12,2) NOT NULL,
    option_type text NOT NULL
);


ALTER TABLE main.dim_option_contract OWNER TO raj;

--
-- Name: dim_option_contract_contract_key_seq; Type: SEQUENCE; Schema: main; Owner: raj
--

CREATE SEQUENCE main.dim_option_contract_contract_key_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE main.dim_option_contract_contract_key_seq OWNER TO raj;

--
-- Name: dim_option_contract_contract_key_seq; Type: SEQUENCE OWNED BY; Schema: main; Owner: raj
--

ALTER SEQUENCE main.dim_option_contract_contract_key_seq OWNED BY main.dim_option_contract.contract_key;


--
-- Name: dim_sector; Type: TABLE; Schema: main; Owner: raj
--

CREATE TABLE main.dim_sector (
    sector_key integer NOT NULL,
    industry text NOT NULL
);


ALTER TABLE main.dim_sector OWNER TO raj;

--
-- Name: dim_sector_sector_key_seq; Type: SEQUENCE; Schema: main; Owner: raj
--

CREATE SEQUENCE main.dim_sector_sector_key_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE main.dim_sector_sector_key_seq OWNER TO raj;

--
-- Name: dim_sector_sector_key_seq; Type: SEQUENCE OWNED BY; Schema: main; Owner: raj
--

ALTER SEQUENCE main.dim_sector_sector_key_seq OWNED BY main.dim_sector.sector_key;


--
-- Name: dim_security; Type: TABLE; Schema: main; Owner: raj
--

CREATE TABLE main.dim_security (
    security_key integer NOT NULL,
    symbol text NOT NULL,
    company_name text,
    isin text,
    listing_date date,
    face_value numeric(12,2),
    market_lot integer,
    sector_key integer,
    is_active boolean DEFAULT true NOT NULL,
    loaded_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE main.dim_security OWNER TO raj;

--
-- Name: dim_security_security_key_seq; Type: SEQUENCE; Schema: main; Owner: raj
--

CREATE SEQUENCE main.dim_security_security_key_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE main.dim_security_security_key_seq OWNER TO raj;

--
-- Name: dim_security_security_key_seq; Type: SEQUENCE OWNED BY; Schema: main; Owner: raj
--

ALTER SEQUENCE main.dim_security_security_key_seq OWNED BY main.dim_security.security_key;


--
-- Name: fact_company_dividends; Type: TABLE; Schema: main; Owner: raj
--

CREATE TABLE main.fact_company_dividends (
    security_key integer NOT NULL,
    ex_date_key integer NOT NULL,
    dividend numeric(14,4)
);


ALTER TABLE main.fact_company_dividends OWNER TO raj;

--
-- Name: fact_company_financials; Type: TABLE; Schema: main; Owner: raj
--

CREATE TABLE main.fact_company_financials (
    security_key integer NOT NULL,
    period_type text NOT NULL,
    period_end_date_key integer NOT NULL,
    total_revenue numeric(20,2),
    net_income numeric(20,2),
    ebitda numeric(20,2),
    ebit numeric(20,2),
    interest_expense numeric(20,2),
    cost_of_revenue numeric(20,2),
    total_debt numeric(20,2),
    stockholders_equity numeric(20,2),
    invested_capital numeric(20,2),
    current_liabilities numeric(20,2),
    inventory numeric(20,2),
    accounts_receivable numeric(20,2),
    accounts_payable numeric(20,2),
    cash_and_equivalents numeric(20,2),
    free_cash_flow numeric(20,2),
    operating_cash_flow numeric(20,2),
    shares_outstanding numeric(20,2),
    total_assets numeric(20,2),
    net_share_issuance numeric(20,2)
);


ALTER TABLE main.fact_company_financials OWNER TO raj;

--
-- Name: fact_company_fundamentals; Type: TABLE; Schema: main; Owner: raj
--

CREATE TABLE main.fact_company_fundamentals (
    security_key integer NOT NULL,
    date_key integer NOT NULL,
    trailing_pe numeric(12,4),
    forward_pe numeric(12,4),
    price_to_book numeric(12,4),
    debt_to_equity numeric(12,4),
    return_on_equity numeric(8,4),
    return_on_assets numeric(8,4),
    profit_margin numeric(8,4),
    operating_margin numeric(8,4),
    dividend_yield numeric(8,4),
    payout_ratio numeric(8,4),
    trailing_eps numeric(14,4),
    forward_eps numeric(14,4),
    book_value numeric(14,4),
    market_cap numeric(20,2),
    current_ratio numeric(8,4),
    quick_ratio numeric(8,4)
);


ALTER TABLE main.fact_company_fundamentals OWNER TO raj;

--
-- Name: fact_daily_prices; Type: TABLE; Schema: main; Owner: raj
--

CREATE TABLE main.fact_daily_prices (
    security_key integer NOT NULL,
    date_key integer NOT NULL,
    exchange_key integer NOT NULL,
    open numeric(14,2),
    high numeric(14,2),
    low numeric(14,2),
    close numeric(14,2),
    prev_close numeric(14,2),
    ltp numeric(14,2),
    vwap numeric(14,2)
);


ALTER TABLE main.fact_daily_prices OWNER TO raj;

--
-- Name: fact_delivery; Type: TABLE; Schema: main; Owner: raj
--

CREATE TABLE main.fact_delivery (
    security_key integer NOT NULL,
    date_key integer NOT NULL,
    exchange_key integer NOT NULL,
    delivery_qty bigint,
    delivery_pct numeric(6,2)
);


ALTER TABLE main.fact_delivery OWNER TO raj;

--
-- Name: fact_index_daily; Type: TABLE; Schema: main; Owner: raj
--

CREATE TABLE main.fact_index_daily (
    index_key integer NOT NULL,
    date_key integer NOT NULL,
    open_value numeric(14,2),
    high_value numeric(14,2),
    low_value numeric(14,2),
    close_value numeric(14,2),
    pe_ratio numeric(12,4),
    pb_ratio numeric(12,4),
    dividend_yield numeric(8,4)
);


ALTER TABLE main.fact_index_daily OWNER TO raj;

--
-- Name: fact_mf_nav_daily; Type: TABLE; Schema: main; Owner: raj
--

CREATE TABLE main.fact_mf_nav_daily (
    scheme_key integer NOT NULL,
    date_key integer NOT NULL,
    nav numeric(14,4)
);


ALTER TABLE main.fact_mf_nav_daily OWNER TO raj;

--
-- Name: fact_news_sentiment_daily; Type: TABLE; Schema: main; Owner: raj
--

CREATE TABLE main.fact_news_sentiment_daily (
    security_key integer NOT NULL,
    date_key integer NOT NULL,
    news_count integer NOT NULL,
    avg_sentiment_score numeric(6,4),
    positive_count integer DEFAULT 0 NOT NULL,
    negative_count integer DEFAULT 0 NOT NULL,
    neutral_count integer DEFAULT 0 NOT NULL,
    computed_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE main.fact_news_sentiment_daily OWNER TO raj;

--
-- Name: fact_options_daily; Type: TABLE; Schema: main; Owner: raj
--

CREATE TABLE main.fact_options_daily (
    contract_key integer NOT NULL,
    date_key integer NOT NULL,
    exchange_key integer NOT NULL,
    open numeric(14,2),
    high numeric(14,2),
    low numeric(14,2),
    close numeric(14,2),
    settle_price numeric(14,2),
    underlying_price numeric(14,2),
    open_interest bigint,
    change_in_oi bigint,
    volume bigint,
    turnover numeric(20,2),
    num_trades bigint
);


ALTER TABLE main.fact_options_daily OWNER TO raj;

--
-- Name: fact_price_sentiment_signal; Type: TABLE; Schema: main; Owner: raj
--

CREATE TABLE main.fact_price_sentiment_signal (
    security_key integer NOT NULL,
    date_key integer NOT NULL,
    daily_return_pct numeric(8,4),
    return_zscore numeric(8,4),
    avg_sentiment_score numeric(6,4),
    news_count integer DEFAULT 0 NOT NULL,
    signal_type text NOT NULL,
    flagged boolean DEFAULT false NOT NULL,
    computed_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE main.fact_price_sentiment_signal OWNER TO raj;

--
-- Name: fact_sector_signal; Type: TABLE; Schema: main; Owner: raj
--

CREATE TABLE main.fact_sector_signal (
    sector_key integer NOT NULL,
    date_key integer NOT NULL,
    avg_return_pct numeric(8,4),
    return_zscore numeric(8,4),
    num_holdings integer NOT NULL,
    flagged boolean DEFAULT false NOT NULL,
    computed_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE main.fact_sector_signal OWNER TO raj;

--
-- Name: fact_stock_quality_metric; Type: TABLE; Schema: main; Owner: raj
--

CREATE TABLE main.fact_stock_quality_metric (
    security_key integer NOT NULL,
    score_date_key integer NOT NULL,
    category text NOT NULL,
    metric_name text NOT NULL,
    raw_value numeric(20,6),
    normalized_score numeric(5,2),
    weight numeric(5,2) DEFAULT 1 NOT NULL,
    data_available boolean NOT NULL,
    notes text,
    computed_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE main.fact_stock_quality_metric OWNER TO raj;

--
-- Name: fact_stock_quality_score; Type: TABLE; Schema: main; Owner: raj
--

CREATE TABLE main.fact_stock_quality_score (
    security_key integer NOT NULL,
    score_date_key integer NOT NULL,
    business_quality_score numeric(5,2),
    financial_strength_score numeric(5,2),
    growth_score numeric(5,2),
    governance_score numeric(5,2),
    balance_sheet_score numeric(5,2),
    valuation_score numeric(5,2),
    overall_score numeric(5,2),
    data_completeness_pct numeric(5,2),
    details jsonb,
    computed_at timestamp with time zone DEFAULT now() NOT NULL,
    cash_flow_capital_allocation_score numeric(5,2),
    market_behaviour_score numeric(5,2),
    sector_percentile numeric(5,2),
    overall_percentile numeric(5,2)
);


ALTER TABLE main.fact_stock_quality_score OWNER TO raj;

--
-- Name: COLUMN fact_stock_quality_score.growth_score; Type: COMMENT; Schema: main; Owner: raj
--

COMMENT ON COLUMN main.fact_stock_quality_score.growth_score IS 'Renamed in spirit to Growth & Consistency — includes earnings consistency, not just CAGR.';


--
-- Name: COLUMN fact_stock_quality_score.overall_percentile; Type: COMMENT; Schema: main; Owner: raj
--

COMMENT ON COLUMN main.fact_stock_quality_score.overall_percentile IS 'Percentile within the currently-scored universe (NIFTY 50 only, not yet "all of NSE") — see docs/STOCK_QUALITY_SCORING_SPEC.md.';


--
-- Name: fact_volume; Type: TABLE; Schema: main; Owner: raj
--

CREATE TABLE main.fact_volume (
    security_key integer NOT NULL,
    date_key integer NOT NULL,
    exchange_key integer NOT NULL,
    volume bigint,
    turnover numeric(20,2),
    num_trades bigint
);


ALTER TABLE main.fact_volume OWNER TO raj;

--
-- Name: dim_exchange exchange_key; Type: DEFAULT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.dim_exchange ALTER COLUMN exchange_key SET DEFAULT nextval('main.dim_exchange_exchange_key_seq'::regclass);


--
-- Name: dim_index index_key; Type: DEFAULT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.dim_index ALTER COLUMN index_key SET DEFAULT nextval('main.dim_index_index_key_seq'::regclass);


--
-- Name: dim_mf_scheme scheme_key; Type: DEFAULT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.dim_mf_scheme ALTER COLUMN scheme_key SET DEFAULT nextval('main.dim_mf_scheme_scheme_key_seq'::regclass);


--
-- Name: dim_option_contract contract_key; Type: DEFAULT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.dim_option_contract ALTER COLUMN contract_key SET DEFAULT nextval('main.dim_option_contract_contract_key_seq'::regclass);


--
-- Name: dim_sector sector_key; Type: DEFAULT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.dim_sector ALTER COLUMN sector_key SET DEFAULT nextval('main.dim_sector_sector_key_seq'::regclass);


--
-- Name: dim_security security_key; Type: DEFAULT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.dim_security ALTER COLUMN security_key SET DEFAULT nextval('main.dim_security_security_key_seq'::regclass);


--
-- Name: dim_date dim_date_full_date_key; Type: CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.dim_date
    ADD CONSTRAINT dim_date_full_date_key UNIQUE (full_date);


--
-- Name: dim_date dim_date_pkey; Type: CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.dim_date
    ADD CONSTRAINT dim_date_pkey PRIMARY KEY (date_key);


--
-- Name: dim_exchange dim_exchange_exchange_code_key; Type: CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.dim_exchange
    ADD CONSTRAINT dim_exchange_exchange_code_key UNIQUE (exchange_code);


--
-- Name: dim_exchange dim_exchange_pkey; Type: CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.dim_exchange
    ADD CONSTRAINT dim_exchange_pkey PRIMARY KEY (exchange_key);


--
-- Name: dim_index dim_index_index_name_key; Type: CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.dim_index
    ADD CONSTRAINT dim_index_index_name_key UNIQUE (index_name);


--
-- Name: dim_index dim_index_pkey; Type: CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.dim_index
    ADD CONSTRAINT dim_index_pkey PRIMARY KEY (index_key);


--
-- Name: dim_mf_scheme dim_mf_scheme_pkey; Type: CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.dim_mf_scheme
    ADD CONSTRAINT dim_mf_scheme_pkey PRIMARY KEY (scheme_key);


--
-- Name: dim_mf_scheme dim_mf_scheme_scheme_code_key; Type: CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.dim_mf_scheme
    ADD CONSTRAINT dim_mf_scheme_scheme_code_key UNIQUE (scheme_code);


--
-- Name: dim_option_contract dim_option_contract_pkey; Type: CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.dim_option_contract
    ADD CONSTRAINT dim_option_contract_pkey PRIMARY KEY (contract_key);


--
-- Name: dim_option_contract dim_option_contract_underlying_symbol_expiry_date_strike_pr_key; Type: CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.dim_option_contract
    ADD CONSTRAINT dim_option_contract_underlying_symbol_expiry_date_strike_pr_key UNIQUE (underlying_symbol, expiry_date, strike_price, option_type);


--
-- Name: dim_sector dim_sector_industry_key; Type: CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.dim_sector
    ADD CONSTRAINT dim_sector_industry_key UNIQUE (industry);


--
-- Name: dim_sector dim_sector_pkey; Type: CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.dim_sector
    ADD CONSTRAINT dim_sector_pkey PRIMARY KEY (sector_key);


--
-- Name: dim_security dim_security_pkey; Type: CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.dim_security
    ADD CONSTRAINT dim_security_pkey PRIMARY KEY (security_key);


--
-- Name: dim_security dim_security_symbol_key; Type: CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.dim_security
    ADD CONSTRAINT dim_security_symbol_key UNIQUE (symbol);


--
-- Name: fact_company_dividends fact_company_dividends_pkey; Type: CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_company_dividends
    ADD CONSTRAINT fact_company_dividends_pkey PRIMARY KEY (security_key, ex_date_key);


--
-- Name: fact_company_financials fact_company_financials_pkey; Type: CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_company_financials
    ADD CONSTRAINT fact_company_financials_pkey PRIMARY KEY (security_key, period_type, period_end_date_key);


--
-- Name: fact_company_fundamentals fact_company_fundamentals_pkey; Type: CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_company_fundamentals
    ADD CONSTRAINT fact_company_fundamentals_pkey PRIMARY KEY (security_key, date_key);


--
-- Name: fact_daily_prices fact_daily_prices_pkey; Type: CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_daily_prices
    ADD CONSTRAINT fact_daily_prices_pkey PRIMARY KEY (security_key, date_key);


--
-- Name: fact_delivery fact_delivery_pkey; Type: CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_delivery
    ADD CONSTRAINT fact_delivery_pkey PRIMARY KEY (security_key, date_key);


--
-- Name: fact_index_daily fact_index_daily_pkey; Type: CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_index_daily
    ADD CONSTRAINT fact_index_daily_pkey PRIMARY KEY (index_key, date_key);


--
-- Name: fact_mf_nav_daily fact_mf_nav_daily_pkey; Type: CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_mf_nav_daily
    ADD CONSTRAINT fact_mf_nav_daily_pkey PRIMARY KEY (scheme_key, date_key);


--
-- Name: fact_news_sentiment_daily fact_news_sentiment_daily_pkey; Type: CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_news_sentiment_daily
    ADD CONSTRAINT fact_news_sentiment_daily_pkey PRIMARY KEY (security_key, date_key);


--
-- Name: fact_options_daily fact_options_daily_pkey; Type: CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_options_daily
    ADD CONSTRAINT fact_options_daily_pkey PRIMARY KEY (contract_key, date_key);


--
-- Name: fact_price_sentiment_signal fact_price_sentiment_signal_pkey; Type: CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_price_sentiment_signal
    ADD CONSTRAINT fact_price_sentiment_signal_pkey PRIMARY KEY (security_key, date_key);


--
-- Name: fact_sector_signal fact_sector_signal_pkey; Type: CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_sector_signal
    ADD CONSTRAINT fact_sector_signal_pkey PRIMARY KEY (sector_key, date_key);


--
-- Name: fact_stock_quality_metric fact_stock_quality_metric_pkey; Type: CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_stock_quality_metric
    ADD CONSTRAINT fact_stock_quality_metric_pkey PRIMARY KEY (security_key, score_date_key, metric_name);


--
-- Name: fact_stock_quality_score fact_stock_quality_score_pkey; Type: CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_stock_quality_score
    ADD CONSTRAINT fact_stock_quality_score_pkey PRIMARY KEY (security_key, score_date_key);


--
-- Name: fact_volume fact_volume_pkey; Type: CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_volume
    ADD CONSTRAINT fact_volume_pkey PRIMARY KEY (security_key, date_key);


--
-- Name: ix_fact_daily_prices_date; Type: INDEX; Schema: main; Owner: raj
--

CREATE INDEX ix_fact_daily_prices_date ON main.fact_daily_prices USING btree (date_key);


--
-- Name: ix_fact_delivery_date; Type: INDEX; Schema: main; Owner: raj
--

CREATE INDEX ix_fact_delivery_date ON main.fact_delivery USING btree (date_key);


--
-- Name: ix_fact_index_daily_date; Type: INDEX; Schema: main; Owner: raj
--

CREATE INDEX ix_fact_index_daily_date ON main.fact_index_daily USING btree (date_key);


--
-- Name: ix_fact_mf_nav_daily_date; Type: INDEX; Schema: main; Owner: raj
--

CREATE INDEX ix_fact_mf_nav_daily_date ON main.fact_mf_nav_daily USING btree (date_key);


--
-- Name: ix_fact_options_daily_date; Type: INDEX; Schema: main; Owner: raj
--

CREATE INDEX ix_fact_options_daily_date ON main.fact_options_daily USING btree (date_key);


--
-- Name: ix_fact_sector_signal_flagged; Type: INDEX; Schema: main; Owner: raj
--

CREATE INDEX ix_fact_sector_signal_flagged ON main.fact_sector_signal USING btree (date_key, flagged);


--
-- Name: ix_fact_volume_date; Type: INDEX; Schema: main; Owner: raj
--

CREATE INDEX ix_fact_volume_date ON main.fact_volume USING btree (date_key);


--
-- Name: ix_price_sentiment_signal_flagged; Type: INDEX; Schema: main; Owner: raj
--

CREATE INDEX ix_price_sentiment_signal_flagged ON main.fact_price_sentiment_signal USING btree (date_key, flagged);


--
-- Name: ix_stock_quality_metric_category; Type: INDEX; Schema: main; Owner: raj
--

CREATE INDEX ix_stock_quality_metric_category ON main.fact_stock_quality_metric USING btree (category, metric_name);


--
-- Name: dim_security dim_security_sector_key_fkey; Type: FK CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.dim_security
    ADD CONSTRAINT dim_security_sector_key_fkey FOREIGN KEY (sector_key) REFERENCES main.dim_sector(sector_key);


--
-- Name: fact_company_dividends fact_company_dividends_ex_date_key_fkey; Type: FK CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_company_dividends
    ADD CONSTRAINT fact_company_dividends_ex_date_key_fkey FOREIGN KEY (ex_date_key) REFERENCES main.dim_date(date_key);


--
-- Name: fact_company_dividends fact_company_dividends_security_key_fkey; Type: FK CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_company_dividends
    ADD CONSTRAINT fact_company_dividends_security_key_fkey FOREIGN KEY (security_key) REFERENCES main.dim_security(security_key);


--
-- Name: fact_company_financials fact_company_financials_period_end_date_key_fkey; Type: FK CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_company_financials
    ADD CONSTRAINT fact_company_financials_period_end_date_key_fkey FOREIGN KEY (period_end_date_key) REFERENCES main.dim_date(date_key);


--
-- Name: fact_company_financials fact_company_financials_security_key_fkey; Type: FK CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_company_financials
    ADD CONSTRAINT fact_company_financials_security_key_fkey FOREIGN KEY (security_key) REFERENCES main.dim_security(security_key);


--
-- Name: fact_company_fundamentals fact_company_fundamentals_date_key_fkey; Type: FK CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_company_fundamentals
    ADD CONSTRAINT fact_company_fundamentals_date_key_fkey FOREIGN KEY (date_key) REFERENCES main.dim_date(date_key);


--
-- Name: fact_company_fundamentals fact_company_fundamentals_security_key_fkey; Type: FK CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_company_fundamentals
    ADD CONSTRAINT fact_company_fundamentals_security_key_fkey FOREIGN KEY (security_key) REFERENCES main.dim_security(security_key);


--
-- Name: fact_daily_prices fact_daily_prices_date_key_fkey; Type: FK CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_daily_prices
    ADD CONSTRAINT fact_daily_prices_date_key_fkey FOREIGN KEY (date_key) REFERENCES main.dim_date(date_key);


--
-- Name: fact_daily_prices fact_daily_prices_exchange_key_fkey; Type: FK CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_daily_prices
    ADD CONSTRAINT fact_daily_prices_exchange_key_fkey FOREIGN KEY (exchange_key) REFERENCES main.dim_exchange(exchange_key);


--
-- Name: fact_daily_prices fact_daily_prices_security_key_fkey; Type: FK CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_daily_prices
    ADD CONSTRAINT fact_daily_prices_security_key_fkey FOREIGN KEY (security_key) REFERENCES main.dim_security(security_key);


--
-- Name: fact_delivery fact_delivery_date_key_fkey; Type: FK CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_delivery
    ADD CONSTRAINT fact_delivery_date_key_fkey FOREIGN KEY (date_key) REFERENCES main.dim_date(date_key);


--
-- Name: fact_delivery fact_delivery_exchange_key_fkey; Type: FK CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_delivery
    ADD CONSTRAINT fact_delivery_exchange_key_fkey FOREIGN KEY (exchange_key) REFERENCES main.dim_exchange(exchange_key);


--
-- Name: fact_delivery fact_delivery_security_key_fkey; Type: FK CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_delivery
    ADD CONSTRAINT fact_delivery_security_key_fkey FOREIGN KEY (security_key) REFERENCES main.dim_security(security_key);


--
-- Name: fact_index_daily fact_index_daily_date_key_fkey; Type: FK CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_index_daily
    ADD CONSTRAINT fact_index_daily_date_key_fkey FOREIGN KEY (date_key) REFERENCES main.dim_date(date_key);


--
-- Name: fact_index_daily fact_index_daily_index_key_fkey; Type: FK CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_index_daily
    ADD CONSTRAINT fact_index_daily_index_key_fkey FOREIGN KEY (index_key) REFERENCES main.dim_index(index_key);


--
-- Name: fact_mf_nav_daily fact_mf_nav_daily_date_key_fkey; Type: FK CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_mf_nav_daily
    ADD CONSTRAINT fact_mf_nav_daily_date_key_fkey FOREIGN KEY (date_key) REFERENCES main.dim_date(date_key);


--
-- Name: fact_mf_nav_daily fact_mf_nav_daily_scheme_key_fkey; Type: FK CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_mf_nav_daily
    ADD CONSTRAINT fact_mf_nav_daily_scheme_key_fkey FOREIGN KEY (scheme_key) REFERENCES main.dim_mf_scheme(scheme_key);


--
-- Name: fact_news_sentiment_daily fact_news_sentiment_daily_date_key_fkey; Type: FK CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_news_sentiment_daily
    ADD CONSTRAINT fact_news_sentiment_daily_date_key_fkey FOREIGN KEY (date_key) REFERENCES main.dim_date(date_key);


--
-- Name: fact_news_sentiment_daily fact_news_sentiment_daily_security_key_fkey; Type: FK CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_news_sentiment_daily
    ADD CONSTRAINT fact_news_sentiment_daily_security_key_fkey FOREIGN KEY (security_key) REFERENCES main.dim_security(security_key);


--
-- Name: fact_options_daily fact_options_daily_contract_key_fkey; Type: FK CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_options_daily
    ADD CONSTRAINT fact_options_daily_contract_key_fkey FOREIGN KEY (contract_key) REFERENCES main.dim_option_contract(contract_key);


--
-- Name: fact_options_daily fact_options_daily_date_key_fkey; Type: FK CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_options_daily
    ADD CONSTRAINT fact_options_daily_date_key_fkey FOREIGN KEY (date_key) REFERENCES main.dim_date(date_key);


--
-- Name: fact_options_daily fact_options_daily_exchange_key_fkey; Type: FK CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_options_daily
    ADD CONSTRAINT fact_options_daily_exchange_key_fkey FOREIGN KEY (exchange_key) REFERENCES main.dim_exchange(exchange_key);


--
-- Name: fact_price_sentiment_signal fact_price_sentiment_signal_date_key_fkey; Type: FK CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_price_sentiment_signal
    ADD CONSTRAINT fact_price_sentiment_signal_date_key_fkey FOREIGN KEY (date_key) REFERENCES main.dim_date(date_key);


--
-- Name: fact_price_sentiment_signal fact_price_sentiment_signal_security_key_fkey; Type: FK CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_price_sentiment_signal
    ADD CONSTRAINT fact_price_sentiment_signal_security_key_fkey FOREIGN KEY (security_key) REFERENCES main.dim_security(security_key);


--
-- Name: fact_sector_signal fact_sector_signal_date_key_fkey; Type: FK CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_sector_signal
    ADD CONSTRAINT fact_sector_signal_date_key_fkey FOREIGN KEY (date_key) REFERENCES main.dim_date(date_key);


--
-- Name: fact_sector_signal fact_sector_signal_sector_key_fkey; Type: FK CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_sector_signal
    ADD CONSTRAINT fact_sector_signal_sector_key_fkey FOREIGN KEY (sector_key) REFERENCES main.dim_sector(sector_key);


--
-- Name: fact_stock_quality_metric fact_stock_quality_metric_score_date_key_fkey; Type: FK CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_stock_quality_metric
    ADD CONSTRAINT fact_stock_quality_metric_score_date_key_fkey FOREIGN KEY (score_date_key) REFERENCES main.dim_date(date_key);


--
-- Name: fact_stock_quality_metric fact_stock_quality_metric_security_key_fkey; Type: FK CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_stock_quality_metric
    ADD CONSTRAINT fact_stock_quality_metric_security_key_fkey FOREIGN KEY (security_key) REFERENCES main.dim_security(security_key);


--
-- Name: fact_stock_quality_score fact_stock_quality_score_score_date_key_fkey; Type: FK CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_stock_quality_score
    ADD CONSTRAINT fact_stock_quality_score_score_date_key_fkey FOREIGN KEY (score_date_key) REFERENCES main.dim_date(date_key);


--
-- Name: fact_stock_quality_score fact_stock_quality_score_security_key_fkey; Type: FK CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_stock_quality_score
    ADD CONSTRAINT fact_stock_quality_score_security_key_fkey FOREIGN KEY (security_key) REFERENCES main.dim_security(security_key);


--
-- Name: fact_volume fact_volume_date_key_fkey; Type: FK CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_volume
    ADD CONSTRAINT fact_volume_date_key_fkey FOREIGN KEY (date_key) REFERENCES main.dim_date(date_key);


--
-- Name: fact_volume fact_volume_exchange_key_fkey; Type: FK CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_volume
    ADD CONSTRAINT fact_volume_exchange_key_fkey FOREIGN KEY (exchange_key) REFERENCES main.dim_exchange(exchange_key);


--
-- Name: fact_volume fact_volume_security_key_fkey; Type: FK CONSTRAINT; Schema: main; Owner: raj
--

ALTER TABLE ONLY main.fact_volume
    ADD CONSTRAINT fact_volume_security_key_fkey FOREIGN KEY (security_key) REFERENCES main.dim_security(security_key);


--
-- PostgreSQL database dump complete
--

\unrestrict T5cODfGpL8BxdQ9vzu85sAQigXEN3ofmW0z2uOfpsetXMDIt9KaTgC1JzgggDht

