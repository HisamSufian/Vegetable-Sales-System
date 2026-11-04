-- =====================================================================
-- 007_farm_money.sql : Phase 6 tables (settlement, extra costs, payments, opening balances)
-- Run once in Supabase -> SQL Editor. Run it BEFORE deploying the new code.
-- =====================================================================

-- ---------- Settlement lines: what I owe the farm owner for cartons of a trip row ----------
-- The rate is my own decision and has nothing to do with the selling rate.
CREATE TABLE settlement_lines (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    trip_row_id BIGINT NOT NULL REFERENCES trip_rows(id),
    qty         INTEGER NOT NULL CHECK (qty > 0),
    rate        NUMERIC(12,2) NOT NULL CHECK (rate >= 0),
    line_date   DATE NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted  BOOLEAN NOT NULL DEFAULT FALSE
);

-- ---------- Extra costs on a farm owner ----------
-- borne_by 'farm_owner' = deducted from his balance; 'me' = my own business expense.
CREATE TABLE farm_owner_costs (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    farm_owner_id BIGINT NOT NULL REFERENCES farm_owners(id),
    trip_id       BIGINT REFERENCES trips(id),          -- optional link to a trip
    amount        NUMERIC(12,2) NOT NULL CHECK (amount > 0),
    borne_by      TEXT NOT NULL CHECK (borne_by IN ('farm_owner', 'me')),
    cost_date     DATE NOT NULL,
    note          TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted    BOOLEAN NOT NULL DEFAULT FALSE
);

-- ---------- Payments to a farm owner (against the owner overall, not a trip) ----------
-- Cash / bank / other count immediately. A cheque counts only once its status is 'cleared'.
CREATE TABLE farm_owner_payments (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    farm_owner_id BIGINT NOT NULL REFERENCES farm_owners(id),
    amount        NUMERIC(12,2) NOT NULL CHECK (amount > 0),
    method        TEXT NOT NULL CHECK (method IN ('cash', 'bank', 'cheque', 'other')),
    pay_date      DATE NOT NULL,
    note          TEXT,
    cheque_no     TEXT,
    bank          TEXT,
    due_date      DATE,
    cheque_status TEXT CHECK (cheque_status IN ('pending', 'cleared', 'bounced')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted    BOOLEAN NOT NULL DEFAULT FALSE,
    CHECK (
        (method = 'cheque' AND cheque_no IS NOT NULL AND due_date IS NOT NULL AND cheque_status IS NOT NULL)
        OR
        (method <> 'cheque' AND cheque_no IS NULL AND bank IS NULL AND due_date IS NULL AND cheque_status IS NULL)
    )
);

-- ---------- Opening balances (old debts) for a farm owner OR a customer ----------
-- Farm owner: positive = I owe him, negative = he owes me.
-- Customer (Phase 7): positive = he owes me.
CREATE TABLE opening_balances (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    party_type    TEXT NOT NULL CHECK (party_type IN ('farm_owner', 'customer')),
    farm_owner_id BIGINT REFERENCES farm_owners(id),
    customer_id   BIGINT REFERENCES customers(id),
    amount        NUMERIC(12,2) NOT NULL CHECK (amount <> 0),
    balance_date  DATE NOT NULL,
    note          TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted    BOOLEAN NOT NULL DEFAULT FALSE,
    CHECK (
        (party_type = 'farm_owner' AND farm_owner_id IS NOT NULL AND customer_id IS NULL)
        OR
        (party_type = 'customer' AND customer_id IS NOT NULL AND farm_owner_id IS NULL)
    )
);

CREATE INDEX idx_settlement_row     ON settlement_lines(trip_row_id);
CREATE INDEX idx_costs_owner        ON farm_owner_costs(farm_owner_id);
CREATE INDEX idx_costs_trip         ON farm_owner_costs(trip_id);
CREATE INDEX idx_fpay_owner         ON farm_owner_payments(farm_owner_id);
CREATE INDEX idx_opening_owner      ON opening_balances(farm_owner_id);
CREATE INDEX idx_opening_customer   ON opening_balances(customer_id);

-- Auto "last changed" + lock the public API (same as before)
DO $$
DECLARE t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY['settlement_lines','farm_owner_costs','farm_owner_payments','opening_balances'] LOOP
    EXECUTE format('CREATE TRIGGER trg_%s_updated BEFORE UPDATE ON %I
                    FOR EACH ROW EXECUTE FUNCTION set_updated_at()', t, t);
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
  END LOOP;
END $$;
