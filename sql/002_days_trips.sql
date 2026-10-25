-- =====================================================================
-- 002_days_trips.sql : Phase 2 tables (days, trips, trip rows)
-- Run once in Supabase -> SQL Editor (after 001_profiles.sql).
-- =====================================================================

-- ---------- Days: one record per calendar date ----------
CREATE TABLE days (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    day_date   DATE NOT NULL UNIQUE,
    status     TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);

-- ---------- Trips: one truck + one farm owner + one driver + one day ----------
-- trip_no (T-0001, T-0002 ...) is made by the database from the id.
CREATE TABLE trips (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    trip_no       TEXT GENERATED ALWAYS AS (
                      'T-' || CASE WHEN id < 10000 THEN lpad(id::text, 4, '0') ELSE id::text END
                  ) STORED UNIQUE,
    day_id        BIGINT NOT NULL REFERENCES days(id),
    vehicle_id    BIGINT NOT NULL REFERENCES vehicles(id),
    farm_owner_id BIGINT NOT NULL REFERENCES farm_owners(id),
    driver_id     BIGINT NOT NULL REFERENCES drivers(id),
    status        TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'sold_out', 'settled')),
    note          TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted    BOOLEAN NOT NULL DEFAULT FALSE
);

-- ---------- Trip rows: one vegetable inside a trip ----------
CREATE TABLE trip_rows (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    trip_id       BIGINT NOT NULL REFERENCES trips(id),
    vegetable_id  BIGINT NOT NULL REFERENCES vegetables(id),
    arrived_qty   INTEGER NOT NULL CHECK (arrived_qty >= 0),    -- whole cartons
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted    BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX idx_trips_day        ON trips(day_id);
CREATE INDEX idx_trips_farm_owner ON trips(farm_owner_id);
CREATE INDEX idx_trips_vehicle    ON trips(vehicle_id);
CREATE INDEX idx_trips_driver     ON trips(driver_id);
CREATE INDEX idx_trip_rows_trip   ON trip_rows(trip_id);
CREATE INDEX idx_trip_rows_veg    ON trip_rows(vegetable_id);

-- Auto "last changed" + lock the public API (same as Phase 1)
DO $$
DECLARE t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY['days','trips','trip_rows'] LOOP
    EXECUTE format('CREATE TRIGGER trg_%s_updated BEFORE UPDATE ON %I
                    FOR EACH ROW EXECUTE FUNCTION set_updated_at()', t, t);
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
  END LOOP;
END $$;
