-- =====================================================================
-- GO-LIVE OPTION 2: delete the test TRANSACTIONS but KEEP your profiles
-- (farm owners, customers, drivers, vehicles, vegetables) and Settings.
-- Deletes: days, trips, sales, stock entries, returns, settlements, costs,
-- payments, cheques, write-offs, opening balances and expenses.
-- Numbers start again at T-0001 and B-0001.
--
-- !!! THIS CANNOT BE UNDONE. Download a backup from Settings FIRST. !!!
-- Run it by hand in Supabase -> SQL Editor. The app never runs it.
-- =====================================================================
TRUNCATE TABLE
    expenses, customer_adjustments, customer_payments, opening_balances,
    farm_owner_payments, farm_owner_costs, settlement_lines, sale_returns,
    stock_corrections, wastage, stock_moves, sale_lines, sale_bills,
    trip_rows, trips, days
RESTART IDENTITY;
