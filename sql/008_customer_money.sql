-- =====================================================================
-- 008_customer_money.sql : Phase 7 tables (customer payments and write-offs)
-- Run once in Supabase -> SQL Editor. Run it BEFORE deploying the new code.
-- (Customer opening balances use the opening_balances table from Phase 6.)
-- =====================================================================

-- ---------- Customer payments (against the customer's TOTAL balance, not a bill) ----------
-- Cash / bank / other count immediately. A cheque counts only once it is 'cleared'.
-- A pending post-dated cheque is "Cheques in hand"; a bounced one is back in the balance.
CREATE TABLE customer_payments (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id   BIGINT NOT NULL REFERENCES customers(id),
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

-- ---------- Write-offs / adjustments ----------
-- Reduce what the customer owes. Not money received; counted as a loss in profit (Phase 8).
CREATE TABLE customer_adjustments (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id BIGINT NOT NULL REFERENCES customers(id),
    amount      NUMERIC(12,2) NOT NULL CHECK (amount > 0),
    reason      TEXT NOT NULL CHECK (btrim(reason) <> ''),
    adj_date    DATE NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted  BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX idx_cpay_customer    ON customer_payments(customer_id);
CREATE INDEX idx_cpay_due         ON customer_payments(due_date) WHERE method = 'cheque' AND is_deleted = false;
CREATE INDEX idx_cadj_customer    ON customer_adjustments(customer_id);

-- Auto "last changed" + lock the public API (same as before)
DO $$
DECLARE t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY['customer_payments','customer_adjustments'] LOOP
    EXECUTE format('CREATE TRIGGER trg_%s_updated BEFORE UPDATE ON %I
                    FOR EACH ROW EXECUTE FUNCTION set_updated_at()', t, t);
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
  END LOOP;
END $$;
