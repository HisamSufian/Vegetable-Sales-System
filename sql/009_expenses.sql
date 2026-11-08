-- =====================================================================
-- 009_expenses.sql : Phase 8 table (general expenses)
-- Run once in Supabase -> SQL Editor. Run it BEFORE deploying the new code.
-- =====================================================================

-- General business expenses (delivery, labour, ...). No categories: just a note.
-- Optionally linked to a trip, so trip profit can include it.
CREATE TABLE expenses (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    expense_date DATE NOT NULL,
    amount       NUMERIC(12,2) NOT NULL CHECK (amount > 0),
    note         TEXT,
    trip_id      BIGINT REFERENCES trips(id),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted   BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX idx_expenses_date ON expenses(expense_date);
CREATE INDEX idx_expenses_trip ON expenses(trip_id);

-- Auto "last changed" + lock the public API (same as before)
CREATE TRIGGER trg_expenses_updated BEFORE UPDATE ON expenses
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
ALTER TABLE expenses ENABLE ROW LEVEL SECURITY;
