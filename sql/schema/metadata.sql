--
-- PostgreSQL database dump
--

\restrict 0eJmTTTsKLxgpLtHgDK19spgLM6gbLOXreXMYXPuiEAae93zldst7lMa64eDinv

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
-- Name: metadata; Type: SCHEMA; Schema: -; Owner: raj
--

CREATE SCHEMA metadata;


ALTER SCHEMA metadata OWNER TO raj;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: audit; Type: TABLE; Schema: metadata; Owner: raj
--

CREATE TABLE metadata.audit (
    audit_id bigint NOT NULL,
    event_type text NOT NULL,
    target text,
    details jsonb,
    occurred_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE metadata.audit OWNER TO raj;

--
-- Name: audit_audit_id_seq; Type: SEQUENCE; Schema: metadata; Owner: raj
--

CREATE SEQUENCE metadata.audit_audit_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE metadata.audit_audit_id_seq OWNER TO raj;

--
-- Name: audit_audit_id_seq; Type: SEQUENCE OWNED BY; Schema: metadata; Owner: raj
--

ALTER SEQUENCE metadata.audit_audit_id_seq OWNED BY metadata.audit.audit_id;


--
-- Name: columns; Type: TABLE; Schema: metadata; Owner: raj
--

CREATE TABLE metadata.columns (
    schema_name text NOT NULL,
    table_name text NOT NULL,
    column_name text NOT NULL,
    ordinal_position integer,
    data_type text,
    is_nullable boolean,
    description text,
    last_refreshed timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE metadata.columns OWNER TO raj;

--
-- Name: data_quality; Type: TABLE; Schema: metadata; Owner: raj
--

CREATE TABLE metadata.data_quality (
    check_id bigint NOT NULL,
    check_name text NOT NULL,
    table_name text NOT NULL,
    status text NOT NULL,
    metric_value numeric,
    details jsonb,
    checked_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE metadata.data_quality OWNER TO raj;

--
-- Name: data_quality_check_id_seq; Type: SEQUENCE; Schema: metadata; Owner: raj
--

CREATE SEQUENCE metadata.data_quality_check_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE metadata.data_quality_check_id_seq OWNER TO raj;

--
-- Name: data_quality_check_id_seq; Type: SEQUENCE OWNED BY; Schema: metadata; Owner: raj
--

ALTER SEQUENCE metadata.data_quality_check_id_seq OWNED BY metadata.data_quality.check_id;


--
-- Name: doc_embeddings; Type: TABLE; Schema: metadata; Owner: raj
--

CREATE TABLE metadata.doc_embeddings (
    id bigint NOT NULL,
    source_type text NOT NULL,
    source_ref text NOT NULL,
    chunk_text text NOT NULL,
    embedding public.vector(384) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE metadata.doc_embeddings OWNER TO raj;

--
-- Name: doc_embeddings_id_seq; Type: SEQUENCE; Schema: metadata; Owner: raj
--

CREATE SEQUENCE metadata.doc_embeddings_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE metadata.doc_embeddings_id_seq OWNER TO raj;

--
-- Name: doc_embeddings_id_seq; Type: SEQUENCE OWNED BY; Schema: metadata; Owner: raj
--

ALTER SEQUENCE metadata.doc_embeddings_id_seq OWNED BY metadata.doc_embeddings.id;


--
-- Name: etl_runs; Type: TABLE; Schema: metadata; Owner: raj
--

CREATE TABLE metadata.etl_runs (
    run_id uuid DEFAULT gen_random_uuid() NOT NULL,
    job_name text NOT NULL,
    params jsonb,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    ended_at timestamp with time zone,
    status text DEFAULT 'running'::text NOT NULL,
    rows_processed bigint DEFAULT 0 NOT NULL,
    error text
);


ALTER TABLE metadata.etl_runs OWNER TO raj;

--
-- Name: lineage; Type: TABLE; Schema: metadata; Owner: raj
--

CREATE TABLE metadata.lineage (
    target_schema text NOT NULL,
    target_table text NOT NULL,
    source_schema text NOT NULL,
    source_table text NOT NULL,
    transform_script text,
    notes text
);


ALTER TABLE metadata.lineage OWNER TO raj;

--
-- Name: scheduler; Type: TABLE; Schema: metadata; Owner: raj
--

CREATE TABLE metadata.scheduler (
    job_name text NOT NULL,
    schedule_type text NOT NULL,
    schedule_expr text,
    command text,
    description text,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE metadata.scheduler OWNER TO raj;

--
-- Name: tables; Type: TABLE; Schema: metadata; Owner: raj
--

CREATE TABLE metadata.tables (
    schema_name text NOT NULL,
    table_name text NOT NULL,
    layer text,
    description text,
    row_count bigint,
    last_refreshed timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE metadata.tables OWNER TO raj;

--
-- Name: audit audit_id; Type: DEFAULT; Schema: metadata; Owner: raj
--

ALTER TABLE ONLY metadata.audit ALTER COLUMN audit_id SET DEFAULT nextval('metadata.audit_audit_id_seq'::regclass);


--
-- Name: data_quality check_id; Type: DEFAULT; Schema: metadata; Owner: raj
--

ALTER TABLE ONLY metadata.data_quality ALTER COLUMN check_id SET DEFAULT nextval('metadata.data_quality_check_id_seq'::regclass);


--
-- Name: doc_embeddings id; Type: DEFAULT; Schema: metadata; Owner: raj
--

ALTER TABLE ONLY metadata.doc_embeddings ALTER COLUMN id SET DEFAULT nextval('metadata.doc_embeddings_id_seq'::regclass);


--
-- Name: audit audit_pkey; Type: CONSTRAINT; Schema: metadata; Owner: raj
--

ALTER TABLE ONLY metadata.audit
    ADD CONSTRAINT audit_pkey PRIMARY KEY (audit_id);


--
-- Name: columns columns_pkey; Type: CONSTRAINT; Schema: metadata; Owner: raj
--

ALTER TABLE ONLY metadata.columns
    ADD CONSTRAINT columns_pkey PRIMARY KEY (schema_name, table_name, column_name);


--
-- Name: data_quality data_quality_pkey; Type: CONSTRAINT; Schema: metadata; Owner: raj
--

ALTER TABLE ONLY metadata.data_quality
    ADD CONSTRAINT data_quality_pkey PRIMARY KEY (check_id);


--
-- Name: doc_embeddings doc_embeddings_pkey; Type: CONSTRAINT; Schema: metadata; Owner: raj
--

ALTER TABLE ONLY metadata.doc_embeddings
    ADD CONSTRAINT doc_embeddings_pkey PRIMARY KEY (id);


--
-- Name: etl_runs etl_runs_pkey; Type: CONSTRAINT; Schema: metadata; Owner: raj
--

ALTER TABLE ONLY metadata.etl_runs
    ADD CONSTRAINT etl_runs_pkey PRIMARY KEY (run_id);


--
-- Name: lineage lineage_pkey; Type: CONSTRAINT; Schema: metadata; Owner: raj
--

ALTER TABLE ONLY metadata.lineage
    ADD CONSTRAINT lineage_pkey PRIMARY KEY (target_schema, target_table, source_schema, source_table);


--
-- Name: scheduler scheduler_pkey; Type: CONSTRAINT; Schema: metadata; Owner: raj
--

ALTER TABLE ONLY metadata.scheduler
    ADD CONSTRAINT scheduler_pkey PRIMARY KEY (job_name);


--
-- Name: tables tables_pkey; Type: CONSTRAINT; Schema: metadata; Owner: raj
--

ALTER TABLE ONLY metadata.tables
    ADD CONSTRAINT tables_pkey PRIMARY KEY (schema_name, table_name);


--
-- Name: ix_data_quality_check_name; Type: INDEX; Schema: metadata; Owner: raj
--

CREATE INDEX ix_data_quality_check_name ON metadata.data_quality USING btree (check_name, checked_at);


--
-- Name: ix_doc_embeddings_source; Type: INDEX; Schema: metadata; Owner: raj
--

CREATE INDEX ix_doc_embeddings_source ON metadata.doc_embeddings USING btree (source_type, source_ref);


--
-- Name: ix_etl_runs_job_name; Type: INDEX; Schema: metadata; Owner: raj
--

CREATE INDEX ix_etl_runs_job_name ON metadata.etl_runs USING btree (job_name, started_at);


--
-- Name: SCHEMA metadata; Type: ACL; Schema: -; Owner: raj
--

GRANT USAGE ON SCHEMA metadata TO mcp_reader;


--
-- Name: TABLE audit; Type: ACL; Schema: metadata; Owner: raj
--

GRANT SELECT ON TABLE metadata.audit TO mcp_reader;


--
-- Name: TABLE columns; Type: ACL; Schema: metadata; Owner: raj
--

GRANT SELECT ON TABLE metadata.columns TO mcp_reader;


--
-- Name: TABLE data_quality; Type: ACL; Schema: metadata; Owner: raj
--

GRANT SELECT ON TABLE metadata.data_quality TO mcp_reader;


--
-- Name: TABLE doc_embeddings; Type: ACL; Schema: metadata; Owner: raj
--

GRANT SELECT ON TABLE metadata.doc_embeddings TO mcp_reader;


--
-- Name: TABLE etl_runs; Type: ACL; Schema: metadata; Owner: raj
--

GRANT SELECT ON TABLE metadata.etl_runs TO mcp_reader;


--
-- Name: TABLE lineage; Type: ACL; Schema: metadata; Owner: raj
--

GRANT SELECT ON TABLE metadata.lineage TO mcp_reader;


--
-- Name: TABLE scheduler; Type: ACL; Schema: metadata; Owner: raj
--

GRANT SELECT ON TABLE metadata.scheduler TO mcp_reader;


--
-- Name: TABLE tables; Type: ACL; Schema: metadata; Owner: raj
--

GRANT SELECT ON TABLE metadata.tables TO mcp_reader;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: metadata; Owner: raj
--

ALTER DEFAULT PRIVILEGES FOR ROLE raj IN SCHEMA metadata GRANT SELECT ON TABLES TO mcp_reader;


--
-- PostgreSQL database dump complete
--

\unrestrict 0eJmTTTsKLxgpLtHgDK19spgLM6gbLOXreXMYXPuiEAae93zldst7lMa64eDinv

