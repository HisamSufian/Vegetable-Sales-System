"""Trips (one truck + one farm owner + one driver on one Day) and their vegetable rows."""
from app.db import execute, query
from app.services.profiles import get_kind, get_profile

TRIP_SELECT = """
    SELECT t.*, d.day_date, d.status AS day_status,
           v.plate_number, f.name AS farm_owner_name, dr.name AS driver_name
    FROM trips t
    JOIN days d ON d.id = t.day_id
    JOIN vehicles v ON v.id = t.vehicle_id
    JOIN farm_owners f ON f.id = t.farm_owner_id
    JOIN drivers dr ON dr.id = t.driver_id
"""

CHOICES = [  # form field, profile type, table, message when missing
    ("vehicle_id", "vehicles", "vehicles", "Please choose a truck."),
    ("farm_owner_id", "farm-owners", "farm_owners", "Please choose a farm owner."),
    ("driver_id", "drivers", "drivers", "Please choose a driver."),
]


def to_int(value) -> int | None:
    """'100' -> 100. Anything else (blank, 12.5, text) -> None. Whole numbers only."""
    text = str(value or "").strip()
    return int(text) if text.isdigit() else None


def profile_label(kind: str, profile_id) -> str:
    """Name to show in a dropdown for an already-chosen id ('' if none)."""
    if not profile_id:
        return ""
    row = get_profile(get_kind(kind), profile_id)
    return row["label"] if row else ""


def parse_trip_form(form: dict) -> dict:
    """Pulls the chosen ids and note out of a submitted trip form,
    plus the labels needed to show the dropdowns again after an error."""
    values = {"note": (form.get("note") or "").strip()}
    for field, kind, _table, _msg in CHOICES:
        pid = to_int(form.get(field))
        values[field] = pid
        values[field.replace("_id", "_label")] = profile_label(kind, pid)
    return values


def check_choices(values: dict, current: dict | None = None) -> list[str]:
    """Each of truck / farm owner / driver must be chosen and must exist.
    When editing, the trip's current choice is accepted even if later hidden."""
    errors = []
    for field, _kind, table, message in CHOICES:
        pid = values.get(field)
        if not pid:
            errors.append(message)
            continue
        if current and current.get(field) == pid:
            continue
        if not query(f"SELECT 1 AS ok FROM {table} WHERE id = %s AND is_deleted = false", [pid]):
            errors.append(message)
    return errors


# ---------------- trips ----------------
def trips_for_day(day_id: int) -> list[dict]:
    trips = query(TRIP_SELECT + " WHERE t.day_id = %s AND t.is_deleted = false ORDER BY t.id", [day_id])
    rows = rows_for_trips([t["id"] for t in trips])
    for t in trips:
        t["lines"] = rows.get(t["id"], [])
        t["total"] = sum(r["arrived_qty"] for r in t["lines"])
        t["summary"] = ", ".join(f"{r['vegetable_name']} {r['arrived_qty']}" for r in t["lines"])
    return trips


def get_trip(trip_id: int) -> dict | None:
    rows = query(TRIP_SELECT + " WHERE t.id = %s AND t.is_deleted = false", [trip_id])
    return rows[0] if rows else None


def create_trip(day_id: int, values: dict) -> int:
    return execute(
        "INSERT INTO trips (day_id, vehicle_id, farm_owner_id, driver_id, note) "
        "VALUES (%s, %s, %s, %s, %s) RETURNING id",
        [day_id, values["vehicle_id"], values["farm_owner_id"], values["driver_id"],
         values["note"] or None])[0]["id"]


def update_trip(trip_id: int, values: dict) -> None:
    execute("UPDATE trips SET vehicle_id = %s, farm_owner_id = %s, driver_id = %s, note = %s "
            "WHERE id = %s",
            [values["vehicle_id"], values["farm_owner_id"], values["driver_id"],
             values["note"] or None, trip_id])


def trip_blockers(trip_id: int) -> list[str]:
    """Reasons a trip cannot be hidden, for example 'This trip has 12 sale lines'.
    Nothing depends on trips yet; Phase 3 (sales) and Phase 6 (settlements) add checks."""
    return []


def hide_trip(trip_id: int) -> None:
    execute("UPDATE trips SET is_deleted = true WHERE id = %s", [trip_id])


# ---------------- trip rows ----------------
ROW_SELECT = """
    SELECT r.*, veg.name AS vegetable_name
    FROM trip_rows r JOIN vegetables veg ON veg.id = r.vegetable_id
"""


def rows_for_trips(trip_ids: list[int]) -> dict[int, list[dict]]:
    grouped: dict[int, list[dict]] = {}
    if not trip_ids:
        return grouped
    for r in query(ROW_SELECT + " WHERE r.trip_id = ANY(%s) AND r.is_deleted = false ORDER BY r.id",
                   [trip_ids]):
        grouped.setdefault(r["trip_id"], []).append(r)
    return grouped


def rows_for_trip(trip_id: int) -> list[dict]:
    return rows_for_trips([trip_id]).get(trip_id, [])


def get_row(row_id: int) -> dict | None:
    rows = query(ROW_SELECT + " WHERE r.id = %s AND r.is_deleted = false", [row_id])
    return rows[0] if rows else None


def vegetable_is_visible(vegetable_id: int) -> bool:
    return bool(query("SELECT 1 AS ok FROM vegetables WHERE id = %s AND is_deleted = false",
                      [vegetable_id]))


def check_row_form(form: dict, minimum: int, current_vegetable_id: int | None = None) -> tuple[dict, list[str]]:
    """Validates a vegetable row: a chosen vegetable and a whole number of cartons."""
    errors = []
    vegetable_id = to_int(form.get("vegetable_id"))
    qty = to_int(form.get("arrived_qty"))
    if not vegetable_id or (vegetable_id != current_vegetable_id and not vegetable_is_visible(vegetable_id)):
        errors.append("Please choose a vegetable.")
    if qty is None or qty < minimum:
        errors.append(f"Enter the cartons as a whole number, {minimum} or more.")
    values = {"vegetable_id": vegetable_id, "arrived_qty": qty,
              "vegetable_label": profile_label("vegetables", vegetable_id),
              "qty_text": (form.get("arrived_qty") or "").strip()}
    return values, errors


def add_row(trip_id: int, vegetable_id: int, qty: int) -> None:
    execute("INSERT INTO trip_rows (trip_id, vegetable_id, arrived_qty) VALUES (%s, %s, %s)",
            [trip_id, vegetable_id, qty])


def update_row(row_id: int, vegetable_id: int, qty: int) -> None:
    execute("UPDATE trip_rows SET vegetable_id = %s, arrived_qty = %s WHERE id = %s",
            [vegetable_id, qty, row_id])


def row_blockers(row_id: int) -> list[str]:
    """Reasons a row cannot be hidden (for example sales were made from it).
    Phase 3 adds the real check."""
    return []


def hide_row(row_id: int) -> None:
    execute("UPDATE trip_rows SET is_deleted = true WHERE id = %s", [row_id])
