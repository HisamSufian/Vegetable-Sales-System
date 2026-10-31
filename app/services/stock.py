"""Stock rules in ONE place.

For every trip row and every vehicle, the cartons there are the sum of:
    + arrived (in the trip's own vehicle)
    + moved in        - moved out
    - sold            - wasted
    + corrections (+ or -)
Later phases add one more line to LEDGER (returns) and nothing else changes."""
from app.db import query

LEDGER = """(
    SELECT r.id AS trip_row_id, t.vehicle_id AS vehicle_id, r.arrived_qty AS delta
    FROM trip_rows r JOIN trips t ON t.id = r.trip_id
    WHERE r.is_deleted = false AND t.is_deleted = false
  UNION ALL
    SELECT m.trip_row_id, m.to_vehicle_id, m.qty
    FROM stock_moves m WHERE m.is_deleted = false
  UNION ALL
    SELECT m.trip_row_id, m.from_vehicle_id, -m.qty
    FROM stock_moves m WHERE m.is_deleted = false
  UNION ALL
    SELECT l.trip_row_id, l.from_vehicle_id, -l.qty
    FROM sale_lines l JOIN sale_bills b ON b.id = l.bill_id
    WHERE l.is_deleted = false AND b.is_deleted = false
  UNION ALL
    SELECT w.trip_row_id, w.vehicle_id, -w.qty
    FROM wastage w WHERE w.is_deleted = false
  UNION ALL
    SELECT c.trip_row_id, c.vehicle_id, c.qty_change
    FROM stock_corrections c WHERE c.is_deleted = false
)"""

# cartons per trip row in each vehicle / in total
LOCATION_STOCK = f"(SELECT trip_row_id, vehicle_id, SUM(delta) AS qty FROM {LEDGER} lg GROUP BY trip_row_id, vehicle_id)"
ROW_STOCK = f"(SELECT trip_row_id, SUM(delta) AS qty FROM {LEDGER} lg GROUP BY trip_row_id)"

# cartons sold / wasted per trip row (shown on the trip page)
SOLD_BY_ROW = """(
    SELECT l.trip_row_id, SUM(l.qty) AS qty
    FROM sale_lines l JOIN sale_bills b ON b.id = l.bill_id
    WHERE l.is_deleted = false AND b.is_deleted = false
    GROUP BY l.trip_row_id
)"""
WASTED_BY_ROW = """(
    SELECT w.trip_row_id, SUM(w.qty) AS qty
    FROM wastage w WHERE w.is_deleted = false
    GROUP BY w.trip_row_id
)"""

STOCK_SELECT = f"""
    SELECT r.id AS trip_row_id, ls.vehicle_id, v.plate_number, veg.name AS vegetable_name,
           f.name AS farm_owner_name, t.id AS trip_id, t.trip_no, t.day_id,
           d.day_date AS arrival_date, r.arrived_qty, t.vehicle_id AS arrival_vehicle_id,
           ls.qty AS stock_left
    FROM {LOCATION_STOCK} ls
    JOIN trip_rows r ON r.id = ls.trip_row_id AND r.is_deleted = false
    JOIN trips t ON t.id = r.trip_id AND t.is_deleted = false
    JOIN days d ON d.id = t.day_id
    JOIN vegetables veg ON veg.id = r.vegetable_id
    JOIN farm_owners f ON f.id = t.farm_owner_id
    JOIN vehicles v ON v.id = ls.vehicle_id
    WHERE true
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


def display(row: dict) -> str:
    d = describe(row)
    return f"{d['label']} | {d['sub']}"


def search_stock(q: str, limit: int = 30) -> list[dict]:
    """Stock for the dropdowns (one entry per trip row per vehicle).
    With nothing typed: only entries with cartons left.
    When typing: every matching entry, including ones at 0 or negative.
    Every typed word must match the vegetable, farm owner, trip number or plate."""
    where, params = [], []
    for word in q.lower().split():
        where.append("lower(veg.name || ' ' || f.name || ' ' || t.trip_no || ' ' || v.plate_number) LIKE %s")
        params.append(f"%{word}%")
    if where:
        sql = STOCK_SELECT + " AND " + " AND ".join(where)
    else:
        sql = STOCK_SELECT + " AND ls.qty > 0"
    sql += " ORDER BY d.day_date DESC, t.id DESC, r.id, v.plate_number LIMIT %s"
    return query(sql, params + [limit])


def get_stock(trip_row_id: int, vehicle_id: int) -> dict | None:
    rows = query(STOCK_SELECT + " AND r.id = %s AND ls.vehicle_id = %s", [trip_row_id, vehicle_id])
    return rows[0] if rows else None


def stock_overview() -> list[dict]:
    """Everything on hand (or below zero) right now, for the Stock page."""
    return query(STOCK_SELECT + " AND ls.qty <> 0 "
                 "ORDER BY v.plate_number, veg.name, d.day_date, t.id")


def group_stock(rows: list[dict], view: str) -> list[dict]:
    """Groups the overview by vehicle (default) or by vegetable, with totals."""
    groups: dict[str, dict] = {}
    for r in rows:
        if view == "vegetable":
            title, main = r["vegetable_name"], r["plate_number"]
        else:
            title, main = r["plate_number"], r["vegetable_name"]
        g = groups.setdefault(title, {"title": title, "total": 0, "items": []})
        g["total"] += r["stock_left"]
        g["items"].append({**r, "main": main})
    return sorted(groups.values(), key=lambda g: g["title"].lower())


def unstored_for_day(day_id: int) -> list[dict]:
    """Cartons of this Day's trips that are still in the vehicle they arrived in
    (used for the close-Day warning)."""
    return query(STOCK_SELECT + " AND t.day_id = %s AND ls.vehicle_id = t.vehicle_id AND ls.qty > 0 "
                 "ORDER BY t.id, veg.name", [day_id])


def negative_message(trip_row_id: int, vehicle_id: int) -> str | None:
    """A warning (never a block) when a vehicle's stock of a row has gone below zero."""
    row = get_stock(trip_row_id, vehicle_id)
    if row and row["stock_left"] < 0:
        return (f"Warning: {row['vegetable_name']} ({row['trip_no']}, {row['farm_owner_name']}) in "
                f"{row['plate_number']} is now at {row['stock_left']} cartons. More was taken out "
                f"than is there. Please check the arrival count or move the stock.")
    return None
