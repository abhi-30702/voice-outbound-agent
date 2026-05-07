-- scripts/grants.sql
-- PostgreSQL permissions for memories_role (LLM read-only access)
-- Apply AFTER migration 001_initial_schema.py

-- Create role if not exists
CREATE ROLE IF NOT EXISTS memories_role;

-- Grant schema usage
GRANT USAGE ON SCHEMA agent_operations TO memories_role;

-- Grant table permissions (SELECT, INSERT, UPDATE only)
GRANT SELECT, INSERT, UPDATE ON agent_operations.campaigns TO memories_role;
GRANT SELECT, INSERT, UPDATE ON agent_operations.leads TO memories_role;
GRANT SELECT, INSERT, UPDATE ON agent_operations.call_logs TO memories_role;
GRANT SELECT, INSERT ON agent_operations.call_transcripts TO memories_role;
GRANT SELECT ON agent_operations.dnc_registry TO memories_role;

-- Grant sequence permissions for UUID generation
GRANT USAGE ON ALL SEQUENCES IN SCHEMA agent_operations TO memories_role;

-- No DELETE, DROP, CREATE, or schema ownership granted
-- This enforces least-privilege access for LLM operations
