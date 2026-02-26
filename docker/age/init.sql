-- Apache AGE Initialization Script for Digital CTO Knowledge Graph
-- This script is run when the postgres-with-age container starts
-- Using apache/age:PG16_latest image which has AGE preloaded via shared_preload_libraries

CREATE EXTENSION IF NOT EXISTS age;

-- Grant usage on ag_catalog to the cto user
GRANT USAGE ON SCHEMA ag_catalog TO cto;

-- Create the knowledge graph
-- This creates the graph and its associated tables
SELECT ag_catalog.create_graph('afcen_knowledge');

-- Grant permissions on the graph tables
GRANT ALL ON ALL TABLES IN SCHEMA ag_catalog TO cto;
GRANT ALL ON ALL SEQUENCES IN SCHEMA ag_catalog TO cto;

-- Log initialization
DO $$
BEGIN
    RAISE NOTICE 'Apache AGE knowledge graph "afcen_knowledge" initialized';
END $$;
