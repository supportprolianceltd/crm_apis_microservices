#!/bin/bash
set -e

# This script initializes the PostgreSQL database with PostGIS extension
echo "Initializing PostgreSQL database with PostGIS..."

# Enable PostGIS extension
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS postgis;
    CREATE EXTENSION IF NOT EXISTS postgis_topology;
    CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;
    CREATE EXTENSION IF NOT EXISTS postgis_tiger_geocoder;
    
    -- Grant necessary permissions
    GRANT ALL PRIVILEGES ON DATABASE $POSTGRES_DB TO $POSTGRES_USER;
    
    -- Create a few utility functions
    CREATE OR REPLACE FUNCTION public.st_distance_meters(geog1 geography, geog2 geography)
    RETURNS double precision
    AS \$\$
    BEGIN
        RETURN ST_Distance(geog1, geog2);
    END;
    \$\$ LANGUAGE plpgsql IMMUTABLE;
    
    -- Log initialization
    \echo 'PostGIS extensions and utility functions created successfully';
EOSQL

echo "Database initialization completed successfully!"