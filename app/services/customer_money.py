"""Customer money: payments (with received cheques), write-offs and the balance.
The balance formula itself lives in calc.py. Walk-in / Cash customers pay on the spot,
so they never have a balance: their sales count as received automatically."""
from decimal import Decimal

from app.db import execute, query
from app.services import calc, opening
from app.services.farm_money import (  # payments work the same way for customers
    CHEQUE_STATUSES, METHOD_LABELS, METHODS, check_payment_form,
)
from app.services.sales import bills_for_customer
from app.services.stock_entries import parse_date
from app.timeutil import dubai_today

__all__ = ["CHEQUE_STATUSES", "METHODS", "check_payment_form"]


# ---------------- payments ----------------
def customer_payments(customer_id: int) -> list[dict]:
    rows = query("SELECT * FROM customer_payments WHERE customer_id = %s AND is_deleted = false "
                 "ORDER BY pay_date DESC, id DESC", [customer_id])
    today = dubai_today()
    for p in rows:
        p["overdue"] = (p["method"] == "cheque" and p["cheque_status"] == "pending"
                        and p["due_date"] is not None and p["due_date"] < today)
    return rows


def get_payment(payment_id: int) -> dict | None:
    rows = query("SELECT * FROM customer_payments WHERE id = %s AND is_deleted = false", [payment_id])
    return rows[0] if rows else None


def create_payment(customer_id: int, v: dict) -> int:
    return execute(
        "INSERT INTO customer_payments (customer_id, amount, method, pay_date, note, cheque_no, bank, "
        "due_date, cheque_status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
        [customer_id, v["amount"], v["method"], v["when"], v["note"], v["cheque_no"], v["bank"],
         v["due"], v["status"]])[0]["id"]


def update_payment(payment_id: int, v: dict) -> None:
    execute("UPDATE customer_payments SET amount = %s, method = %s, pay_date = %s, note = %s, "
            "cheque_no = %s, bank = %s, due_date = %s, cheque_status = %s WHERE id = %s",
            [v["amount"], v["method"], v["when"], v["note"], v["cheque_no"], v["bank"],
             v["due"], v["status"], payment_id])


def set_cheque_status(payment_id: int, status: str) -> None:
    execute("UPDATE customer_payments SET cheque_status = %s WHERE id = %s AND method = 'cheque'",
            [status, payment_id])


def hide_payment(payment_id: int) -> None:
    execute("UPDATE customer_payments SET is_deleted = true WHERE id = %s", [payment_id])


# ---------------- write-offs ----------------
def customer_writeoffs(customer_id: int) -> list[dict]:
    return query("SELECT * FROM customer_adjustments WHERE customer_id = %s AND is_deleted = false "
                 "ORDER BY adj_date DESC, id DESC", [customer_id])


def get_writeoff(writeoff_id: int) -> dict | None:
    rows = query("SELECT * FROM customer_adjustments WHERE id = %s AND is_deleted = false", [writeoff_id])
    return rows[0] if rows else None


def check_writeoff_form(form: dict) -> tuple[dict, list[str]]:
    errors = []
    amount, amount_error = calc.parse_money(form.get("amount"), blank=None)
    if amount_error:
        errors.append(f"Amount: {amount_error}")
    elif amount is None or amount <= 0:
        errors.append("Enter an amount above 0.")
    reason = (form.get("reason") or "").strip()
    if not reason:
        errors.append("A reason is required for a write-off.")
    when, date_error = parse_date(form.get("adj_date") or dubai_today().isoformat())
    if date_error:
        errors.append(date_error)
    values = {"amount": amount, "reason": reason, "when": when,
              "amount_text": (form.get("amount") or "").strip(),
              "date_text": (form.get("adj_date") or "").strip(), "reason_text": reason}
    return values, errors


def create_writeoff(customer_id: int, v: dict) -> int:
    return execute("INSERT INTO customer_adjustments (customer_id, amount, reason, adj_date) "
                   "VALUES (%s, %s, %s, %s) RETURNING id",
                   [customer_id, v["amount"], v["reason"], v["when"]])[0]["id"]


