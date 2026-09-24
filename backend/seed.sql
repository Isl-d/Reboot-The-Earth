-- Seeding is done from data/*.csv by backend/db.py so that the CSV files stay
-- the single source of truth (they carry a `source` column saying whether a
-- number is real open data or an approximation). This file only clears the
-- tables that are rebuilt on every start.
TRUNCATE TABLE readings;
TRUNCATE TABLE events RESTART IDENTITY;
TRUNCATE TABLE decisions;
TRUNCATE TABLE shipments;
