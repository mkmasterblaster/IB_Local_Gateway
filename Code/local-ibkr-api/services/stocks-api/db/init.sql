-- Database Initialization Script for IBKR Local API
-- This script sets up the initial database schema

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For text search optimization

-- Set timezone
SET timezone = 'America/New_York';

-- Create custom types
CREATE TYPE order_status AS ENUM (
    'pending',
    'submitted',
    'filled',
    'partial_fill',
    'cancelled',
    'rejected',
    'expired'
);

CREATE TYPE order_type AS ENUM (
    'market',
    'limit',
    'stop',
    'stop_limit',
    'trailing_stop'
);

CREATE TYPE order_action AS ENUM (
    'buy',
    'sell'
);

-- Create audit trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE stocks_db TO stocks_user;
GRANT ALL PRIVILEGES ON SCHEMA public TO stocks_user;

-- Create initial admin comment
COMMENT ON DATABASE stocks_db IS 'IBKR Local API - Paper Trading Database';
