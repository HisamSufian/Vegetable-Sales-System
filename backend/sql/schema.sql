-- =====================================================================
-- AL AWEER PRODUCE SYSTEM - DATABASE SCHEMA (PostgreSQL / Supabase)
-- Run this whole file once in Supabase -> SQL Editor.
-- Money = NUMERIC(12,2). Quantities = whole cartons (INTEGER).
-- =====================================================================

-- ---------- 1. ENUM TYPES (fixed lists of allowed values) ------------
CREATE TYPE buyer_type          AS ENUM ('LOCAL_SELLER', 'CONSUMER');
CREATE TYPE consignment_status  AS ENUM ('ARRIVED', 'VERIFIED', 'CLOSED');
CREATE TYPE sale_payment_method AS ENUM ('CASH', 'CREDIT');
CREATE TYPE ledger_entry_type   AS ENUM ('INVOICE', 'PAYMENT');
CREATE TYPE payment_mode        AS ENUM ('CASH', 'BANK_TRANSFER', 'CHEQUE', 'PDC');
CREATE TYPE pdc_status          AS ENUM ('PENDING', 'CLEARED', 'BOUNCED');
CREATE TYPE settlement_status   AS ENUM ('DRAFT', 'FINAL');
CREATE TYPE expense_type        AS ENUM ('FARM_DEDUCTIBLE', 'INTERNAL');
CREATE TYPE expense_category    AS ENUM (
    -- farm-deductible
    'DRIVER_ADVANCE', 'PACKAGING_CARTONS', 'EXTRA_DAY_FEE', 'CUSTOM_FARM_DEDUCTION',
    -- internal
    'PARKING', 'UNLOADING_LABOR', 'DELIVERY_LABOR', 'CUSTOM_INTERNAL'
);

