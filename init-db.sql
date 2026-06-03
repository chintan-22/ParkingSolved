-- Initialize parking database schema

-- Create tables
CREATE TABLE IF NOT EXISTS parking_lots (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    address VARCHAR(500) NOT NULL,
    latitude DECIMAL(10, 8) NOT NULL,
    longitude DECIMAL(11, 8) NOT NULL,
    total_capacity INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(latitude, longitude)
);

CREATE TABLE IF NOT EXISTS occupancy_events (
    id SERIAL PRIMARY KEY,
    lot_id INTEGER NOT NULL REFERENCES parking_lots(id) ON DELETE CASCADE,
    event_type VARCHAR(20) NOT NULL CHECK (event_type IN ('entry', 'exit')),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS occupancy_snapshots (
    id SERIAL PRIMARY KEY,
    lot_id INTEGER NOT NULL REFERENCES parking_lots(id) ON DELETE CASCADE,
    occupied_count INTEGER NOT NULL,
    snapshot_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_occupancy_events_lot_id ON occupancy_events(lot_id);
CREATE INDEX IF NOT EXISTS idx_occupancy_events_timestamp ON occupancy_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_occupancy_snapshots_lot_id ON occupancy_snapshots(lot_id);
CREATE INDEX IF NOT EXISTS idx_occupancy_snapshots_snapshot_time ON occupancy_snapshots(snapshot_time);
