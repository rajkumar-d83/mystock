-- Read-only role for the MCP server. Originally excluded `portfolio` (real
-- holdings/trades) from its grants; widened on 2026-08-06 to include it
-- (single-user personal data, no other users on this system).

DO $$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'mcp_reader') THEN
      CREATE ROLE mcp_reader WITH LOGIN PASSWORD 'mcp_reader_local_dev';
   END IF;
END
$$;

GRANT USAGE ON SCHEMA staging, main, metadata, portfolio TO mcp_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA staging, main, metadata, portfolio TO mcp_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA staging, main, metadata, portfolio GRANT SELECT ON TABLES TO mcp_reader;
