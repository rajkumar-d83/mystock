--
-- PostgreSQL database dump
--

\restrict od2E8nOlh1NHcEdkb5CA5OneWgV7HJkuPoDUKgN3KKqMxDdwLDi5cGCBB5eTq1c

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
-- Name: staging; Type: SCHEMA; Schema: -; Owner: raj
--

CREATE SCHEMA staging;


ALTER SCHEMA staging OWNER TO raj;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: company_dividends; Type: TABLE; Schema: staging; Owner: raj
--

CREATE TABLE staging.company_dividends (
    symbol text NOT NULL,
    ex_date date NOT NULL,
    dividend numeric(14,4),
    loaded_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE staging.company_dividends OWNER TO raj;

--
-- Name: company_financials; Type: TABLE; Schema: staging; Owner: raj
--

CREATE TABLE staging.company_financials (
    symbol text NOT NULL,
    period_type text NOT NULL,
    period_end_date date NOT NULL,
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
    loaded_at timestamp with time zone DEFAULT now() NOT NULL,
    shares_outstanding numeric(20,2),
    total_assets numeric(20,2),
    net_share_issuance numeric(20,2)
);


ALTER TABLE staging.company_financials OWNER TO raj;

--
-- Name: company_fundamentals_snapshot; Type: TABLE; Schema: staging; Owner: raj
--

CREATE TABLE staging.company_fundamentals_snapshot (
    symbol text NOT NULL,
    snapshot_date date NOT NULL,
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
    quick_ratio numeric(8,4),
    loaded_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE staging.company_fundamentals_snapshot OWNER TO raj;

--
-- Name: equity_master; Type: TABLE; Schema: staging; Owner: raj
--

CREATE TABLE staging.equity_master (
    symbol text NOT NULL,
    company_name text,
    series text,
    listing_date date,
    isin text,
    face_value numeric(12,2),
    market_lot integer,
    paid_up_value numeric(12,2),
    is_active boolean DEFAULT true NOT NULL,
    loaded_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE staging.equity_master OWNER TO raj;

--
-- Name: fo_options_daily; Type: TABLE; Schema: staging; Owner: raj
--

CREATE TABLE staging.fo_options_daily (
    underlying_symbol text NOT NULL,
    expiry_date date NOT NULL,
    strike_price numeric(12,2) NOT NULL,
    option_type text NOT NULL,
    trade_date date NOT NULL,
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
    num_trades bigint,
    source_system text NOT NULL,
    loaded_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE staging.fo_options_daily OWNER TO raj;

--
-- Name: index_daily; Type: TABLE; Schema: staging; Owner: raj
--

CREATE TABLE staging.index_daily (
    index_name text NOT NULL,
    trade_date date NOT NULL,
    open_value numeric(14,2),
    high_value numeric(14,2),
    low_value numeric(14,2),
    close_value numeric(14,2),
    pe_ratio numeric(12,4),
    pb_ratio numeric(12,4),
    dividend_yield numeric(8,4),
    loaded_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE staging.index_daily OWNER TO raj;

--
-- Name: news_raw; Type: TABLE; Schema: staging; Owner: raj
--

CREATE TABLE staging.news_raw (
    id bigint NOT NULL,
    security_key integer NOT NULL,
    source text DEFAULT 'google_news_rss'::text NOT NULL,
    link text NOT NULL,
    raw_payload jsonb NOT NULL,
    published_at timestamp with time zone,
    batch_id uuid NOT NULL,
    fetched_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE staging.news_raw OWNER TO raj;

--
-- Name: news_raw_id_seq; Type: SEQUENCE; Schema: staging; Owner: raj
--

CREATE SEQUENCE staging.news_raw_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE staging.news_raw_id_seq OWNER TO raj;

--
-- Name: news_raw_id_seq; Type: SEQUENCE OWNED BY; Schema: staging; Owner: raj
--

ALTER SEQUENCE staging.news_raw_id_seq OWNED BY staging.news_raw.id;


--
-- Name: news_sentiment; Type: TABLE; Schema: staging; Owner: raj
--

CREATE TABLE staging.news_sentiment (
    news_raw_id bigint NOT NULL,
    security_key integer NOT NULL,
    title text NOT NULL,
    link text NOT NULL,
    source_name text,
    published_at timestamp with time zone,
    sentiment_label text NOT NULL,
    sentiment_score numeric(6,4) NOT NULL,
    model_name text DEFAULT 'ProsusAI/finbert'::text NOT NULL,
    scored_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT news_sentiment_sentiment_label_check CHECK ((sentiment_label = ANY (ARRAY['positive'::text, 'negative'::text, 'neutral'::text])))
);


ALTER TABLE staging.news_sentiment OWNER TO raj;

--
-- Name: nse_bhavcopy_raw; Type: TABLE; Schema: staging; Owner: raj
--

CREATE TABLE staging.nse_bhavcopy_raw (
    id bigint NOT NULL,
    trade_date date NOT NULL,
    symbol text,
    raw_payload jsonb NOT NULL,
    source text DEFAULT 'jugaad_data.bhavcopy'::text NOT NULL,
    batch_id uuid NOT NULL,
    fetched_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE staging.nse_bhavcopy_raw OWNER TO raj;

--
-- Name: nse_bhavcopy_raw_id_seq; Type: SEQUENCE; Schema: staging; Owner: raj
--

CREATE SEQUENCE staging.nse_bhavcopy_raw_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE staging.nse_bhavcopy_raw_id_seq OWNER TO raj;

--
-- Name: nse_bhavcopy_raw_id_seq; Type: SEQUENCE OWNED BY; Schema: staging; Owner: raj
--

ALTER SEQUENCE staging.nse_bhavcopy_raw_id_seq OWNED BY staging.nse_bhavcopy_raw.id;


--
-- Name: nse_equity_master; Type: TABLE; Schema: staging; Owner: raj
--

CREATE TABLE staging.nse_equity_master (
    id bigint NOT NULL,
    symbol text NOT NULL,
    raw_payload jsonb NOT NULL,
    batch_id uuid NOT NULL,
    fetched_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE staging.nse_equity_master OWNER TO raj;

--
-- Name: nse_equity_master_id_seq; Type: SEQUENCE; Schema: staging; Owner: raj
--

CREATE SEQUENCE staging.nse_equity_master_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE staging.nse_equity_master_id_seq OWNER TO raj;

--
-- Name: nse_equity_master_id_seq; Type: SEQUENCE OWNED BY; Schema: staging; Owner: raj
--

ALTER SEQUENCE staging.nse_equity_master_id_seq OWNED BY staging.nse_equity_master.id;


--
-- Name: nse_fo_bhavcopy_raw; Type: TABLE; Schema: staging; Owner: raj
--

CREATE TABLE staging.nse_fo_bhavcopy_raw (
    id bigint NOT NULL,
    trade_date date NOT NULL,
    underlying_symbol text NOT NULL,
    expiry_date date NOT NULL,
    strike_price numeric(12,2) NOT NULL,
    option_type text NOT NULL,
    raw_payload jsonb NOT NULL,
    source text NOT NULL,
    batch_id uuid NOT NULL,
    fetched_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE staging.nse_fo_bhavcopy_raw OWNER TO raj;

--
-- Name: nse_fo_bhavcopy_raw_id_seq; Type: SEQUENCE; Schema: staging; Owner: raj
--

CREATE SEQUENCE staging.nse_fo_bhavcopy_raw_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE staging.nse_fo_bhavcopy_raw_id_seq OWNER TO raj;

--
-- Name: nse_fo_bhavcopy_raw_id_seq; Type: SEQUENCE OWNED BY; Schema: staging; Owner: raj
--

ALTER SEQUENCE staging.nse_fo_bhavcopy_raw_id_seq OWNED BY staging.nse_fo_bhavcopy_raw.id;


--
-- Name: nse_indices_bhavcopy_raw; Type: TABLE; Schema: staging; Owner: raj
--

CREATE TABLE staging.nse_indices_bhavcopy_raw (
    id bigint NOT NULL,
    trade_date date NOT NULL,
    index_name text NOT NULL,
    raw_payload jsonb NOT NULL,
    source text DEFAULT 'niftyindices_daily_snapshot'::text NOT NULL,
    batch_id uuid NOT NULL,
    fetched_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE staging.nse_indices_bhavcopy_raw OWNER TO raj;

--
-- Name: nse_indices_bhavcopy_raw_id_seq; Type: SEQUENCE; Schema: staging; Owner: raj
--

CREATE SEQUENCE staging.nse_indices_bhavcopy_raw_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE staging.nse_indices_bhavcopy_raw_id_seq OWNER TO raj;

--
-- Name: nse_indices_bhavcopy_raw_id_seq; Type: SEQUENCE OWNED BY; Schema: staging; Owner: raj
--

ALTER SEQUENCE staging.nse_indices_bhavcopy_raw_id_seq OWNED BY staging.nse_indices_bhavcopy_raw.id;


--
-- Name: nse_stock_history_raw; Type: TABLE; Schema: staging; Owner: raj
--

CREATE TABLE staging.nse_stock_history_raw (
    id bigint NOT NULL,
    symbol text NOT NULL,
    trade_date date NOT NULL,
    raw_payload jsonb NOT NULL,
    source text DEFAULT 'jugaad_data.stock_df'::text NOT NULL,
    batch_id uuid NOT NULL,
    fetched_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE staging.nse_stock_history_raw OWNER TO raj;

--
-- Name: nse_stock_history_raw_id_seq; Type: SEQUENCE; Schema: staging; Owner: raj
--

CREATE SEQUENCE staging.nse_stock_history_raw_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE staging.nse_stock_history_raw_id_seq OWNER TO raj;

--
-- Name: nse_stock_history_raw_id_seq; Type: SEQUENCE OWNED BY; Schema: staging; Owner: raj
--

ALTER SEQUENCE staging.nse_stock_history_raw_id_seq OWNED BY staging.nse_stock_history_raw.id;


--
-- Name: sector_map; Type: TABLE; Schema: staging; Owner: raj
--

CREATE TABLE staging.sector_map (
    symbol text NOT NULL,
    company_name text,
    industry text NOT NULL,
    index_source text DEFAULT 'ind_niftytotalmarket_list'::text NOT NULL,
    loaded_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE staging.sector_map OWNER TO raj;

--
-- Name: stock_daily; Type: TABLE; Schema: staging; Owner: raj
--

CREATE TABLE staging.stock_daily (
    symbol text NOT NULL,
    trade_date date NOT NULL,
    open numeric(14,2),
    high numeric(14,2),
    low numeric(14,2),
    close numeric(14,2),
    prev_close numeric(14,2),
    ltp numeric(14,2),
    vwap numeric(14,2),
    volume bigint,
    turnover numeric(20,2),
    num_trades bigint,
    delivery_qty bigint,
    delivery_pct numeric(6,2),
    source_system text NOT NULL,
    loaded_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE staging.stock_daily OWNER TO raj;

--
-- Name: yf_company_snapshot_raw; Type: TABLE; Schema: staging; Owner: raj
--

CREATE TABLE staging.yf_company_snapshot_raw (
    symbol text NOT NULL,
    snapshot_date date NOT NULL,
    raw_payload jsonb NOT NULL,
    batch_id uuid NOT NULL,
    fetched_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE staging.yf_company_snapshot_raw OWNER TO raj;

--
-- Name: yf_dividends_raw; Type: TABLE; Schema: staging; Owner: raj
--

CREATE TABLE staging.yf_dividends_raw (
    symbol text NOT NULL,
    ex_date date NOT NULL,
    dividend numeric(14,4),
    batch_id uuid NOT NULL,
    fetched_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE staging.yf_dividends_raw OWNER TO raj;

--
-- Name: yf_financials_raw; Type: TABLE; Schema: staging; Owner: raj
--

CREATE TABLE staging.yf_financials_raw (
    symbol text NOT NULL,
    statement_type text NOT NULL,
    period_type text NOT NULL,
    period_end_date date NOT NULL,
    raw_payload jsonb NOT NULL,
    batch_id uuid NOT NULL,
    fetched_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE staging.yf_financials_raw OWNER TO raj;

--
-- Name: news_raw id; Type: DEFAULT; Schema: staging; Owner: raj
--

ALTER TABLE ONLY staging.news_raw ALTER COLUMN id SET DEFAULT nextval('staging.news_raw_id_seq'::regclass);


--
-- Name: nse_bhavcopy_raw id; Type: DEFAULT; Schema: staging; Owner: raj
--

ALTER TABLE ONLY staging.nse_bhavcopy_raw ALTER COLUMN id SET DEFAULT nextval('staging.nse_bhavcopy_raw_id_seq'::regclass);


--
-- Name: nse_equity_master id; Type: DEFAULT; Schema: staging; Owner: raj
--

ALTER TABLE ONLY staging.nse_equity_master ALTER COLUMN id SET DEFAULT nextval('staging.nse_equity_master_id_seq'::regclass);


--
-- Name: nse_fo_bhavcopy_raw id; Type: DEFAULT; Schema: staging; Owner: raj
--

ALTER TABLE ONLY staging.nse_fo_bhavcopy_raw ALTER COLUMN id SET DEFAULT nextval('staging.nse_fo_bhavcopy_raw_id_seq'::regclass);


--
-- Name: nse_indices_bhavcopy_raw id; Type: DEFAULT; Schema: staging; Owner: raj
--

ALTER TABLE ONLY staging.nse_indices_bhavcopy_raw ALTER COLUMN id SET DEFAULT nextval('staging.nse_indices_bhavcopy_raw_id_seq'::regclass);


--
-- Name: nse_stock_history_raw id; Type: DEFAULT; Schema: staging; Owner: raj
--

ALTER TABLE ONLY staging.nse_stock_history_raw ALTER COLUMN id SET DEFAULT nextval('staging.nse_stock_history_raw_id_seq'::regclass);


--
-- Name: company_dividends company_dividends_pkey; Type: CONSTRAINT; Schema: staging; Owner: raj
--

ALTER TABLE ONLY staging.company_dividends
    ADD CONSTRAINT company_dividends_pkey PRIMARY KEY (symbol, ex_date);


--
-- Name: company_financials company_financials_pkey; Type: CONSTRAINT; Schema: staging; Owner: raj
--

ALTER TABLE ONLY staging.company_financials
    ADD CONSTRAINT company_financials_pkey PRIMARY KEY (symbol, period_type, period_end_date);


--
-- Name: company_fundamentals_snapshot company_fundamentals_snapshot_pkey; Type: CONSTRAINT; Schema: staging; Owner: raj
--

ALTER TABLE ONLY staging.company_fundamentals_snapshot
    ADD CONSTRAINT company_fundamentals_snapshot_pkey PRIMARY KEY (symbol, snapshot_date);


--
-- Name: equity_master equity_master_pkey; Type: CONSTRAINT; Schema: staging; Owner: raj
--

ALTER TABLE ONLY staging.equity_master
    ADD CONSTRAINT equity_master_pkey PRIMARY KEY (symbol);


--
-- Name: fo_options_daily fo_options_daily_pkey; Type: CONSTRAINT; Schema: staging; Owner: raj
--

ALTER TABLE ONLY staging.fo_options_daily
    ADD CONSTRAINT fo_options_daily_pkey PRIMARY KEY (underlying_symbol, expiry_date, strike_price, option_type, trade_date);


--
-- Name: index_daily index_daily_pkey; Type: CONSTRAINT; Schema: staging; Owner: raj
--

ALTER TABLE ONLY staging.index_daily
    ADD CONSTRAINT index_daily_pkey PRIMARY KEY (index_name, trade_date);


--
-- Name: news_raw news_raw_pkey; Type: CONSTRAINT; Schema: staging; Owner: raj
--

ALTER TABLE ONLY staging.news_raw
    ADD CONSTRAINT news_raw_pkey PRIMARY KEY (id);


--
-- Name: news_raw news_raw_security_key_link_key; Type: CONSTRAINT; Schema: staging; Owner: raj
--

ALTER TABLE ONLY staging.news_raw
    ADD CONSTRAINT news_raw_security_key_link_key UNIQUE (security_key, link);


--
-- Name: news_sentiment news_sentiment_pkey; Type: CONSTRAINT; Schema: staging; Owner: raj
--

ALTER TABLE ONLY staging.news_sentiment
    ADD CONSTRAINT news_sentiment_pkey PRIMARY KEY (news_raw_id);


--
-- Name: nse_bhavcopy_raw nse_bhavcopy_raw_pkey; Type: CONSTRAINT; Schema: staging; Owner: raj
--

ALTER TABLE ONLY staging.nse_bhavcopy_raw
    ADD CONSTRAINT nse_bhavcopy_raw_pkey PRIMARY KEY (id);


--
-- Name: nse_bhavcopy_raw nse_bhavcopy_raw_trade_date_symbol_source_key; Type: CONSTRAINT; Schema: staging; Owner: raj
--

ALTER TABLE ONLY staging.nse_bhavcopy_raw
    ADD CONSTRAINT nse_bhavcopy_raw_trade_date_symbol_source_key UNIQUE (trade_date, symbol, source);


--
-- Name: nse_equity_master nse_equity_master_pkey; Type: CONSTRAINT; Schema: staging; Owner: raj
--

ALTER TABLE ONLY staging.nse_equity_master
    ADD CONSTRAINT nse_equity_master_pkey PRIMARY KEY (id);


--
-- Name: nse_fo_bhavcopy_raw nse_fo_bhavcopy_raw_pkey; Type: CONSTRAINT; Schema: staging; Owner: raj
--

ALTER TABLE ONLY staging.nse_fo_bhavcopy_raw
    ADD CONSTRAINT nse_fo_bhavcopy_raw_pkey PRIMARY KEY (id);


--
-- Name: nse_fo_bhavcopy_raw nse_fo_bhavcopy_raw_trade_date_underlying_symbol_expiry_dat_key; Type: CONSTRAINT; Schema: staging; Owner: raj
--

ALTER TABLE ONLY staging.nse_fo_bhavcopy_raw
    ADD CONSTRAINT nse_fo_bhavcopy_raw_trade_date_underlying_symbol_expiry_dat_key UNIQUE (trade_date, underlying_symbol, expiry_date, strike_price, option_type, source);


--
-- Name: nse_indices_bhavcopy_raw nse_indices_bhavcopy_raw_pkey; Type: CONSTRAINT; Schema: staging; Owner: raj
--

ALTER TABLE ONLY staging.nse_indices_bhavcopy_raw
    ADD CONSTRAINT nse_indices_bhavcopy_raw_pkey PRIMARY KEY (id);


--
-- Name: nse_indices_bhavcopy_raw nse_indices_bhavcopy_raw_trade_date_index_name_source_key; Type: CONSTRAINT; Schema: staging; Owner: raj
--

ALTER TABLE ONLY staging.nse_indices_bhavcopy_raw
    ADD CONSTRAINT nse_indices_bhavcopy_raw_trade_date_index_name_source_key UNIQUE (trade_date, index_name, source);


--
-- Name: nse_stock_history_raw nse_stock_history_raw_pkey; Type: CONSTRAINT; Schema: staging; Owner: raj
--

ALTER TABLE ONLY staging.nse_stock_history_raw
    ADD CONSTRAINT nse_stock_history_raw_pkey PRIMARY KEY (id);


--
-- Name: nse_stock_history_raw nse_stock_history_raw_symbol_trade_date_source_key; Type: CONSTRAINT; Schema: staging; Owner: raj
--

ALTER TABLE ONLY staging.nse_stock_history_raw
    ADD CONSTRAINT nse_stock_history_raw_symbol_trade_date_source_key UNIQUE (symbol, trade_date, source);


--
-- Name: sector_map sector_map_pkey; Type: CONSTRAINT; Schema: staging; Owner: raj
--

ALTER TABLE ONLY staging.sector_map
    ADD CONSTRAINT sector_map_pkey PRIMARY KEY (symbol);


--
-- Name: stock_daily stock_daily_pkey; Type: CONSTRAINT; Schema: staging; Owner: raj
--

ALTER TABLE ONLY staging.stock_daily
    ADD CONSTRAINT stock_daily_pkey PRIMARY KEY (symbol, trade_date);


--
-- Name: nse_equity_master uq_equity_master_symbol; Type: CONSTRAINT; Schema: staging; Owner: raj
--

ALTER TABLE ONLY staging.nse_equity_master
    ADD CONSTRAINT uq_equity_master_symbol UNIQUE (symbol);


--
-- Name: yf_company_snapshot_raw yf_company_snapshot_raw_pkey; Type: CONSTRAINT; Schema: staging; Owner: raj
--

ALTER TABLE ONLY staging.yf_company_snapshot_raw
    ADD CONSTRAINT yf_company_snapshot_raw_pkey PRIMARY KEY (symbol, snapshot_date);


--
-- Name: yf_dividends_raw yf_dividends_raw_pkey; Type: CONSTRAINT; Schema: staging; Owner: raj
--

ALTER TABLE ONLY staging.yf_dividends_raw
    ADD CONSTRAINT yf_dividends_raw_pkey PRIMARY KEY (symbol, ex_date);


--
-- Name: yf_financials_raw yf_financials_raw_pkey; Type: CONSTRAINT; Schema: staging; Owner: raj
--

ALTER TABLE ONLY staging.yf_financials_raw
    ADD CONSTRAINT yf_financials_raw_pkey PRIMARY KEY (symbol, statement_type, period_type, period_end_date);


--
-- Name: ix_bhavcopy_raw_date; Type: INDEX; Schema: staging; Owner: raj
--

CREATE INDEX ix_bhavcopy_raw_date ON staging.nse_bhavcopy_raw USING btree (trade_date);


--
-- Name: ix_fo_bhavcopy_raw_date; Type: INDEX; Schema: staging; Owner: raj
--

CREATE INDEX ix_fo_bhavcopy_raw_date ON staging.nse_fo_bhavcopy_raw USING btree (trade_date);


--
-- Name: ix_fo_bhavcopy_raw_underlying; Type: INDEX; Schema: staging; Owner: raj
--

CREATE INDEX ix_fo_bhavcopy_raw_underlying ON staging.nse_fo_bhavcopy_raw USING btree (underlying_symbol, expiry_date);


--
-- Name: ix_news_raw_published; Type: INDEX; Schema: staging; Owner: raj
--

CREATE INDEX ix_news_raw_published ON staging.news_raw USING btree (published_at);


--
-- Name: ix_news_sentiment_security_date; Type: INDEX; Schema: staging; Owner: raj
--

CREATE INDEX ix_news_sentiment_security_date ON staging.news_sentiment USING btree (security_key, published_at);


--
-- Name: ix_nse_indices_bhavcopy_date; Type: INDEX; Schema: staging; Owner: raj
--

CREATE INDEX ix_nse_indices_bhavcopy_date ON staging.nse_indices_bhavcopy_raw USING btree (trade_date);


--
-- Name: ix_nse_indices_bhavcopy_name; Type: INDEX; Schema: staging; Owner: raj
--

CREATE INDEX ix_nse_indices_bhavcopy_name ON staging.nse_indices_bhavcopy_raw USING btree (index_name, trade_date);


--
-- Name: ix_stock_history_raw_date; Type: INDEX; Schema: staging; Owner: raj
--

CREATE INDEX ix_stock_history_raw_date ON staging.nse_stock_history_raw USING btree (trade_date);


--
-- Name: news_raw news_raw_security_key_fkey; Type: FK CONSTRAINT; Schema: staging; Owner: raj
--

ALTER TABLE ONLY staging.news_raw
    ADD CONSTRAINT news_raw_security_key_fkey FOREIGN KEY (security_key) REFERENCES main.dim_security(security_key);


--
-- Name: news_sentiment news_sentiment_news_raw_id_fkey; Type: FK CONSTRAINT; Schema: staging; Owner: raj
--

ALTER TABLE ONLY staging.news_sentiment
    ADD CONSTRAINT news_sentiment_news_raw_id_fkey FOREIGN KEY (news_raw_id) REFERENCES staging.news_raw(id);


--
-- Name: news_sentiment news_sentiment_security_key_fkey; Type: FK CONSTRAINT; Schema: staging; Owner: raj
--

ALTER TABLE ONLY staging.news_sentiment
    ADD CONSTRAINT news_sentiment_security_key_fkey FOREIGN KEY (security_key) REFERENCES main.dim_security(security_key);


--
-- Name: SCHEMA staging; Type: ACL; Schema: -; Owner: raj
--

GRANT USAGE ON SCHEMA staging TO mcp_reader;


--
-- Name: TABLE company_dividends; Type: ACL; Schema: staging; Owner: raj
--

GRANT SELECT ON TABLE staging.company_dividends TO mcp_reader;


--
-- Name: TABLE company_financials; Type: ACL; Schema: staging; Owner: raj
--

GRANT SELECT ON TABLE staging.company_financials TO mcp_reader;


--
-- Name: TABLE company_fundamentals_snapshot; Type: ACL; Schema: staging; Owner: raj
--

GRANT SELECT ON TABLE staging.company_fundamentals_snapshot TO mcp_reader;


--
-- Name: TABLE equity_master; Type: ACL; Schema: staging; Owner: raj
--

GRANT SELECT ON TABLE staging.equity_master TO mcp_reader;


--
-- Name: TABLE fo_options_daily; Type: ACL; Schema: staging; Owner: raj
--

GRANT SELECT ON TABLE staging.fo_options_daily TO mcp_reader;


--
-- Name: TABLE index_daily; Type: ACL; Schema: staging; Owner: raj
--

GRANT SELECT ON TABLE staging.index_daily TO mcp_reader;


--
-- Name: TABLE news_raw; Type: ACL; Schema: staging; Owner: raj
--

GRANT SELECT ON TABLE staging.news_raw TO mcp_reader;


--
-- Name: TABLE news_sentiment; Type: ACL; Schema: staging; Owner: raj
--

GRANT SELECT ON TABLE staging.news_sentiment TO mcp_reader;


--
-- Name: TABLE nse_bhavcopy_raw; Type: ACL; Schema: staging; Owner: raj
--

GRANT SELECT ON TABLE staging.nse_bhavcopy_raw TO mcp_reader;


--
-- Name: TABLE nse_equity_master; Type: ACL; Schema: staging; Owner: raj
--

GRANT SELECT ON TABLE staging.nse_equity_master TO mcp_reader;


--
-- Name: TABLE nse_fo_bhavcopy_raw; Type: ACL; Schema: staging; Owner: raj
--

GRANT SELECT ON TABLE staging.nse_fo_bhavcopy_raw TO mcp_reader;


--
-- Name: TABLE nse_indices_bhavcopy_raw; Type: ACL; Schema: staging; Owner: raj
--

GRANT SELECT ON TABLE staging.nse_indices_bhavcopy_raw TO mcp_reader;


--
-- Name: TABLE nse_stock_history_raw; Type: ACL; Schema: staging; Owner: raj
--

GRANT SELECT ON TABLE staging.nse_stock_history_raw TO mcp_reader;


--
-- Name: TABLE sector_map; Type: ACL; Schema: staging; Owner: raj
--

GRANT SELECT ON TABLE staging.sector_map TO mcp_reader;


--
-- Name: TABLE stock_daily; Type: ACL; Schema: staging; Owner: raj
--

GRANT SELECT ON TABLE staging.stock_daily TO mcp_reader;


--
-- Name: TABLE yf_company_snapshot_raw; Type: ACL; Schema: staging; Owner: raj
--

GRANT SELECT ON TABLE staging.yf_company_snapshot_raw TO mcp_reader;


--
-- Name: TABLE yf_dividends_raw; Type: ACL; Schema: staging; Owner: raj
--

GRANT SELECT ON TABLE staging.yf_dividends_raw TO mcp_reader;


--
-- Name: TABLE yf_financials_raw; Type: ACL; Schema: staging; Owner: raj
--

GRANT SELECT ON TABLE staging.yf_financials_raw TO mcp_reader;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: staging; Owner: raj
--

ALTER DEFAULT PRIVILEGES FOR ROLE raj IN SCHEMA staging GRANT SELECT ON TABLES TO mcp_reader;


--
-- PostgreSQL database dump complete
--

\unrestrict od2E8nOlh1NHcEdkb5CA5OneWgV7HJkuPoDUKgN3KKqMxDdwLDi5cGCBB5eTq1c