-- ---------- 2. MASTER TABLES -----------------------------------------
CREATE TABLE farm_owners (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name          TEXT NOT NULL,
    contact_phone TEXT,
    default_margin_per_carton NUMERIC(12,2) CHECK (default_margin_per_carton >= 0),
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE drivers_trucks (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    plate_number TEXT NOT NULL UNIQUE,
    driver_name  TEXT NOT NULL,
    driver_phone TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE vegetables (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE,
    category   TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Company-owned vehicles used as virtual storage for leftover stock
CREATE TABLE company_vehicles (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    plate_number TEXT NOT NULL UNIQUE,
    label        TEXT,
    is_active    BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE buyers (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name         TEXT NOT NULL,
    phone        TEXT,
    buyer_type   buyer_type NOT NULL DEFAULT 'LOCAL_SELLER',
    credit_limit NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (credit_limit >= 0),
    is_active    BOOLEAN NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- 3. INBOUND CONSIGNMENTS (one truck = one farm owner) -----
CREATE TABLE consignments (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    farm_owner_id    BIGINT NOT NULL REFERENCES farm_owners(id),
    driver_truck_id  BIGINT NOT NULL REFERENCES drivers_trucks(id),
    arrival_date     DATE NOT NULL DEFAULT CURRENT_DATE,
    status           consignment_status NOT NULL DEFAULT 'ARRIVED',
    verified_by      TEXT,
    notes            TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Dual verification: farm dispatch count vs. count at market entry
CREATE TABLE consignment_items (
    id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    consignment_id     BIGINT NOT NULL REFERENCES consignments(id) ON DELETE CASCADE,
    vegetable_id       BIGINT NOT NULL REFERENCES vegetables(id),
    dispatched_cartons INTEGER NOT NULL CHECK (dispatched_cartons >= 0),
    unloaded_cartons   INTEGER CHECK (unloaded_cartons >= 0),
    variance_cartons   INTEGER GENERATED ALWAYS AS (unloaded_cartons - dispatched_cartons) STORED,
    UNIQUE (consignment_id, vegetable_id)
);

-- ---------- 4. STOCK ON HAND + VIRTUAL TRANSFERS ----------------------
-- Where each batch physically is right now.
-- company_vehicle_id NULL  = still on the original driver's truck.
-- Batch (consignment_item) keeps its farm owner no matter where it moves.
CREATE TABLE item_stock (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    consignment_item_id BIGINT NOT NULL REFERENCES consignment_items(id),
    company_vehicle_id  BIGINT REFERENCES company_vehicles(id),
    cartons_on_hand     INTEGER NOT NULL DEFAULT 0 CHECK (cartons_on_hand >= 0)
);
CREATE UNIQUE INDEX uq_item_stock_location
    ON item_stock (consignment_item_id, COALESCE(company_vehicle_id, 0));

CREATE TABLE inventory_transfers (
    id                    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    consignment_item_id   BIGINT NOT NULL REFERENCES consignment_items(id),
    from_company_vehicle_id BIGINT REFERENCES company_vehicles(id), -- NULL = original truck
    to_company_vehicle_id BIGINT NOT NULL REFERENCES company_vehicles(id),
    cartons               INTEGER NOT NULL CHECK (cartons > 0),
    transferred_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    note                  TEXT,
    CHECK (from_company_vehicle_id IS DISTINCT FROM to_company_vehicle_id)
);

-- ---------- 5. SALES (POS) -------------------------------------------
CREATE TABLE sales_transactions (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    buyer_id       BIGINT REFERENCES buyers(id),          -- NULL allowed only for walk-in cash
    sale_date      TIMESTAMPTZ NOT NULL DEFAULT now(),
    payment_method sale_payment_method NOT NULL,
    total_amount   NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (total_amount >= 0),
    notes          TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (payment_method = 'CASH' OR buyer_id IS NOT NULL)  -- credit needs a known buyer
);

-- Each line says exactly which batch AND which vehicle the cartons came from
CREATE TABLE sale_items (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sale_id             BIGINT NOT NULL REFERENCES sales_transactions(id) ON DELETE CASCADE,
    consignment_item_id BIGINT NOT NULL REFERENCES consignment_items(id),
    item_stock_id       BIGINT NOT NULL REFERENCES item_stock(id),
    cartons             INTEGER NOT NULL CHECK (cartons > 0),
    price_per_carton    NUMERIC(12,2) NOT NULL CHECK (price_per_carton >= 0),
    farm_rate_per_carton NUMERIC(12,2) NOT NULL CHECK (farm_rate_per_carton >= 0), -- what the FARM gets
    line_total          NUMERIC(12,2) GENERATED ALWAYS AS (cartons * price_per_carton) STORED,
    margin_per_carton   NUMERIC(12,2) GENERATED ALWAYS AS (price_per_carton - farm_rate_per_carton) STORED,
    farm_payout         NUMERIC(12,2) GENERATED ALWAYS AS (cartons * farm_rate_per_carton) STORED
);

-- ---------- 6. BUYER LEDGER ------------------------------------------
-- INVOICE increases what the buyer owes; PAYMENT reduces it.
-- A PDC (post-dated cheque) is logged as PENDING and only counts
-- toward the balance once marked CLEARED.
CREATE TABLE buyer_ledger (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    buyer_id       BIGINT NOT NULL REFERENCES buyers(id),
    entry_date     DATE NOT NULL DEFAULT CURRENT_DATE,
    entry_type     ledger_entry_type NOT NULL,
    sale_id        BIGINT REFERENCES sales_transactions(id),   -- for INVOICE rows
    amount         NUMERIC(12,2) NOT NULL CHECK (amount > 0),
    payment_mode   payment_mode,
    cheque_number  TEXT,
    cheque_date    DATE,
    pdc_status     pdc_status,
    reference_note TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (entry_type <> 'INVOICE' OR sale_id IS NOT NULL),
    CHECK (entry_type <> 'PAYMENT' OR payment_mode IS NOT NULL),
    CHECK (payment_mode IS DISTINCT FROM 'PDC' OR (cheque_date IS NOT NULL AND pdc_status IS NOT NULL))
);

-- Which invoice(s) a payment was applied to (specific invoice OR lump sum split oldest-first)
CREATE TABLE buyer_payment_allocations (
    id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    payment_ledger_id BIGINT NOT NULL REFERENCES buyer_ledger(id) ON DELETE CASCADE,
    invoice_ledger_id BIGINT NOT NULL REFERENCES buyer_ledger(id),
    amount            NUMERIC(12,2) NOT NULL CHECK (amount > 0)
);

-- ---------- 7. FARM OWNER SETTLEMENTS & PAYOUTS ----------------------
CREATE TABLE farm_owner_settlements (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    farm_owner_id    BIGINT NOT NULL REFERENCES farm_owners(id),
    settlement_date  DATE NOT NULL,
    cartons_sold     INTEGER NOT NULL DEFAULT 0,
    gross_amount     NUMERIC(12,2) NOT NULL DEFAULT 0,
    total_deductions NUMERIC(12,2) NOT NULL DEFAULT 0,
    net_payout       NUMERIC(12,2) NOT NULL DEFAULT 0,   -- can be negative (farm owes us)
    status           settlement_status NOT NULL DEFAULT 'DRAFT',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (farm_owner_id, settlement_date)
);

-- Partial payments made to farm owners
CREATE TABLE farm_owner_payments (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    farm_owner_id BIGINT NOT NULL REFERENCES farm_owners(id),
    payment_date  DATE NOT NULL DEFAULT CURRENT_DATE,
    amount        NUMERIC(12,2) NOT NULL CHECK (amount > 0),
    mode          payment_mode NOT NULL DEFAULT 'CASH',
    note          TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- 8. EXPENSES (one table, two types) -----------------------
-- FARM_DEDUCTIBLE: reduces the farm owner's payout. Needs farm_owner_id.
--                  settlement_id is filled when it gets deducted, so it
--                  can never be deducted twice.
-- INTERNAL:        our own business cost. Must be tied to a consignment,
--                  a sale, or flagged as daily overhead.
CREATE TABLE operational_expenses (
    id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    expense_type      expense_type NOT NULL,
    category          expense_category NOT NULL,
    description       TEXT,
    amount            NUMERIC(12,2) NOT NULL CHECK (amount > 0),
    expense_date      DATE NOT NULL DEFAULT CURRENT_DATE,
    farm_owner_id     BIGINT REFERENCES farm_owners(id),
    consignment_id    BIGINT REFERENCES consignments(id),
    sale_id           BIGINT REFERENCES sales_transactions(id),
    is_daily_overhead BOOLEAN NOT NULL DEFAULT FALSE,
    settlement_id     BIGINT REFERENCES farm_owner_settlements(id),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),

    CHECK (expense_type <> 'FARM_DEDUCTIBLE' OR category IN
           ('DRIVER_ADVANCE','PACKAGING_CARTONS','EXTRA_DAY_FEE','CUSTOM_FARM_DEDUCTION')),
    CHECK (expense_type <> 'INTERNAL' OR category IN
           ('PARKING','UNLOADING_LABOR','DELIVERY_LABOR','CUSTOM_INTERNAL')),
    CHECK (expense_type <> 'FARM_DEDUCTIBLE' OR farm_owner_id IS NOT NULL),
    CHECK (expense_type <> 'INTERNAL'
           OR consignment_id IS NOT NULL OR sale_id IS NOT NULL OR is_daily_overhead),
    CHECK (expense_type = 'FARM_DEDUCTIBLE' OR settlement_id IS NULL)
);

-- ---------- 9. INDEXES (speed up common lookups) ---------------------
CREATE INDEX idx_consignments_date      ON consignments(arrival_date);
CREATE INDEX idx_consignments_farm      ON consignments(farm_owner_id);
CREATE INDEX idx_items_consignment      ON consignment_items(consignment_id);
CREATE INDEX idx_stock_item             ON item_stock(consignment_item_id);
CREATE INDEX idx_sales_date             ON sales_transactions(sale_date);
CREATE INDEX idx_sale_items_sale        ON sale_items(sale_id);
CREATE INDEX idx_sale_items_batch       ON sale_items(consignment_item_id);
CREATE INDEX idx_ledger_buyer           ON buyer_ledger(buyer_id, entry_date);
CREATE INDEX idx_expenses_farm_pending  ON operational_expenses(farm_owner_id) WHERE settlement_id IS NULL;
CREATE INDEX idx_expenses_date          ON operational_expenses(expense_date);
CREATE INDEX idx_settlements_farm       ON farm_owner_settlements(farm_owner_id, settlement_date);

-- ---------- 10. VIEWS: balances are calculated, never stored ---------
-- (so they can never drift out of sync with the real records)
CREATE VIEW v_farm_owner_balance WITH (security_invoker = true) AS
SELECT
    f.id AS farm_owner_id,
    f.name,
    COALESCE((SELECT SUM(net_payout) FROM farm_owner_settlements s
              WHERE s.farm_owner_id = f.id AND s.status = 'FINAL'), 0)
  - COALESCE((SELECT SUM(amount) FROM farm_owner_payments p
              WHERE p.farm_owner_id = f.id), 0) AS balance_payable
FROM farm_owners f;

CREATE VIEW v_buyer_balance WITH (security_invoker = true) AS
SELECT
    b.id AS buyer_id,
    b.name,
    COALESCE(SUM(CASE WHEN l.entry_type = 'INVOICE' THEN l.amount END), 0)
  - COALESCE(SUM(CASE WHEN l.entry_type = 'PAYMENT'
                       AND (l.payment_mode <> 'PDC' OR l.pdc_status = 'CLEARED')
                      THEN l.amount END), 0) AS balance_receivable
FROM buyers b
LEFT JOIN buyer_ledger l ON l.buyer_id = b.id
GROUP BY b.id, b.name;

-- ---------- 11. SECURITY: lock tables from the public API ------------
-- Supabase exposes tables to the internet through its own "Data API".
-- Enabling Row Level Security with NO policies blocks all of that access.
-- Our Python backend connects directly to the database, so it is unaffected.
DO $$
DECLARE t TEXT;
BEGIN
  FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
  END LOOP;
END $$;

-- ---------- 12. STARTER DATA ------------------------------------------
INSERT INTO vegetables (name, category) VALUES
  ('Tomato', 'Fruit Vegetable'),
  ('Cucumber', 'Fruit Vegetable'),
  ('Potato', 'Root'),
  ('Onion', 'Root');
