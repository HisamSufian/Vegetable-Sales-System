"""Stock entries: moving cartons between vehicles, wastage, and corrections."""
from datetime import date

from app.db import execute, query
from app.services import calc, stock
from app.services.trips import profile_label, to_int
from app.timeutil import dubai_today

TABLES = {"move": "stock_moves", "wastage": "wastage", "correction": "stock_corrections"}
TITLES = {"move": "Store / move stock", "wastage": "Record wastage", "correction": "Stock correction"}


def parse_date(text) -> tuple[date | None, str | None]:
    try:
        return date.fromisoformat((text or "").strip()), None
    except ValueError:
        return None, "Please choose a valid date."


def empty_values(stock_key: str = "") -> dict:
    key = stock.parse_key(stock_key)
    option = stock.get_stock(*key) if key else None
    return {"stock_key": stock.make_key(*key) if option else "",
            "stock_label": stock.display(option) if option else "",
            "qty_text": "", "date_text": dubai_today().isoformat(), "note": "", "reason": "",
            "to_vehicle_id": "", "to_vehicle_label": ""}


def check_form(kind: str, form: dict) -> tuple[dict, list[str]]:
    """Validates a move / wastage / correction form."""
    errors = []
    key = stock.parse_key(form.get("stock_key"))
    option = stock.get_stock(*key) if key else None
    if option is None:
        errors.append("Please choose the stock.")
    when, date_error = parse_date(form.get("entry_date"))
    if date_error:
        errors.append(date_error)

    qty_text = (form.get("qty") or "").strip()
    if kind == "correction":
        qty = calc.parse_signed_int(qty_text)
        if qty is None or qty == 0:
            errors.append("Enter the change as a whole number like +5 or -3 (not 0).")
    else:
        qty = to_int(qty_text)
        if qty is None or qty < 1:
            errors.append("Enter the cartons as a whole number, 1 or more.")

    to_id = to_int(form.get("to_vehicle_id")) if kind == "move" else None
    if kind == "move":
        if not to_id or not query("SELECT 1 AS ok FROM vehicles WHERE id = %s AND is_deleted = false", [to_id]):
            errors.append("Please choose the vehicle to store the cartons in.")
        elif option and to_id == key[1]:
            errors.append("Choose a different vehicle from the one the cartons are in now.")

    note = (form.get("note") or "").strip()
    reason = (form.get("reason") or "").strip()
    if kind == "correction" and not reason:
        errors.append("A reason is required for a correction.")

    values = {
        "trip_row_id": key[0] if option else None, "vehicle_id": key[1] if option else None,
        "to_vehicle_id": to_id, "qty": qty, "when": when, "note": note or None, "reason": reason,
        # what the form shows again if something is wrong
        "stock_key": stock.make_key(*key) if option else "",
        "stock_label": stock.display(option) if option else "",
        "qty_text": qty_text, "date_text": (form.get("entry_date") or "").strip(),
        "to_vehicle_label": profile_label("vehicles", to_id) if to_id else "",
    }
    return values, errors


def create(kind: str, v: dict) -> int:
    if kind == "move":
        sql = ("INSERT INTO stock_moves (trip_row_id, from_vehicle_id, to_vehicle_id, qty, move_date, note) "
               "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id")
        params = [v["trip_row_id"], v["vehicle_id"], v["to_vehicle_id"], v["qty"], v["when"], v["note"]]
    elif kind == "wastage":
        sql = ("INSERT INTO wastage (trip_row_id, vehicle_id, qty, waste_date, note) "
               "VALUES (%s, %s, %s, %s, %s) RETURNING id")
        params = [v["trip_row_id"], v["vehicle_id"], v["qty"], v["when"], v["note"]]
    else:
        sql = ("INSERT INTO stock_corrections (trip_row_id, vehicle_id, qty_change, correction_date, reason) "
               "VALUES (%s, %s, %s, %s, %s) RETURNING id")
        params = [v["trip_row_id"], v["vehicle_id"], v["qty"], v["when"], v["reason"]]
    return execute(sql, params)[0]["id"]


def update(kind: str, entry_id: int, v: dict) -> None:
    if kind == "move":
        execute("UPDATE stock_moves SET trip_row_id = %s, from_vehicle_id = %s, to_vehicle_id = %s, "
                "qty = %s, move_date = %s, note = %s WHERE id = %s",
                [v["trip_row_id"], v["vehicle_id"], v["to_vehicle_id"], v["qty"], v["when"], v["note"], entry_id])
    elif kind == "wastage":
        execute("UPDATE wastage SET trip_row_id = %s, vehicle_id = %s, qty = %s, waste_date = %s, "
                "note = %s WHERE id = %s",
                [v["trip_row_id"], v["vehicle_id"], v["qty"], v["when"], v["note"], entry_id])
    else:
        execute("UPDATE stock_corrections SET trip_row_id = %s, vehicle_id = %s, qty_change = %s, "
                "correction_date = %s, reason = %s WHERE id = %s",
                [v["trip_row_id"], v["vehicle_id"], v["qty"], v["when"], v["reason"], entry_id])


