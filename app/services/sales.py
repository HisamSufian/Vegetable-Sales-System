"""Sale bills (one per customer per Day) and their lines."""
from decimal import Decimal

from app.db import execute, query
from app.services import calc, stock
from app.services.stock import SOLD_BY_ROW
from app.services.trips import to_int

BILL_SELECT = """
    SELECT b.*, c.name AS customer_name, c.is_walk_in, d.day_date, d.status AS day_status
    FROM sale_bills b
    JOIN customers c ON c.id = b.customer_id
    JOIN days d ON d.id = b.day_id
"""

LINE_SELECT = f"""
    SELECT l.*, veg.name AS vegetable_name, t.id AS trip_id, t.trip_no,
           d.day_date AS arrival_date, f.name AS farm_owner_name, v.plate_number,
           r.arrived_qty - COALESCE(s.qty, 0) AS stock_left
    FROM sale_lines l
    JOIN trip_rows r ON r.id = l.trip_row_id
    JOIN vegetables veg ON veg.id = r.vegetable_id
    JOIN trips t ON t.id = r.trip_id
    JOIN days d ON d.id = t.day_id
    JOIN farm_owners f ON f.id = t.farm_owner_id
    JOIN vehicles v ON v.id = l.from_vehicle_id
    LEFT JOIN {SOLD_BY_ROW} s ON s.trip_row_id = r.id
"""


# ---------------- bills ----------------
def get_bill(bill_id: int) -> dict | None:
    rows = query(BILL_SELECT + " WHERE b.id = %s AND b.is_deleted = false", [bill_id])
    return rows[0] if rows else None


def walk_in_customer_id() -> int:
    return query("SELECT id FROM customers WHERE is_walk_in = true")[0]["id"]


def customer_is_visible(customer_id: int) -> bool:
    return bool(query("SELECT 1 AS ok FROM customers WHERE id = %s AND is_deleted = false",
                      [customer_id]))


def get_or_create_bill(day_id: int, customer_id: int) -> tuple[int, bool]:
    """One bill per customer per Day: returns (bill_id, created).
    If the customer already has a bill today, that bill is returned."""
    rows = execute(
        "INSERT INTO sale_bills (day_id, customer_id) VALUES (%s, %s) "
        "ON CONFLICT (day_id, customer_id) WHERE is_deleted = false DO NOTHING RETURNING id",
        [day_id, customer_id])
    if rows:
        return rows[0]["id"], True
    existing = query("SELECT id FROM sale_bills WHERE day_id = %s AND customer_id = %s "
                     "AND is_deleted = false", [day_id, customer_id])
    return existing[0]["id"], False


def bills_for_day(day_id: int) -> list[dict]:
    """The Day's bills with their totals (calculated by calc.py)."""
    bills = query(BILL_SELECT + " WHERE b.day_id = %s AND b.is_deleted = false ORDER BY b.id", [day_id])
    lines = query("SELECT l.bill_id, l.qty, l.rate FROM sale_lines l "
                  "WHERE l.is_deleted = false AND l.bill_id = ANY(%s)", [[b["id"] for b in bills]])
    by_bill: dict[int, list[dict]] = {}
    for l in lines:
        by_bill.setdefault(l["bill_id"], []).append(l)
    for b in bills:
        b["line_count"] = len(by_bill.get(b["id"], []))
        b["totals"] = calc.bill_totals(by_bill.get(b["id"], []), b["discount_amount"])
    return bills


def update_bill_details(bill_id: int, discount: Decimal, note: str | None) -> None:
    execute("UPDATE sale_bills SET discount_amount = %s, note = %s WHERE id = %s",
            [discount, note, bill_id])


def hide_bill(bill_id: int) -> None:
    execute("UPDATE sale_bills SET is_deleted = true WHERE id = %s", [bill_id])


# ---------------- lines ----------------
def lines_for_bill(bill_id: int) -> list[dict]:
    lines = query(LINE_SELECT + " WHERE l.bill_id = %s AND l.is_deleted = false ORDER BY l.id", [bill_id])
    for l in lines:
        l["amount"] = calc.line_amount(l["qty"], l["rate"])
    return lines


