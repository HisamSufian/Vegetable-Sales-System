"""Settlement lines: what I owe a farm owner for the cartons of each trip row.
The rate is my own decision. The only rule: settled cartons of a row cannot
exceed its net sold cartons (sold minus returned)."""
from app.db import execute, query
from app.services import calc
from app.services.stock import SOLD_BY_ROW, WASTED_BY_ROW
from app.services.stock_entries import parse_date
from app.services.trips import to_int
from app.timeutil import dubai_today

ROWS_BASE = f"""
    SELECT r.id AS trip_row_id, r.trip_id, veg.name AS vegetable_name, r.arrived_qty,
           COALESCE(sold.qty, 0) AS net_sold, COALESCE(w.qty, 0) AS wasted_qty
    FROM trip_rows r
    JOIN vegetables veg ON veg.id = r.vegetable_id
    LEFT JOIN {SOLD_BY_ROW} sold ON sold.trip_row_id = r.id
    LEFT JOIN {WASTED_BY_ROW} w ON w.trip_row_id = r.id
    WHERE r.is_deleted = false
"""


def get_line(line_id: int) -> dict | None:
    rows = query("SELECT * FROM settlement_lines WHERE id = %s AND is_deleted = false", [line_id])
    return rows[0] if rows else None


def settlement_overview(trip_id: int) -> dict:
    """Every row of the trip with its settlement lines and numbers."""
    rows = query(ROWS_BASE + " AND r.trip_id = %s ORDER BY r.id", [trip_id])
    lines = query("SELECT * FROM settlement_lines WHERE trip_row_id = ANY(%s) AND is_deleted = false "
                  "ORDER BY id", [[r["trip_row_id"] for r in rows]])
    by_row: dict[int, list[dict]] = {}
    for l in lines:
        l["amount"] = calc.line_amount(l["qty"], l["rate"])
        by_row.setdefault(l["trip_row_id"], []).append(l)
    settled_amount = calc.ZERO
    for r in rows:
        r["lines"] = by_row.get(r["trip_row_id"], [])
        r["settled_qty"] = sum(l["qty"] for l in r["lines"])
        r["amount"] = sum((l["amount"] for l in r["lines"]), calc.ZERO)
        r["remaining"] = r["net_sold"] - r["settled_qty"]          # sold but not yet settled
        r["over"] = max(0, r["settled_qty"] - r["net_sold"])       # settled more than sold
        settled_amount += r["amount"]
    return {"rows": rows, "settled_amount": settled_amount}


def settle_problems(trip_id: int) -> dict:
    """For the Mark settled warning (never a block)."""
    rows = settlement_overview(trip_id)["rows"]
    return {"unsettled": [r for r in rows if r["remaining"] > 0],
            "over": [r for r in rows if r["over"] > 0]}


def check_line_form(form: dict, trip_id: int, exclude_line_id: int | None = None) -> tuple[dict, list[str]]:
    """Validates a settlement line. Blocks cartons above what is left to settle."""
    errors = []
    row_id = to_int(form.get("trip_row_id"))
    found = query(ROWS_BASE + " AND r.id = %s AND r.trip_id = %s", [row_id, trip_id]) if row_id else []
    row = found[0] if found else None
    if row is None:
        errors.append("Please choose a vegetable row.")

    qty = to_int(form.get("qty"))
    if qty is None or qty < 1:
        errors.append("Enter the cartons as a whole number, 1 or more.")

    rate, rate_error = calc.parse_money(form.get("rate"), blank=None)
    if rate_error:
        errors.append(f"Rate: {rate_error}")
    elif rate is None:
        errors.append("Enter the rate per carton.")

    when, date_error = parse_date(form.get("line_date") or dubai_today().isoformat())
    if date_error:
        errors.append(date_error)

    if row and qty and qty >= 1:
        settled_other = int(query(
            "SELECT COALESCE(SUM(qty), 0) AS n FROM settlement_lines "
            "WHERE trip_row_id = %s AND is_deleted = false AND id <> %s",
            [row_id, exclude_line_id or 0])[0]["n"])
        available = row["net_sold"] - settled_other
        if qty > available:
            errors.append(f"Only {max(available, 0)} cartons can still be settled for "
                          f"{row['vegetable_name']} (sold {row['net_sold']} after returns, "
                          f"already settled {settled_other}). If the sold count is wrong, "
                          f"fix the sale or return first.")
    values = {"trip_row_id": row_id if row else None, "qty": qty, "rate": rate, "when": when,
              "qty_text": (form.get("qty") or "").strip(), "rate_text": (form.get("rate") or "").strip(),
              "date_text": (form.get("line_date") or "").strip()}
    return values, errors


def create_line(v: dict) -> int:
    return execute("INSERT INTO settlement_lines (trip_row_id, qty, rate, line_date) "
                   "VALUES (%s, %s, %s, %s) RETURNING id",
                   [v["trip_row_id"], v["qty"], v["rate"], v["when"]])[0]["id"]


def update_line(line_id: int, v: dict) -> None:
    execute("UPDATE settlement_lines SET qty = %s, rate = %s, line_date = %s WHERE id = %s",
            [v["qty"], v["rate"], v["when"], line_id])


def hide_line(line_id: int) -> None:
    execute("UPDATE settlement_lines SET is_deleted = true WHERE id = %s", [line_id])
