-- =====================================================================
-- 004_sales.sql : Phase 3 tables (sale bills and sale lines)
-- Run once in Supabase -> SQL Editor. Run it BEFORE deploying the new code.
-- =====================================================================

-- ---------- Sale bills: one bill per customer per Day ----------
-- bill_no (B-0001, B-0002 ...) is made by the database from the id.
CREATE TABLE sale_bills (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    bill_no         TEXT GENERATED ALWAYS AS (
                        'B-' || CASE WHEN id < 10000 THEN lpad(id::text, 4, '0') ELSE id::text END
                    ) STORED UNIQUE,
    day_id          BIGINT NOT NULL REFERENCES days(id),
    customer_id     BIGINT NOT NULL REFERENCES customers(id),
    discount_amount NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
    note            TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted      BOOLEAN NOT NULL DEFAULT FALSE
);
-- the rule "one bill per customer per Day", enforced by the database
CREATE UNIQUE INDEX uq_one_bill_per_customer_day
    ON sale_bills (day_id, customer_id) WHERE is_deleted = false;

-- ---------- Sale lines ----------
-- rate may be empty (NULL) = "Rate pending". Cartons are whole numbers.
CREATE TABLE sale_lines (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    bill_id         BIGINT NOT NULL REFERENCES sale_bills(id),
    trip_row_id     BIGINT NOT NULL REFERENCES trip_rows(id),
    from_vehicle_id BIGINT NOT NULL REFERENCES vehicles(id),   -- where the cartons were taken from
    qty             INTEGER NOT NULL CHECK (qty > 0),
    rate            NUMERIC(12,2) CHECK (rate IS NULL OR rate >= 0),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted      BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX idx_sale_bills_day      ON sale_bills(day_id);
CREATE INDEX idx_sale_bills_customer ON sale_bills(customer_id);
CREATE INDEX idx_sale_lines_bill     ON sale_lines(bill_id);
CREATE INDEX idx_sale_lines_row      ON sale_lines(trip_row_id);
CREATE INDEX idx_sale_lines_vehicle  ON sale_lines(from_vehicle_id);
CREATE INDEX idx_sale_lines_pending  ON sale_lines(id) WHERE rate IS NULL AND is_deleted = false;

-- Auto "last changed" + lock the public API (same as before)
DO $$
DECLARE t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY['sale_bills','sale_lines'] LOOP
    EXECUTE format('CREATE TRIGGER trg_%s_updated BEFORE UPDATE ON %I
                    FOR EACH ROW EXECUTE FUNCTION set_updated_at()', t, t);
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
  END LOOP;
END $$;