def get_line(line_id: int) -> dict | None:
    rows = query(LINE_SELECT + " WHERE l.id = %s AND l.is_deleted = false", [line_id])
    return rows[0] if rows else None


def check_line_form(form: dict, current_key: str | None = None) -> tuple[dict, list[str]]:
    """Validates a sale line: stock chosen, whole cartons, optional rate."""
    errors = []
    key = stock.parse_key(form.get("stock_key"))
    option = stock.get_stock(*key) if key else None
    if option is None:
        errors.append("Please choose the stock to sell from.")
    qty = to_int(form.get("qty"))
    if qty is None or qty < 1:
        errors.append("Enter the cartons as a whole number, 1 or more.")
    rate, rate_error = calc.parse_money(form.get("rate"), blank=None)
    if rate_error:
        errors.append(f"Rate: {rate_error}")
    values = {
        "trip_row_id": key[0] if option else None, "vehicle_id": key[1] if option else None,
        "stock_key": stock.make_key(*key) if option else "",
        "stock_label": (stock.describe(option)["label"] + " | " + stock.describe(option)["sub"]) if option else "",
        "qty": qty, "rate": rate,
        "qty_text": (form.get("qty") or "").strip(), "rate_text": (form.get("rate") or "").strip(),
    }
    return values, errors


def add_line(bill_id: int, values: dict) -> int:
    return execute(
        "INSERT INTO sale_lines (bill_id, trip_row_id, from_vehicle_id, qty, rate) "
        "VALUES (%s, %s, %s, %s, %s) RETURNING id",
        [bill_id, values["trip_row_id"], values["vehicle_id"], values["qty"], values["rate"]])[0]["id"]


def update_line(line_id: int, values: dict) -> None:
    execute("UPDATE sale_lines SET trip_row_id = %s, from_vehicle_id = %s, qty = %s, rate = %s "
            "WHERE id = %s",
            [values["trip_row_id"], values["vehicle_id"], values["qty"], values["rate"], line_id])


def hide_line(line_id: int) -> None:
    execute("UPDATE sale_lines SET is_deleted = true WHERE id = %s", [line_id])


def negative_stock_warning(trip_row_id: int, vehicle_id: int) -> str | None:
    """A warning (never a block) when a row has been sold below zero."""
    row = stock.get_stock(trip_row_id, vehicle_id)
    if row and row["stock_left"] < 0:
        return (f"Warning: {row['vegetable_name']} from {row['trip_no']} is now at "
                f"{row['stock_left']} cartons (more sold than arrived). "
                f"Please check the arrival count on the trip.")
    return None


# ---------------- Rate pending ----------------
def pending_lines() -> list[dict]:
    return query("""
        SELECT l.id, l.qty, b.id AS bill_id, b.bill_no, d.day_date, c.name AS customer_name,
               veg.name AS vegetable_name, t.trip_no
        FROM sale_lines l
        JOIN sale_bills b ON b.id = l.bill_id
        JOIN days d ON d.id = b.day_id
        JOIN customers c ON c.id = b.customer_id
        JOIN trip_rows r ON r.id = l.trip_row_id
        JOIN vegetables veg ON veg.id = r.vegetable_id
        JOIN trips t ON t.id = r.trip_id
        WHERE l.rate IS NULL AND l.is_deleted = false AND b.is_deleted = false
        ORDER BY d.day_date DESC, b.id, l.id
    """)


def pending_count() -> int:
    return query("SELECT count(*) AS n FROM sale_lines l JOIN sale_bills b ON b.id = l.bill_id "
                 "WHERE l.rate IS NULL AND l.is_deleted = false AND b.is_deleted = false")[0]["n"]


def set_rate(line_id: int, rate: Decimal) -> None:
    execute("UPDATE sale_lines SET rate = %s WHERE id = %s", [rate, line_id])
