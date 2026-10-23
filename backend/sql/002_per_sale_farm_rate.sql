-- =====================================================================
-- MIGRATION 002: farm payout is decided PER SALE LINE, not per day.
-- Example: sold at 25 -> farm gets 20; sold at 23 -> farm gets 18 (5 margin kept)
-- Run once in Supabase -> SQL Editor.
-- (Safe now because no sales exist yet.)
-- =====================================================================

-- 1. Each sold line records what the FARM gets per carton.
--    margin and farm_payout are calculated by the database.
ALTER TABLE sale_items
  ADD COLUMN farm_rate_per_carton NUMERIC(12,2) NOT NULL CHECK (farm_rate_per_carton >= 0),
  ADD COLUMN margin_per_carton    NUMERIC(12,2) GENERATED ALWAYS AS (price_per_carton - farm_rate_per_carton) STORED,
  ADD COLUMN farm_payout          NUMERIC(12,2) GENERATED ALWAYS AS (cartons * farm_rate_per_carton) STORED;

-- 2. Optional default margin per farm owner (e.g. 5.00). The POS uses it to
--    suggest the farm rate automatically: farm rate = selling price - margin.
ALTER TABLE farm_owners
  ADD COLUMN default_margin_per_carton NUMERIC(12,2) CHECK (default_margin_per_carton >= 0);

-- 3. The day-based rate table is no longer needed.
DROP TABLE farm_rates;
