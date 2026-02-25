-- Apache AGE Initialization Script for Digital CTO Knowledge Graph
-- This script is run when the postgres-with-age container starts

-- Install Apache AGE extension (must be pre-loaded in Bitnami image)
-- If using standard postgres, AGE must be installed via apt first
-- For Bitnami postgresql with AGE support, the extension is already available

CREATE EXTENSION IF NOT EXISTS age;

-- Load the extension
LOAD 'age';

-- Grant usage on ag_catalog to the cto user
GRANT USAGE ON SCHEMA ag_catalog TO cto;

-- Create the knowledge graph
-- This creates the graph and its associated tables
SELECT ag_catalog.create_graph('afcen_knowledge');

-- Grant permissions on the graph tables
GRANT ALL ON ALL TABLES IN SCHEMA ag_catalog TO cto;
GRANT ALL ON ALL SEQUENCES IN SCHEMA ag_catalog TO cto;

-- Create indexes for common queries (will be updated as graph grows)
-- These indexes will be created on graph vertex/label tables as needed

-- Log initialization
DO $$
BEGIN
    RAISE NOTICE 'Apache AGE knowledge graph "afcen_knowledge" initialized';
END $$;
