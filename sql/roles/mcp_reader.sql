-- Read-only role for the MCP server. Originally excluded `portfolio` (real
-- holdings/trades) from its grants; widened on 2026-08-06 to include it
-- (single-user personal data, no other users on this system).
--
-- Password comes from the MCP_PGPASSWORD environment variable, never
-- hardcoded here. Run as:
--   MCP_PGPASSWORD='...' psql -U raj -d mystock -f sql/roles/mcp_reader.sql

\getenv mcp_reader_password MCP_PGPASSWORD
\if :{?mcp_reader_password}
\else
  \echo 'ERROR: set MCP_PGPASSWORD before running this script'
  \quit
\endif

DO $$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'mcp_reader') THEN
      CREATE ROLE mcp_reader WITH LOGIN;
   END IF;
END
$$;

ALTER ROLE mcp_reader WITH PASSWORD :'mcp_reader_password';

GRANT USAGE ON SCHEMA staging, main, metadata, portfolio TO mcp_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA staging, main, metadata, portfolio TO mcp_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA staging, main, metadata, portfolio GRANT SELECT ON TABLES TO mcp_reader;
