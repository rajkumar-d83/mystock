--
-- PostgreSQL database dump
--

\restrict 3stKct8cDsnWcdQVeUNYejjd6JXiF1TC3ZDKPQ6VDJLPin6xXjAVXX0THfi9Iv7

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
-- Name: portfolio; Type: SCHEMA; Schema: -; Owner: raj
--

CREATE SCHEMA portfolio;


ALTER SCHEMA portfolio OWNER TO raj;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: broker_fee_schedule; Type: TABLE; Schema: portfolio; Owner: raj
--

CREATE TABLE portfolio.broker_fee_schedule (
    fee_schedule_id integer NOT NULL,
    broker text NOT NULL,
    plan text NOT NULL,
    segment text NOT NULL,
    charge_type text NOT NULL,
    side text NOT NULL,
    calc_method text NOT NULL,
    rate_pct numeric(12,8),
    flat_amount numeric(10,4),
    applies_on text,
    effective_from date NOT NULL,
    effective_to date,
    source_url text,
    notes text,
    loaded_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT broker_fee_schedule_calc_method_check CHECK ((calc_method = ANY (ARRAY['flat_per_order'::text, 'pct_of_value'::text, 'min_of_flat_and_pct'::text, 'flat_per_scrip_per_day'::text, 'pct_of_charges'::text])))
);


ALTER TABLE portfolio.broker_fee_schedule OWNER TO raj;

--
-- Name: broker_fee_schedule_fee_schedule_id_seq; Type: SEQUENCE; Schema: portfolio; Owner: raj
--

CREATE SEQUENCE portfolio.broker_fee_schedule_fee_schedule_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE portfolio.broker_fee_schedule_fee_schedule_id_seq OWNER TO raj;

--
-- Name: broker_fee_schedule_fee_schedule_id_seq; Type: SEQUENCE OWNED BY; Schema: portfolio; Owner: raj
--

ALTER SEQUENCE portfolio.broker_fee_schedule_fee_schedule_id_seq OWNED BY portfolio.broker_fee_schedule.fee_schedule_id;


--
-- Name: daily_alert; Type: TABLE; Schema: portfolio; Owner: raj
--

