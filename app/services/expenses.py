"""General business expenses: date, amount, a free-text note, optional link to a trip."""
from datetime import date

from app.db import execute, query
from app.services import calc
from app.services.stock_entries import parse_date
from app.services.trips import to_int
from app.timeutil import dubai_today


def list_expenses(d_from: date, d_to: date) -> list[dict]:
    return query("SELECT e.*, t.trip_no FROM expenses e LEFT JOIN trips t ON t.id = e.trip_id "
                 "WHERE e.is_deleted = false AND e.expense_date BETWEEN %s AND %s "
                 "ORDER BY e.expense_date DESC, e.id DESC", [d_from, d_to])


def get_expense(expense_id: int) -> dict | None:
    rows = query("SELECT * FROM expenses WHERE id = %s AND is_deleted = false", [expense_id])
    return rows[0] if rows else None


def trip_label(trip_id) -> str:
    if not trip_id:
        return ""
    rows = query("SELECT t.trip_no, v.plate_number FROM trips t JOIN vehicles v ON v.id = t.vehicle_id "
                 "WHERE t.id = %s", [trip_id])
    return f"{rows[0]['trip_no']} | {rows[0]['plate_number']}" if rows else ""


def search_trips(q: str, limit: int = 20) -> list[dict]:
    """Trips for the dropdown (type a trip number, farm owner or plate)."""
    where, params = [], []
    for word in q.lower().split():
        where.append("lower(t.trip_no || ' ' || f.name || ' ' || v.plate_number) LIKE %s")
        params.append(f"%{word}%")
    sql = ("SELECT t.id, t.trip_no, f.name AS farm_owner_name, v.plate_number, d.day_date "
           "FROM trips t JOIN farm_owners f ON f.id = t.farm_owner_id JOIN vehicles v ON v.id = t.vehicle_id "
           "JOIN days d ON d.id = t.day_id WHERE t.is_deleted = false")
    if where:
        sql += " AND " + " AND ".join(where)
    sql += " ORDER BY d.day_date DESC, t.id DESC LIMIT %s"
    return [{"id": str(r["id"]), "label": f"{r['trip_no']} | {r['plate_number']}",
             "sub": f"{r['farm_owner_name']} | {r['day_date'].strftime('%d %b %Y')}", "neg": False}
            for r in query(sql, params + [limit])]


def check_form(form: dict) -> tuple[dict, list[str]]:
    errors = []
    amount, amount_error = calc.parse_money(form.get("amount"), blank=None)
    if amount_error:
        errors.append(f"Amount: {amount_error}")
    elif amount is None or amount <= 0:
        errors.append("Enter an amount above 0.")
    when, date_error = parse_date(form.get("expense_date") or dubai_today().isoformat())
    if date_error:
        errors.append(date_error)
    trip_id = to_int(form.get("trip_id"))
    if trip_id and not query("SELECT 1 AS ok FROM trips WHERE id = %s AND is_deleted = false", [trip_id]):
        errors.append("That trip was not found.")
        trip_id = None
    note = (form.get("note") or "").strip()
    values = {"amount": amount, "when": when, "trip_id": trip_id, "note": note or None,
              "amount_text": (form.get("amount") or "").strip(),
              "date_text": (form.get("expense_date") or "").strip(), "note_text": note,
              "trip_label": trip_label(trip_id)}
    return values, errors


def create_expense(v: dict) -> int:
    return execute("INSERT INTO expenses (expense_date, amount, note, trip_id) VALUES (%s, %s, %s, %s) "
                   "RETURNING id", [v["when"], v["amount"], v["note"], v["trip_id"]])[0]["id"]


def update_expense(expense_id: int, v: dict) -> None:
    execute("UPDATE expenses SET expense_date = %s, amount = %s, note = %s, trip_id = %s WHERE id = %s",
            [v["when"], v["amount"], v["note"], v["trip_id"], expense_id])


def hide_expense(expense_id: int) -> None:
    execute("UPDATE expenses SET is_deleted = true WHERE id = %s", [expense_id])
