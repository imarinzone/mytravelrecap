-- Travel Recap Database Schema
-- This file is automatically executed by Postgres when the container first starts
-- (mounted to /docker-entrypoint-initdb.d via docker-compose.yaml)

-- Place Locations Cache Table
-- Stores geocoded location data keyed by Google place_id to avoid re-geocoding
CREATE TABLE IF NOT EXISTS place_locations (
    place_id TEXT PRIMARY KEY,
    lat DOUBLE PRECISION NOT NULL,
    lng DOUBLE PRECISION NOT NULL,
    city TEXT,
    state TEXT,
    country TEXT,
    address TEXT,
    geocoded_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for place_locations
CREATE INDEX IF NOT EXISTS idx_place_locations_lat_lng ON place_locations(lat, lng);
CREATE INDEX IF NOT EXISTS idx_place_locations_city_country ON place_locations(city, country);

-- Visits Table
-- Stores visit data extracted from GoogleTimeline.json semantic segments
-- Location data (city, state, country, address) is stored in place_locations table
-- and accessed via place_id foreign key relationship
CREATE TABLE IF NOT EXISTS visits (
    id BIGSERIAL PRIMARY KEY,
    start_time TIMESTAMPTZ NOT NULL,
    lat DOUBLE PRECISION NOT NULL,
    lng DOUBLE PRECISION NOT NULL,
    probability DOUBLE PRECISION NOT NULL,
    place_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT fk_visits_place_id 
        FOREIGN KEY (place_id) REFERENCES place_locations(place_id) ON DELETE SET NULL
);

-- Indexes for visits
CREATE INDEX IF NOT EXISTS idx_visits_start_time ON visits(start_time);
CREATE INDEX IF NOT EXISTS idx_visits_location ON visits(lat, lng);
CREATE INDEX IF NOT EXISTS idx_visits_place_id ON visits(place_id);