def hide(kind: str, entry_id: int) -> None:
    execute(f"UPDATE {TABLES[kind]} SET is_deleted = true WHERE id = %s", [entry_id])


def load(kind: str, entry_id: int) -> dict | None:
    rows = query(f"SELECT * FROM {TABLES[kind]} WHERE id = %s AND is_deleted = false", [entry_id])
    return rows[0] if rows else None


def values_from_entry(kind: str, e: dict) -> dict:
    """Fills the form with an existing entry (for editing)."""
    vehicle_id = e["from_vehicle_id"] if kind == "move" else e["vehicle_id"]
    option = stock.get_stock(e["trip_row_id"], vehicle_id)
    v = empty_values()
    v["stock_key"] = stock.make_key(e["trip_row_id"], vehicle_id)
    v["stock_label"] = stock.display(option) if option else ""
    if kind == "move":
        v.update(qty_text=str(e["qty"]), date_text=e["move_date"].isoformat(), note=e["note"] or "",
                 to_vehicle_id=e["to_vehicle_id"], to_vehicle_label=profile_label("vehicles", e["to_vehicle_id"]))
    elif kind == "wastage":
        v.update(qty_text=str(e["qty"]), date_text=e["waste_date"].isoformat(), note=e["note"] or "")
    else:
        v.update(qty_text=str(e["qty_change"]), date_text=e["correction_date"].isoformat(), reason=e["reason"])
    return v


_BASE = """
    FROM {table} x
    JOIN trip_rows r ON r.id = x.trip_row_id
    JOIN trips t ON t.id = r.trip_id
    JOIN vegetables veg ON veg.id = r.vegetable_id
    JOIN farm_owners f ON f.id = t.farm_owner_id
"""


def recent_entries(limit: int = 40) -> list[dict]:
    """The latest moves, wastage and corrections together, newest first."""
    out = []
    for e in query("SELECT x.id, x.move_date AS entry_date, x.qty, x.note, veg.name AS veg, t.trip_no, "
                   "f.name AS farm, vf.plate_number AS from_plate, vt.plate_number AS to_plate "
                   + _BASE.format(table="stock_moves") +
                   " JOIN vehicles vf ON vf.id = x.from_vehicle_id JOIN vehicles vt ON vt.id = x.to_vehicle_id"
                   " WHERE x.is_deleted = false ORDER BY x.move_date DESC, x.id DESC LIMIT %s", [limit]):
        out.append({"kind": "move", "id": e["id"], "date": e["entry_date"],
                    "text": f"Moved {e['qty']} {e['veg']} ({e['trip_no']}, {e['farm']}) "
                            f"from {e['from_plate']} to {e['to_plate']}", "note": e["note"]})
    for e in query("SELECT x.id, x.waste_date AS entry_date, x.qty, x.note, veg.name AS veg, t.trip_no, "
                   "f.name AS farm, v.plate_number AS plate "
                   + _BASE.format(table="wastage") +
                   " JOIN vehicles v ON v.id = x.vehicle_id"
                   " WHERE x.is_deleted = false ORDER BY x.waste_date DESC, x.id DESC LIMIT %s", [limit]):
        out.append({"kind": "wastage", "id": e["id"], "date": e["entry_date"],
                    "text": f"Wasted {e['qty']} {e['veg']} ({e['trip_no']}, {e['farm']}) in {e['plate']}",
                    "note": e["note"]})
    for e in query("SELECT x.id, x.correction_date AS entry_date, x.qty_change, x.reason, veg.name AS veg, "
                   "t.trip_no, f.name AS farm, v.plate_number AS plate "
                   + _BASE.format(table="stock_corrections") +
                   " JOIN vehicles v ON v.id = x.vehicle_id"
                   " WHERE x.is_deleted = false ORDER BY x.correction_date DESC, x.id DESC LIMIT %s", [limit]):
        out.append({"kind": "correction", "id": e["id"], "date": e["entry_date"],
                    "text": f"Correction {e['qty_change']:+d} {e['veg']} ({e['trip_no']}, {e['farm']}) in {e['plate']}",
                    "note": e["reason"]})
    out.sort(key=lambda e: (e["date"], e["id"]), reverse=True)
    return out[:limit]
