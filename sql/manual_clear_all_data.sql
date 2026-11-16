-- =====================================================================
-- GO-LIVE OPTION 1: delete ALL test data, including profiles
-- (farm owners, customers, drivers, vehicles, vegetables) and everything else.
-- Keeps: your Settings, and the built-in Walk-in / Cash customer.
-- Numbers start again at T-0001 and B-0001.
--
-- !!! THIS CANNOT BE UNDONE. Download a backup from Settings FIRST. !!!
-- Run it by hand in Supabase -> SQL Editor. The app never runs it.
-- =====================================================================
TRUNCATE TABLE
    expenses, customer_adjustments, customer_payments, opening_balances,
    farm_owner_payments, farm_owner_costs, settlement_lines, sale_returns,
    stock_corrections, wastage, stock_moves, sale_lines, sale_bills,
    trip_rows, trips, days,
    vegetables, vehicles, drivers, customers, farm_owners
RESTART IDENTITY CASCADE;

-- the built-in customer for cash sales
INSERT INTO customers (name, is_walk_in) VALUES ('Walk-in / Cash', TRUE);
