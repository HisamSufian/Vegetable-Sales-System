-- =====================================================================
-- 005_stock.sql : Phase 4 tables (stock moves, wastage, corrections)
-- Run once in Supabase -> SQL Editor. Run it BEFORE deploying the new code.
-- Note: wastage and corrections also record WHICH VEHICLE the cartons were in
-- (a small addition to the PDF's list) so per-vehicle stock always adds up.
-- =====================================================================

-- ---------- Moving cartons from one vehicle to another ----------
CREATE TABLE stock_moves (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    trip_row_id     BIGINT NOT NULL REFERENCES trip_rows(id),
    from_vehicle_id BIGINT NOT NULL REFERENCES vehicles(id),
    to_vehicle_id   BIGINT NOT NULL REFERENCES vehicles(id),
    qty             INTEGER NOT NULL CHECK (qty > 0),
    move_date       DATE NOT NULL,
    note            TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted      BOOLEAN NOT NULL DEFAULT FALSE,
    CHECK (from_vehicle_id <> to_vehicle_id)
);

-- ---------- Wastage / loss (reduces stock, not paid to the farm owner) ----------
CREATE TABLE wastage (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    trip_row_id BIGINT NOT NULL REFERENCES trip_rows(id),
    vehicle_id  BIGINT NOT NULL REFERENCES vehicles(id),
    qty         INTEGER NOT NULL CHECK (qty > 0),
    waste_date  DATE NOT NULL,
    note        TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted  BOOLEAN NOT NULL DEFAULT FALSE
);

-- ---------- Stock corrections (+ or - cartons, a reason is required) ----------
CREATE TABLE stock_corrections (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    trip_row_id     BIGINT NOT NULL REFERENCES trip_rows(id),
    vehicle_id      BIGINT NOT NULL REFERENCES vehicles(id),
    qty_change      INTEGER NOT NULL CHECK (qty_change <> 0),
    correction_date DATE NOT NULL,
    reason          TEXT NOT NULL CHECK (btrim(reason) <> ''),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted      BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX idx_moves_row        ON stock_moves(trip_row_id);
CREATE INDEX idx_moves_from       ON stock_moves(from_vehicle_id);
CREATE INDEX idx_moves_to         ON stock_moves(to_vehicle_id);
CREATE INDEX idx_wastage_row      ON wastage(trip_row_id);
CREATE INDEX idx_wastage_vehicle  ON wastage(vehicle_id);
CREATE INDEX idx_corrections_row  ON stock_corrections(trip_row_id);
CREATE INDEX idx_corrections_veh  ON stock_corrections(vehicle_id);

-- Auto "last changed" + lock the public API (same as before)
DO $$
DECLARE t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY['stock_moves','wastage','stock_corrections'] LOOP
    EXECUTE format('CREATE TRIGGER trg_%s_updated BEFORE UPDATE ON %I
                    FOR EACH ROW EXECUTE FUNCTION set_updated_at()', t, t);
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
  END LOOP;
END $$;
