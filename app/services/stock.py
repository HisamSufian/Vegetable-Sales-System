"""Stock = what is left of each trip row.
Now:  left = arrived - sold.   Later phases add returns, wastage, corrections and
moves between vehicles here, so there is one place that knows the stock rules."""
from app.db import query

# cartons sold per trip row (ignores hidden lines and hidden bills)
SOLD_BY_ROW = """(
    SELECT l.trip_row_id, SUM(l.qty) AS qty
    FROM sale_lines l JOIN sale_bills b ON b.id = l.bill_id
    WHERE l.is_deleted = false AND b.is_deleted = false
    GROUP BY l.trip_row_id
)"""

STOCK_SELECT = f"""
    SELECT r.id AS trip_row_id, t.vehicle_id, v.plate_number, veg.name AS vegetable_name,
           f.name AS farm_owner_name, t.trip_no, d.day_date AS arrival_date, r.arrived_qty,
           r.arrived_qty - COALESCE(s.qty, 0) AS stock_left
    FROM trip_rows r
    JOIN trips t ON t.id = r.trip_id AND t.is_deleted = false
    JOIN days d ON d.id = t.day_id
    JOIN vegetables veg ON veg.id = r.vegetable_id
    JOIN farm_owners f ON f.id = t.farm_owner_id
    JOIN vehicles v ON v.id = t.vehicle_id
    LEFT JOIN {SOLD_BY_ROW} s ON s.trip_row_id = r.id
    WHERE r.is_deleted = false
"""


def make_key(trip_row_id: int, vehicle_id: int) -> str:
    """The value the stock dropdown submits: which trip row, in which vehicle."""
    return f"{trip_row_id}-{vehicle_id}"


def parse_key(text) -> tuple[int, int] | None:
    parts = str(text or "").strip().split("-")
    if len(parts) == 2 and all(p.isdigit() for p in parts):
        return int(parts[0]), int(parts[1])
    return None


def describe(row: dict) -> dict:
    """Turns a stock row into what the dropdown shows."""
    left = row["stock_left"]
    label = f"{row['vegetable_name']} - {left} left" + (" (negative!)" if left < 0 else "")
    sub = (f"{row['farm_owner_name']} | {row['trip_no']} | "
           f"{row['arrival_date'].strftime('%d %b %Y')} | {row['plate_number']}")
    return {"id": make_key(row["trip_row_id"], row["vehicle_id"]),
            "label": label, "sub": sub, "neg": left < 0}


def search_stock(q: str, limit: int = 30) -> list[dict]:
    """Stock for the dropdown. With nothing typed: only rows with cartons left.
    When typing: every matching row, including ones at 0 or negative.
    Every typed word must match the vegetable, farm owner, trip number or plate."""
    where, params = [], []
    for word in q.lower().split():
        where.append("lower(veg.name || ' ' || f.name || ' ' || t.trip_no || ' ' || v.plate_number) LIKE %s")
        params.append(f"%{word}%")
    if where:
        sql = STOCK_SELECT + " AND " + " AND ".join(where)
    else:
        sql = STOCK_SELECT + " AND r.arrived_qty - COALESCE(s.qty, 0) > 0"
    sql += " ORDER BY d.day_date DESC, t.id DESC, r.id LIMIT %s"
    return query(sql, params + [limit])


def get_stock(trip_row_id: int, vehicle_id: int) -> dict | None:
    rows = query(STOCK_SELECT + " AND r.id = %s AND t.vehicle_id = %s", [trip_row_id, vehicle_id])
    return rows[0] if rows else None
