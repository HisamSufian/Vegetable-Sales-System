"""Farm owner money: extra costs, payments (with issued cheques) and the balance.
The balance formula itself lives in calc.py."""
from decimal import Decimal

from app.db import execute, query
from app.services import calc, opening
from app.services.stock_entries import parse_date
from app.services.trips import to_int
from app.timeutil import dubai_today

METHODS = ("cash", "bank", "cheque", "other")
METHOD_LABELS = {"cash": "Cash", "bank": "Bank", "cheque": "Cheque", "other": "Other"}
CHEQUE_STATUSES = ("pending", "cleared", "bounced")


# ---------------- extra costs ----------------
def owner_costs(owner_id: int) -> list[dict]:
    return query("SELECT c.*, t.trip_no FROM farm_owner_costs c LEFT JOIN trips t ON t.id = c.trip_id "
                 "WHERE c.farm_owner_id = %s AND c.is_deleted = false ORDER BY c.cost_date DESC, c.id DESC",
                 [owner_id])


def costs_for_trip(trip_id: int) -> list[dict]:
    return query("SELECT c.*, NULL AS trip_no FROM farm_owner_costs c WHERE c.trip_id = %s "
                 "AND c.is_deleted = false ORDER BY c.cost_date, c.id", [trip_id])


def get_cost(cost_id: int) -> dict | None:
    rows = query("SELECT * FROM farm_owner_costs WHERE id = %s AND is_deleted = false", [cost_id])
    return rows[0] if rows else None


def owner_trip_choices(owner_id: int) -> list[dict]:
    return query("SELECT t.id, t.trip_no, d.day_date FROM trips t JOIN days d ON d.id = t.day_id "
                 "WHERE t.farm_owner_id = %s AND t.is_deleted = false ORDER BY d.day_date DESC, t.id DESC",
                 [owner_id])


def check_cost_form(form: dict, owner_id: int) -> tuple[dict, list[str]]:
    errors = []
    amount, amount_error = calc.parse_money(form.get("amount"), blank=None)
    if amount_error:
        errors.append(f"Amount: {amount_error}")
    elif amount is None or amount <= 0:
        errors.append("Enter an amount above 0.")
    borne_by = form.get("borne_by")
    if borne_by not in ("farm_owner", "me"):
        errors.append("Choose who bears the cost: the farm owner or me.")
    when, date_error = parse_date(form.get("cost_date") or dubai_today().isoformat())
    if date_error:
        errors.append(date_error)
    trip_id = to_int(form.get("trip_id"))
    if trip_id and not query("SELECT 1 AS ok FROM trips WHERE id = %s AND farm_owner_id = %s "
                             "AND is_deleted = false", [trip_id, owner_id]):
        errors.append("That trip does not belong to this farm owner.")
    note = (form.get("note") or "").strip()
    values = {"amount": amount, "borne_by": borne_by, "when": when, "trip_id": trip_id or None,
              "note": note or None,
              "amount_text": (form.get("amount") or "").strip(),
              "date_text": (form.get("cost_date") or "").strip(), "note_text": note}
    return values, errors


