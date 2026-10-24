-- =====================================================================
-- 001_profiles.sql : Phase 1 tables (settings + the five profile types)
-- Run once in Supabase -> SQL Editor (after 000_reset.sql).
-- Every table has: id, created_at, updated_at, is_deleted (hidden).
-- =====================================================================

-- Keeps "last changed" correct automatically, whatever code changes a row
CREATE FUNCTION set_updated_at() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

-- ---------- Settings (always exactly one row, id = 1) ----------
CREATE TABLE settings (
    id               INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    business_name    TEXT NOT NULL DEFAULT '',
    business_phone   TEXT NOT NULL DEFAULT '',
    statement_footer TEXT NOT NULL DEFAULT '',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted       BOOLEAN NOT NULL DEFAULT FALSE
);
INSERT INTO settings (id) VALUES (1);

-- ---------- Farm owners ----------
CREATE TABLE farm_owners (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name          TEXT NOT NULL CHECK (btrim(name) <> ''),
    phone         TEXT,
    email         TEXT,
    farm_location TEXT,
    notes         TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted    BOOLEAN NOT NULL DEFAULT FALSE
);

-- ---------- Customers (includes the built-in Walk-in / Cash) ----------
CREATE TABLE customers (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name          TEXT NOT NULL CHECK (btrim(name) <> ''),
    phone         TEXT,
    shop_no       TEXT,
    shop_location TEXT,
    notes         TEXT,
    is_walk_in    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted    BOOLEAN NOT NULL DEFAULT FALSE,
    CHECK (NOT (is_walk_in AND is_deleted))          -- Walk-in can never be hidden
);
CREATE UNIQUE INDEX uq_one_walk_in ON customers (is_walk_in) WHERE is_walk_in;   -- only one
INSERT INTO customers (name, is_walk_in) VALUES ('Walk-in / Cash', TRUE);

-- ---------- Drivers ----------
CREATE TABLE drivers (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name       TEXT NOT NULL CHECK (btrim(name) <> ''),
    phone      TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);

-- ---------- Vehicles (just a plate number) ----------
CREATE TABLE vehicles (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    plate_number TEXT NOT NULL CHECK (btrim(plate_number) <> ''),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted   BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE UNIQUE INDEX uq_vehicles_plate ON vehicles (lower(plate_number));

-- ---------- Vegetables ----------
CREATE TABLE vegetables (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name       TEXT NOT NULL CHECK (btrim(name) <> ''),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE UNIQUE INDEX uq_vegetables_name ON vegetables (lower(name));

-- ---------- For every table: auto "last changed" + lock the public API ----------
-- (Row Level Security with no policies blocks Supabase's public Data API.
--  Our app connects directly with the database password, so it is unaffected.)
DO $$
DECLARE t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY['settings','farm_owners','customers','drivers','vehicles','vegetables'] LOOP
    EXECUTE format('CREATE TRIGGER trg_%s_updated BEFORE UPDATE ON %I
                    FOR EACH ROW EXECUTE FUNCTION set_updated_at()', t, t);
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
  END LOOP;
END $$;
