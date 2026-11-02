-- =====================================================================
-- 006_returns.sql : Phase 5 table (customer returns)
-- Run once in Supabase -> SQL Editor. Run it BEFORE deploying the new code.
-- =====================================================================

-- A return belongs to a sale line. The cartons go back into the SAME trip row,
-- into the vehicle chosen in back_to_vehicle_id.
CREATE TABLE sale_returns (
    id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sale_line_id       BIGINT NOT NULL REFERENCES sale_lines(id),
    qty                INTEGER NOT NULL CHECK (qty > 0),
    credit_rate        NUMERIC(12,2) NOT NULL CHECK (credit_rate >= 0),
    back_to_vehicle_id BIGINT NOT NULL REFERENCES vehicles(id),
    return_date        DATE NOT NULL,
    note               TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted         BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX idx_returns_line    ON sale_returns(sale_line_id);
CREATE INDEX idx_returns_vehicle ON sale_returns(back_to_vehicle_id);

-- Auto "last changed" + lock the public API (same as before)
CREATE TRIGGER trg_sale_returns_updated BEFORE UPDATE ON sale_returns
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
ALTER TABLE sale_returns ENABLE ROW LEVEL SECURITY;