def create_cost(owner_id: int, v: dict) -> int:
    return execute("INSERT INTO farm_owner_costs (farm_owner_id, trip_id, amount, borne_by, cost_date, note) "
                   "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                   [owner_id, v["trip_id"], v["amount"], v["borne_by"], v["when"], v["note"]])[0]["id"]


def update_cost(cost_id: int, v: dict) -> None:
    execute("UPDATE farm_owner_costs SET trip_id = %s, amount = %s, borne_by = %s, cost_date = %s, "
            "note = %s WHERE id = %s",
            [v["trip_id"], v["amount"], v["borne_by"], v["when"], v["note"], cost_id])


def hide_cost(cost_id: int) -> None:
    execute("UPDATE farm_owner_costs SET is_deleted = true WHERE id = %s", [cost_id])


# ---------------- payments ----------------
def owner_payments(owner_id: int) -> list[dict]:
    return query("SELECT * FROM farm_owner_payments WHERE farm_owner_id = %s AND is_deleted = false "
                 "ORDER BY pay_date DESC, id DESC", [owner_id])


def get_payment(payment_id: int) -> dict | None:
    rows = query("SELECT * FROM farm_owner_payments WHERE id = %s AND is_deleted = false", [payment_id])
    return rows[0] if rows else None


def check_payment_form(form: dict) -> tuple[dict, list[str]]:
    errors = []
    amount, amount_error = calc.parse_money(form.get("amount"), blank=None)
    if amount_error:
        errors.append(f"Amount: {amount_error}")
    elif amount is None or amount <= 0:
        errors.append("Enter an amount above 0.")
    method = form.get("method")
    if method not in METHODS:
        errors.append("Choose how it was paid.")
    when, date_error = parse_date(form.get("pay_date") or dubai_today().isoformat())
    if date_error:
        errors.append(date_error)

    cheque_no = (form.get("cheque_no") or "").strip()
    bank = (form.get("bank") or "").strip()
    due, status = None, None
    if method == "cheque":
        if not cheque_no:
            errors.append("Enter the cheque number.")
        due, due_error = parse_date(form.get("due_date"))
        if due_error:
            errors.append("Enter the cheque due date.")
        status = form.get("cheque_status") if form.get("cheque_status") in CHEQUE_STATUSES else "pending"
    else:
        cheque_no = bank = ""          # cheque details only apply to cheques
    note = (form.get("note") or "").strip()
    values = {"amount": amount, "method": method, "when": when, "note": note or None,
              "cheque_no": cheque_no or None, "bank": bank or None, "due": due, "status": status,
              "amount_text": (form.get("amount") or "").strip(),
              "date_text": (form.get("pay_date") or "").strip(),
              "due_text": (form.get("due_date") or "").strip(),
              "note_text": note, "cheque_no_text": cheque_no, "bank_text": bank}
    return values, errors


def create_payment(owner_id: int, v: dict) -> int:
    return execute(
        "INSERT INTO farm_owner_payments (farm_owner_id, amount, method, pay_date, note, cheque_no, bank, "
        "due_date, cheque_status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
        [owner_id, v["amount"], v["method"], v["when"], v["note"], v["cheque_no"], v["bank"],
         v["due"], v["status"]])[0]["id"]


def update_payment(payment_id: int, v: dict) -> None:
    execute("UPDATE farm_owner_payments SET amount = %s, method = %s, pay_date = %s, note = %s, "
            "cheque_no = %s, bank = %s, due_date = %s, cheque_status = %s WHERE id = %s",
            [v["amount"], v["method"], v["when"], v["note"], v["cheque_no"], v["bank"],
             v["due"], v["status"], payment_id])


def set_cheque_status(payment_id: int, status: str) -> None:
    execute("UPDATE farm_owner_payments SET cheque_status = %s WHERE id = %s AND method = 'cheque'",
            [status, payment_id])


def hide_payment(payment_id: int) -> None:
    execute("UPDATE farm_owner_payments SET is_deleted = true WHERE id = %s", [payment_id])


# ---------------- balance and profile page ----------------
def owner_summary(owner_id: int) -> dict:
    """All the numbers behind a farm owner's balance."""
    lines = query("SELECT sl.qty, sl.rate FROM settlement_lines sl "
                  "JOIN trip_rows r ON r.id = sl.trip_row_id JOIN trips t ON t.id = r.trip_id "
                  "WHERE t.farm_owner_id = %s AND sl.is_deleted = false AND r.is_deleted = false "
                  "AND t.is_deleted = false", [owner_id])
    settled = sum((calc.line_amount(l["qty"], l["rate"]) for l in lines), calc.ZERO)
    opening_total = opening.total("farm_owner", owner_id)

    costs = {r["borne_by"]: Decimal(r["total"]) for r in query(
        "SELECT borne_by, COALESCE(SUM(amount), 0) AS total FROM farm_owner_costs "
        "WHERE farm_owner_id = %s AND is_deleted = false GROUP BY borne_by", [owner_id])}
    paid = Decimal(query(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM farm_owner_payments "
        "WHERE farm_owner_id = %s AND is_deleted = false AND (method <> 'cheque' OR cheque_status = 'cleared')",
        [owner_id])[0]["total"])
    pending = query(
        "SELECT count(*) AS n, COALESCE(SUM(amount), 0) AS total FROM farm_owner_payments "
        "WHERE farm_owner_id = %s AND is_deleted = false AND method = 'cheque' AND cheque_status = 'pending'",
        [owner_id])[0]
    costs_owner = costs.get("farm_owner", calc.ZERO)
    return {
        "settled": settled, "opening": opening_total, "costs_owner": costs_owner,
        "costs_me": costs.get("me", calc.ZERO), "paid": paid,
        "cheques_pending_count": pending["n"], "cheques_pending_total": Decimal(pending["total"]),
        "balance": calc.farm_balance(settled, opening_total, costs_owner, paid),
    }


def owner_page(owner_id: int) -> dict:
    """Everything the farm owner profile page shows about money."""
    trips = query("SELECT t.id, t.trip_no, t.status, d.day_date, v.plate_number FROM trips t "
                  "JOIN days d ON d.id = t.day_id JOIN vehicles v ON v.id = t.vehicle_id "
                  "WHERE t.farm_owner_id = %s AND t.is_deleted = false ORDER BY d.day_date DESC, t.id DESC",
                  [owner_id])
    lines = query("SELECT r.trip_id, sl.qty, sl.rate FROM settlement_lines sl "
                  "JOIN trip_rows r ON r.id = sl.trip_row_id "
                  "WHERE r.trip_id = ANY(%s) AND sl.is_deleted = false AND r.is_deleted = false",
                  [[t["id"] for t in trips]])
    per_trip: dict[int, Decimal] = {}
    for l in lines:
        per_trip[l["trip_id"]] = per_trip.get(l["trip_id"], calc.ZERO) + calc.line_amount(l["qty"], l["rate"])
    for t in trips:
        t["settled_amount"] = per_trip.get(t["id"], calc.ZERO)
    return {**owner_summary(owner_id), "trips": trips, "costs": owner_costs(owner_id),
            "payments": owner_payments(owner_id), "openings": opening.list_openings("farm_owner", owner_id),
            "method_labels": METHOD_LABELS}
