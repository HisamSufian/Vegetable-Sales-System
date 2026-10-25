-- =====================================================================
-- 003_one_row_per_vegetable.sql : a trip has ONE row per vegetable.
-- Run once in Supabase -> SQL Editor. Run it BEFORE deploying the new code.
-- =====================================================================

-- 1. Where a trip already has the same vegetable twice, add the cartons into the
--    oldest row...
UPDATE trip_rows r
SET arrived_qty = d.total
FROM (SELECT trip_id, vegetable_id, MIN(id) AS keep_id, SUM(arrived_qty) AS total
      FROM trip_rows
      WHERE is_deleted = false
      GROUP BY trip_id, vegetable_id
      HAVING COUNT(*) > 1) d
WHERE r.id = d.keep_id;

-- 2. ...and hide the other copies (safe: no sales exist yet).
UPDATE trip_rows r
SET is_deleted = true
FROM (SELECT trip_id, vegetable_id, MIN(id) AS keep_id
      FROM trip_rows
      WHERE is_deleted = false
      GROUP BY trip_id, vegetable_id
      HAVING COUNT(*) > 1) d
WHERE r.trip_id = d.trip_id
  AND r.vegetable_id = d.vegetable_id
  AND r.is_deleted = false
  AND r.id <> d.keep_id;

-- 3. From now on the database itself refuses a second visible row for the same
--    vegetable in a trip.
CREATE UNIQUE INDEX uq_trip_rows_one_per_vegetable
    ON trip_rows (trip_id, vegetable_id) WHERE is_deleted = false;
