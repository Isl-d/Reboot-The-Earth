-- ColdGuard schema (CLAUDE.md section 6). PostgreSQL 16.
-- TimescaleDB is optional: if the extension is present, `readings` becomes a
-- hypertable, otherwise a plain table with an index is fine for a 48 h demo.

CREATE TABLE IF NOT EXISTS products (
    product                  TEXT PRIMARY KEY,
    ideal_temp_c             REAL NOT NULL,
    life_at_ideal_days       REAL NOT NULL,
    q10                      REAL NOT NULL,
    alert_limit_c            REAL NOT NULL,
    min_life_on_arrival_days REAL NOT NULL,
    value_qar_per_kg         REAL NOT NULL,
    source_note              TEXT
);

CREATE TABLE IF NOT EXISTS places (
    place_id      TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    type          TEXT NOT NULL,
    lat           DOUBLE PRECISION NOT NULL,
    lon           DOUBLE PRECISION NOT NULL,
    has_cold_room BOOLEAN NOT NULL DEFAULT FALSE,
    source        TEXT
);

CREATE TABLE IF NOT EXISTS shipments (
    truck_id             TEXT PRIMARY KEY,
    product              TEXT REFERENCES products(product),
    qty_kg               REAL NOT NULL,
    route_id             TEXT NOT NULL,
    destination_place_id TEXT REFERENCES places(place_id),
    eta                  TIMESTAMPTZ,
    life_left_h          REAL,
    status               TEXT NOT NULL DEFAULT 'rolling'
);

CREATE TABLE IF NOT EXISTS readings (
    ts        TIMESTAMPTZ NOT NULL,
    truck_id  TEXT NOT NULL,
    air_c     REAL,
    hum_pct   REAL,
    door_open BOOLEAN,
    lat       DOUBLE PRECISION,
    lon       DOUBLE PRECISION,
    src       TEXT
);
CREATE INDEX IF NOT EXISTS readings_truck_ts ON readings (truck_id, ts DESC);

CREATE TABLE IF NOT EXISTS events (
    id         BIGSERIAL PRIMARY KEY,
    truck_id   TEXT NOT NULL,
    type       TEXT NOT NULL,          -- door | defrost | sensor_fault | failure
    started_at TIMESTAMPTZ NOT NULL,
    ended_at   TIMESTAMPTZ,
    peak_c     REAL,
    note       TEXT
);
CREATE INDEX IF NOT EXISTS events_truck ON events (truck_id, started_at DESC);

CREATE TABLE IF NOT EXISTS decisions (
    decision_id TEXT PRIMARY KEY,
    truck_id    TEXT NOT NULL,
    product     TEXT,
    qty_kg      REAL,
    options     JSONB NOT NULL,        -- every option A-D with its numbers
    facts       JSONB NOT NULL,        -- the JSON handed to the agent
    chosen      TEXT,
    text_en     TEXT,
    text_ar     TEXT,
    text_source TEXT,                  -- qwen2.5:7b or template
    created_at  TIMESTAMPTZ NOT NULL,
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    prev_hash   TEXT NOT NULL,
    hash        TEXT NOT NULL
);
