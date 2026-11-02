"""Customer returns: cartons come back from a sale line into the same trip row."""
from app.db import execute, query
from app.services import calc
from app.services.stock_entries import parse_date
from app.services.trips import profile_label, to_int


def get_return(return_id: int) -> dict | None:
    rows = query("SELECT * FROM sale_returns WHERE id = %s AND is_deleted = false", [return_id])
    return rows[0] if rows else None


def returned_total(line_id: int, exclude_return_id: int | None = None) -> int:
    """Cartons already returned from a sale line (optionally ignoring one return)."""
    rows = query("SELECT COALESCE(SUM(qty), 0) AS n FROM sale_returns "
                 "WHERE sale_line_id = %s AND is_deleted = false AND id <> %s",
                 [line_id, exclude_return_id or 0])
    return int(rows[0]["n"])


def returns_for_bill(bill_id: int) -> list[dict]:
    rows = query("""
        SELECT rt.id, rt.sale_line_id, rt.qty, rt.credit_rate, rt.return_date, rt.note, v.plate_number
        FROM sale_returns rt
        JOIN sale_lines l ON l.id = rt.sale_line_id
        JOIN vehicles v ON v.id = rt.back_to_vehicle_id
        WHERE l.bill_id = %s AND rt.is_deleted = false AND l.is_deleted = false
        ORDER BY rt.id
    """, [bill_id])
    for r in rows:
        r["credit_amount"] = calc.line_amount(r["qty"], r["credit_rate"])
    return rows


def returns_for_bills(bill_ids: list[int]) -> dict[int, list[dict]]:
    """For bill lists: each bill's returns (qty and credit rate), grouped by bill."""
    grouped: dict[int, list[dict]] = {}
    if not bill_ids:
        return grouped
    for r in query("SELECT l.bill_id, rt.qty, rt.credit_rate FROM sale_returns rt "
                   "JOIN sale_lines l ON l.id = rt.sale_line_id "
                   "WHERE rt.is_deleted = false AND l.is_deleted = false AND l.bill_id = ANY(%s)",
                   [bill_ids]):
        grouped.setdefault(r["bill_id"], []).append(r)
    return grouped


def check_form(form: dict, line: dict, exclude_return_id: int | None = None) -> tuple[dict, list[str]]:
    """Validates a return form against the sale line it comes from."""
    errors = []
    others = returned_total(line["id"], exclude_return_id)
    max_qty = line["qty"] - others

    qty = to_int(form.get("qty"))
    if qty is None or qty < 1:
        errors.append("Enter the cartons as a whole number, 1 or more.")
    elif qty > max_qty:
        errors.append(f"Only {max_qty} cartons can still be returned from this line "
                      f"(sold {line['qty']}, already returned {others}). "
                      f"If the line was entered wrongly, edit the sale line first.")

    credit_rate, rate_error = calc.parse_money(form.get("credit_rate"), blank=None)
    if rate_error:
        errors.append(f"Credit rate: {rate_error}")
    elif credit_rate is None:
        errors.append("Enter the credit rate per carton.")

    vehicle_id = to_int(form.get("back_to_vehicle_id"))
    if not vehicle_id or not query("SELECT 1 AS ok FROM vehicles WHERE id = %s AND is_deleted = false",
                                   [vehicle_id]):
        errors.append("Please choose the vehicle the cartons are in now.")
        vehicle_id = None

    when, date_error = parse_date(form.get("return_date"))
    if date_error:
        errors.append(date_error)

    note = (form.get("note") or "").strip()
    values = {
        "qty": qty, "credit_rate": credit_rate, "vehicle_id": vehicle_id, "when": when,
        "note": note or None,
        # shown again if something is wrong
        "qty_text": (form.get("qty") or "").strip(),
        "credit_rate_text": (form.get("credit_rate") or "").strip(),
        "vehicle_label": profile_label("vehicles", vehicle_id) if vehicle_id else "",
        "date_text": (form.get("return_date") or "").strip(), "note_text": note,
    }
    return values, errors


def create_return(line_id: int, v: dict) -> int:
    return execute(
        "INSERT INTO sale_returns (sale_line_id, qty, credit_rate, back_to_vehicle_id, return_date, note) "
        "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
        [line_id, v["qty"], v["credit_rate"], v["vehicle_id"], v["when"], v["note"]])[0]["id"]


def update_return(return_id: int, v: dict) -> None:
    execute("UPDATE sale_returns SET qty = %s, credit_rate = %s, back_to_vehicle_id = %s, "
            "return_date = %s, note = %s WHERE id = %s",
            [v["qty"], v["credit_rate"], v["vehicle_id"], v["when"], v["note"], return_id])


def hide_return(return_id: int) -> None:
    execute("UPDATE sale_returns SET is_deleted = true WHERE id = %s", [return_id])