def update_writeoff(writeoff_id: int, v: dict) -> None:
    execute("UPDATE customer_adjustments SET amount = %s, reason = %s, adj_date = %s WHERE id = %s",
            [v["amount"], v["reason"], v["when"], writeoff_id])


def hide_writeoff(writeoff_id: int) -> None:
    execute("UPDATE customer_adjustments SET is_deleted = true WHERE id = %s", [writeoff_id])


# ---------------- balance and profile page ----------------
def customer_returns(customer_id: int) -> list[dict]:
    rows = query("""
        SELECT rt.id, rt.qty, rt.credit_rate, rt.return_date, b.id AS bill_id, b.bill_no, veg.name AS vegetable_name
        FROM sale_returns rt
        JOIN sale_lines l ON l.id = rt.sale_line_id
        JOIN sale_bills b ON b.id = l.bill_id
        JOIN trip_rows r ON r.id = l.trip_row_id
        JOIN vegetables veg ON veg.id = r.vegetable_id
        WHERE b.customer_id = %s AND rt.is_deleted = false AND l.is_deleted = false AND b.is_deleted = false
        ORDER BY rt.return_date DESC, rt.id DESC
    """, [customer_id])
    for r in rows:
        r["credit_amount"] = calc.line_amount(r["qty"], r["credit_rate"])
    return rows


def customer_summary(customer_id: int, is_walk_in: bool, bills: list[dict]) -> dict:
    """All the numbers behind a customer's balance."""
    bills_total = sum((b["totals"]["total"] for b in bills), calc.ZERO)
    if is_walk_in:
        # Paid on the spot: counts as received, never a balance.
        return {"bills_total": bills_total, "balance": calc.ZERO, "received_auto": bills_total,
                "opening": calc.ZERO, "paid": calc.ZERO, "writeoffs": calc.ZERO,
                "cheques_pending_count": 0, "cheques_pending_total": calc.ZERO,
                "bounced_count": 0, "bounced_total": calc.ZERO}
    opening_total = opening.total("customer", customer_id)
    paid = Decimal(query(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM customer_payments "
        "WHERE customer_id = %s AND is_deleted = false AND (method <> 'cheque' OR cheque_status = 'cleared')",
        [customer_id])[0]["total"])
    writeoffs = Decimal(query(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM customer_adjustments "
        "WHERE customer_id = %s AND is_deleted = false", [customer_id])[0]["total"])
    cheques = {r["cheque_status"]: r for r in query(
        "SELECT cheque_status, count(*) AS n, COALESCE(SUM(amount), 0) AS total FROM customer_payments "
        "WHERE customer_id = %s AND is_deleted = false AND method = 'cheque' GROUP BY cheque_status",
        [customer_id])}
    pending, bounced = cheques.get("pending"), cheques.get("bounced")
    return {
        "bills_total": bills_total, "opening": opening_total, "paid": paid, "writeoffs": writeoffs,
        "received_auto": calc.ZERO,
        "cheques_pending_count": pending["n"] if pending else 0,
        "cheques_pending_total": Decimal(pending["total"]) if pending else calc.ZERO,
        "bounced_count": bounced["n"] if bounced else 0,
        "bounced_total": Decimal(bounced["total"]) if bounced else calc.ZERO,
        "balance": calc.customer_balance(bills_total, opening_total, paid, writeoffs),
    }


def customer_page(customer_id: int, is_walk_in: bool) -> dict:
    """Everything the customer profile page shows about money."""
    bills = bills_for_customer(customer_id, limit=None)
    data = {**customer_summary(customer_id, is_walk_in, bills), "bills": bills,
            "method_labels": METHOD_LABELS}
    if not is_walk_in:
        data.update(returns=customer_returns(customer_id), payments=customer_payments(customer_id),
                    writeoff_list=customer_writeoffs(customer_id),
                    openings=opening.list_openings("customer", customer_id))
    return data