CREATE TABLE portfolio.daily_alert (
    portfolio_id integer NOT NULL,
    date_key integer NOT NULL,
    portfolio_value_change_pct numeric(8,4),
    portfolio_value_change_abs numeric(20,2),
    stock_signals_count integer DEFAULT 0 NOT NULL,
    sector_signals_count integer DEFAULT 0 NOT NULL,
    summary text,
    computed_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE portfolio.daily_alert OWNER TO raj;

--
-- Name: fact_portfolio_health; Type: TABLE; Schema: portfolio; Owner: raj
--

CREATE TABLE portfolio.fact_portfolio_health (
    portfolio_id integer NOT NULL,
    date_key integer NOT NULL,
    weighted_overall_score numeric(5,2),
    weighted_business_quality numeric(5,2),
    weighted_financial_strength numeric(5,2),
    weighted_growth_consistency numeric(5,2),
    weighted_cash_flow_capital_allocation numeric(5,2),
    weighted_balance_sheet numeric(5,2),
    weighted_governance numeric(5,2),
    weighted_valuation numeric(5,2),
    weighted_market_behaviour numeric(5,2),
    top_holding_pct numeric(5,2),
    top_sector_pct numeric(5,2),
    holdings_with_score_pct numeric(5,2)
);


ALTER TABLE portfolio.fact_portfolio_health OWNER TO raj;

--
-- Name: fact_portfolio_value_daily; Type: TABLE; Schema: portfolio; Owner: raj
--

CREATE TABLE portfolio.fact_portfolio_value_daily (
    portfolio_id integer NOT NULL,
    date_key integer NOT NULL,
    market_value numeric(20,2) NOT NULL,
    cost_basis numeric(20,2) NOT NULL,
    cash_dividends_received numeric(20,2) DEFAULT 0 NOT NULL,
    unrealized_pnl numeric(20,2) NOT NULL,
    realized_pnl numeric(20,2) DEFAULT 0 NOT NULL
);


ALTER TABLE portfolio.fact_portfolio_value_daily OWNER TO raj;

--
-- Name: import_staging_trades; Type: TABLE; Schema: portfolio; Owner: raj
--

CREATE TABLE portfolio.import_staging_trades (
    staging_id bigint NOT NULL,
    portfolio_id integer NOT NULL,
    source_file text NOT NULL,
    trade_date date NOT NULL,
    company_raw text NOT NULL,
    scrip_code_raw text,
    side text NOT NULL,
    quantity numeric(14,4) NOT NULL,
    price numeric(14,4) NOT NULL,
    matched_security_key integer,
    match_method text,
    match_confidence numeric(4,3),
    reviewed boolean DEFAULT false NOT NULL,
    promoted boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT import_staging_trades_side_check CHECK ((side = ANY (ARRAY['BUY'::text, 'SELL'::text])))
);


ALTER TABLE portfolio.import_staging_trades OWNER TO raj;

--
-- Name: import_staging_trades_staging_id_seq; Type: SEQUENCE; Schema: portfolio; Owner: raj
--

CREATE SEQUENCE portfolio.import_staging_trades_staging_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE portfolio.import_staging_trades_staging_id_seq OWNER TO raj;

--
-- Name: import_staging_trades_staging_id_seq; Type: SEQUENCE OWNED BY; Schema: portfolio; Owner: raj
--

ALTER SEQUENCE portfolio.import_staging_trades_staging_id_seq OWNED BY portfolio.import_staging_trades.staging_id;


--
-- Name: portfolios; Type: TABLE; Schema: portfolio; Owner: raj
--

CREATE TABLE portfolio.portfolios (
    portfolio_id integer NOT NULL,
    user_id integer NOT NULL,
    portfolio_name text NOT NULL,
    broker text,
    description text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE portfolio.portfolios OWNER TO raj;

--
-- Name: portfolios_portfolio_id_seq; Type: SEQUENCE; Schema: portfolio; Owner: raj
--

CREATE SEQUENCE portfolio.portfolios_portfolio_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE portfolio.portfolios_portfolio_id_seq OWNER TO raj;

--
-- Name: portfolios_portfolio_id_seq; Type: SEQUENCE OWNED BY; Schema: portfolio; Owner: raj
--

ALTER SEQUENCE portfolio.portfolios_portfolio_id_seq OWNED BY portfolio.portfolios.portfolio_id;


--
-- Name: transactions; Type: TABLE; Schema: portfolio; Owner: raj
--

CREATE TABLE portfolio.transactions (
    transaction_id bigint NOT NULL,
    portfolio_id integer NOT NULL,
    security_key integer NOT NULL,
    transaction_type text NOT NULL,
    transaction_date date NOT NULL,
    quantity numeric(14,4) NOT NULL,
    price numeric(14,4) NOT NULL,
    fees numeric(14,4) DEFAULT 0 NOT NULL,
    source_file text,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT transactions_price_check CHECK ((price >= (0)::numeric)),
    CONSTRAINT transactions_quantity_check CHECK ((quantity > (0)::numeric)),
    CONSTRAINT transactions_transaction_type_check CHECK ((transaction_type = ANY (ARRAY['BUY'::text, 'SELL'::text, 'OPENING_BALANCE'::text])))
);


ALTER TABLE portfolio.transactions OWNER TO raj;

--
-- Name: transactions_transaction_id_seq; Type: SEQUENCE; Schema: portfolio; Owner: raj
--

CREATE SEQUENCE portfolio.transactions_transaction_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE portfolio.transactions_transaction_id_seq OWNER TO raj;

--
-- Name: transactions_transaction_id_seq; Type: SEQUENCE OWNED BY; Schema: portfolio; Owner: raj
--

ALTER SEQUENCE portfolio.transactions_transaction_id_seq OWNED BY portfolio.transactions.transaction_id;


--
-- Name: users; Type: TABLE; Schema: portfolio; Owner: raj
--

CREATE TABLE portfolio.users (
    user_id integer NOT NULL,
    username text NOT NULL,
    display_name text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE portfolio.users OWNER TO raj;

--
-- Name: users_user_id_seq; Type: SEQUENCE; Schema: portfolio; Owner: raj
--

CREATE SEQUENCE portfolio.users_user_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE portfolio.users_user_id_seq OWNER TO raj;

--
-- Name: users_user_id_seq; Type: SEQUENCE OWNED BY; Schema: portfolio; Owner: raj
--

ALTER SEQUENCE portfolio.users_user_id_seq OWNED BY portfolio.users.user_id;


--
-- Name: broker_fee_schedule fee_schedule_id; Type: DEFAULT; Schema: portfolio; Owner: raj
--

ALTER TABLE ONLY portfolio.broker_fee_schedule ALTER COLUMN fee_schedule_id SET DEFAULT nextval('portfolio.broker_fee_schedule_fee_schedule_id_seq'::regclass);


--
-- Name: import_staging_trades staging_id; Type: DEFAULT; Schema: portfolio; Owner: raj
--

ALTER TABLE ONLY portfolio.import_staging_trades ALTER COLUMN staging_id SET DEFAULT nextval('portfolio.import_staging_trades_staging_id_seq'::regclass);


--
-- Name: portfolios portfolio_id; Type: DEFAULT; Schema: portfolio; Owner: raj
--

ALTER TABLE ONLY portfolio.portfolios ALTER COLUMN portfolio_id SET DEFAULT nextval('portfolio.portfolios_portfolio_id_seq'::regclass);


--
-- Name: transactions transaction_id; Type: DEFAULT; Schema: portfolio; Owner: raj
--

ALTER TABLE ONLY portfolio.transactions ALTER COLUMN transaction_id SET DEFAULT nextval('portfolio.transactions_transaction_id_seq'::regclass);


--
-- Name: users user_id; Type: DEFAULT; Schema: portfolio; Owner: raj
--

ALTER TABLE ONLY portfolio.users ALTER COLUMN user_id SET DEFAULT nextval('portfolio.users_user_id_seq'::regclass);


--
-- Name: broker_fee_schedule broker_fee_schedule_pkey; Type: CONSTRAINT; Schema: portfolio; Owner: raj
--

ALTER TABLE ONLY portfolio.broker_fee_schedule
    ADD CONSTRAINT broker_fee_schedule_pkey PRIMARY KEY (fee_schedule_id);


--
-- Name: daily_alert daily_alert_pkey; Type: CONSTRAINT; Schema: portfolio; Owner: raj
--

ALTER TABLE ONLY portfolio.daily_alert
    ADD CONSTRAINT daily_alert_pkey PRIMARY KEY (portfolio_id, date_key);


--
-- Name: fact_portfolio_health fact_portfolio_health_pkey; Type: CONSTRAINT; Schema: portfolio; Owner: raj
--

ALTER TABLE ONLY portfolio.fact_portfolio_health
    ADD CONSTRAINT fact_portfolio_health_pkey PRIMARY KEY (portfolio_id, date_key);


--
-- Name: fact_portfolio_value_daily fact_portfolio_value_daily_pkey; Type: CONSTRAINT; Schema: portfolio; Owner: raj
--

ALTER TABLE ONLY portfolio.fact_portfolio_value_daily
    ADD CONSTRAINT fact_portfolio_value_daily_pkey PRIMARY KEY (portfolio_id, date_key);


--
-- Name: import_staging_trades import_staging_trades_pkey; Type: CONSTRAINT; Schema: portfolio; Owner: raj
--

ALTER TABLE ONLY portfolio.import_staging_trades
    ADD CONSTRAINT import_staging_trades_pkey PRIMARY KEY (staging_id);


--
-- Name: portfolios portfolios_pkey; Type: CONSTRAINT; Schema: portfolio; Owner: raj
--

ALTER TABLE ONLY portfolio.portfolios
    ADD CONSTRAINT portfolios_pkey PRIMARY KEY (portfolio_id);


--
-- Name: portfolios portfolios_user_id_portfolio_name_key; Type: CONSTRAINT; Schema: portfolio; Owner: raj
--

ALTER TABLE ONLY portfolio.portfolios
    ADD CONSTRAINT portfolios_user_id_portfolio_name_key UNIQUE (user_id, portfolio_name);


--
-- Name: transactions transactions_pkey; Type: CONSTRAINT; Schema: portfolio; Owner: raj
--

ALTER TABLE ONLY portfolio.transactions
    ADD CONSTRAINT transactions_pkey PRIMARY KEY (transaction_id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: portfolio; Owner: raj
--

ALTER TABLE ONLY portfolio.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (user_id);


--
-- Name: users users_username_key; Type: CONSTRAINT; Schema: portfolio; Owner: raj
--

ALTER TABLE ONLY portfolio.users
    ADD CONSTRAINT users_username_key UNIQUE (username);


--
-- Name: ix_broker_fee_schedule_lookup; Type: INDEX; Schema: portfolio; Owner: raj
--

CREATE INDEX ix_broker_fee_schedule_lookup ON portfolio.broker_fee_schedule USING btree (broker, plan, segment, effective_from);


--
-- Name: ix_import_staging_trades_portfolio; Type: INDEX; Schema: portfolio; Owner: raj
--

CREATE INDEX ix_import_staging_trades_portfolio ON portfolio.import_staging_trades USING btree (portfolio_id, reviewed, promoted);


--
-- Name: ix_portfolio_transactions_portfolio; Type: INDEX; Schema: portfolio; Owner: raj
--

CREATE INDEX ix_portfolio_transactions_portfolio ON portfolio.transactions USING btree (portfolio_id, transaction_date);


--
-- Name: ix_portfolio_transactions_security; Type: INDEX; Schema: portfolio; Owner: raj
--

CREATE INDEX ix_portfolio_transactions_security ON portfolio.transactions USING btree (security_key);


--
-- Name: ix_portfolio_value_daily_date; Type: INDEX; Schema: portfolio; Owner: raj
--

CREATE INDEX ix_portfolio_value_daily_date ON portfolio.fact_portfolio_value_daily USING btree (date_key);


--
-- Name: ux_transactions_dedupe; Type: INDEX; Schema: portfolio; Owner: raj
--

CREATE UNIQUE INDEX ux_transactions_dedupe ON portfolio.transactions USING btree (portfolio_id, security_key, transaction_type, transaction_date, quantity, price);


--
-- Name: daily_alert daily_alert_date_key_fkey; Type: FK CONSTRAINT; Schema: portfolio; Owner: raj
--

ALTER TABLE ONLY portfolio.daily_alert
    ADD CONSTRAINT daily_alert_date_key_fkey FOREIGN KEY (date_key) REFERENCES main.dim_date(date_key);


--
-- Name: daily_alert daily_alert_portfolio_id_fkey; Type: FK CONSTRAINT; Schema: portfolio; Owner: raj
--

ALTER TABLE ONLY portfolio.daily_alert
    ADD CONSTRAINT daily_alert_portfolio_id_fkey FOREIGN KEY (portfolio_id) REFERENCES portfolio.portfolios(portfolio_id);


--
-- Name: fact_portfolio_health fact_portfolio_health_date_key_fkey; Type: FK CONSTRAINT; Schema: portfolio; Owner: raj
--

ALTER TABLE ONLY portfolio.fact_portfolio_health
    ADD CONSTRAINT fact_portfolio_health_date_key_fkey FOREIGN KEY (date_key) REFERENCES main.dim_date(date_key);


--
-- Name: fact_portfolio_health fact_portfolio_health_portfolio_id_fkey; Type: FK CONSTRAINT; Schema: portfolio; Owner: raj
--

ALTER TABLE ONLY portfolio.fact_portfolio_health
    ADD CONSTRAINT fact_portfolio_health_portfolio_id_fkey FOREIGN KEY (portfolio_id) REFERENCES portfolio.portfolios(portfolio_id);


--
-- Name: fact_portfolio_value_daily fact_portfolio_value_daily_date_key_fkey; Type: FK CONSTRAINT; Schema: portfolio; Owner: raj
--

ALTER TABLE ONLY portfolio.fact_portfolio_value_daily
    ADD CONSTRAINT fact_portfolio_value_daily_date_key_fkey FOREIGN KEY (date_key) REFERENCES main.dim_date(date_key);


--
-- Name: fact_portfolio_value_daily fact_portfolio_value_daily_portfolio_id_fkey; Type: FK CONSTRAINT; Schema: portfolio; Owner: raj
--

ALTER TABLE ONLY portfolio.fact_portfolio_value_daily
    ADD CONSTRAINT fact_portfolio_value_daily_portfolio_id_fkey FOREIGN KEY (portfolio_id) REFERENCES portfolio.portfolios(portfolio_id);


--
-- Name: import_staging_trades import_staging_trades_matched_security_key_fkey; Type: FK CONSTRAINT; Schema: portfolio; Owner: raj
--

ALTER TABLE ONLY portfolio.import_staging_trades
    ADD CONSTRAINT import_staging_trades_matched_security_key_fkey FOREIGN KEY (matched_security_key) REFERENCES main.dim_security(security_key);


--
-- Name: import_staging_trades import_staging_trades_portfolio_id_fkey; Type: FK CONSTRAINT; Schema: portfolio; Owner: raj
--

ALTER TABLE ONLY portfolio.import_staging_trades
    ADD CONSTRAINT import_staging_trades_portfolio_id_fkey FOREIGN KEY (portfolio_id) REFERENCES portfolio.portfolios(portfolio_id);


--
-- Name: portfolios portfolios_user_id_fkey; Type: FK CONSTRAINT; Schema: portfolio; Owner: raj
--

ALTER TABLE ONLY portfolio.portfolios
    ADD CONSTRAINT portfolios_user_id_fkey FOREIGN KEY (user_id) REFERENCES portfolio.users(user_id);


--
-- Name: transactions transactions_portfolio_id_fkey; Type: FK CONSTRAINT; Schema: portfolio; Owner: raj
--

ALTER TABLE ONLY portfolio.transactions
    ADD CONSTRAINT transactions_portfolio_id_fkey FOREIGN KEY (portfolio_id) REFERENCES portfolio.portfolios(portfolio_id);


--
-- Name: transactions transactions_security_key_fkey; Type: FK CONSTRAINT; Schema: portfolio; Owner: raj
--

ALTER TABLE ONLY portfolio.transactions
    ADD CONSTRAINT transactions_security_key_fkey FOREIGN KEY (security_key) REFERENCES main.dim_security(security_key);


--
-- Name: SCHEMA portfolio; Type: ACL; Schema: -; Owner: raj
--

GRANT USAGE ON SCHEMA portfolio TO mcp_reader;


--
-- Name: TABLE broker_fee_schedule; Type: ACL; Schema: portfolio; Owner: raj
--

GRANT SELECT ON TABLE portfolio.broker_fee_schedule TO mcp_reader;


--
-- Name: TABLE daily_alert; Type: ACL; Schema: portfolio; Owner: raj
--

GRANT SELECT ON TABLE portfolio.daily_alert TO mcp_reader;


--
-- Name: TABLE fact_portfolio_health; Type: ACL; Schema: portfolio; Owner: raj
--

GRANT SELECT ON TABLE portfolio.fact_portfolio_health TO mcp_reader;


--
-- Name: TABLE fact_portfolio_value_daily; Type: ACL; Schema: portfolio; Owner: raj
--

GRANT SELECT ON TABLE portfolio.fact_portfolio_value_daily TO mcp_reader;


--
-- Name: TABLE import_staging_trades; Type: ACL; Schema: portfolio; Owner: raj
--

GRANT SELECT ON TABLE portfolio.import_staging_trades TO mcp_reader;


--
-- Name: TABLE portfolios; Type: ACL; Schema: portfolio; Owner: raj
--

GRANT SELECT ON TABLE portfolio.portfolios TO mcp_reader;


--
-- Name: TABLE transactions; Type: ACL; Schema: portfolio; Owner: raj
--

GRANT SELECT ON TABLE portfolio.transactions TO mcp_reader;


--
-- Name: TABLE users; Type: ACL; Schema: portfolio; Owner: raj
--

GRANT SELECT ON TABLE portfolio.users TO mcp_reader;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: portfolio; Owner: raj
--

ALTER DEFAULT PRIVILEGES FOR ROLE raj IN SCHEMA portfolio GRANT SELECT ON TABLES TO mcp_reader;


--
-- PostgreSQL database dump complete
--

\unrestrict 3stKct8cDsnWcdQVeUNYejjd6JXiF1TC3ZDKPQ6VDJLPin6xXjAVXX0THfi9Iv7

