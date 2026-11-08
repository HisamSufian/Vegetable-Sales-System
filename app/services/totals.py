"""Totals: Payable, Paid, Receivable, Received, and the two cheque lists.
Balances use the same formulas (calc.py) as the farm owner and customer profiles."""
from datetime import date
from decimal import Decimal

from app.db import query
from app.services import calc
from app.services.sales import all_bills_with_totals
from app.timeutil import dubai_today


def _grouped(sql: str) -> dict[int, Decimal]:
    return {r["pid"]: Decimal(r["total"]) for r in query(sql)}


def _range(column: str, d_from: date | None, d_to: date | None) -> tuple[str, list]:
    clauses, params = [], []
    if d_from:
        clauses.append(f"{column} >= %s")
        params.append(d_from)
    if d_to:
        clauses.append(f"{column} <= %s")
        params.append(d_to)
    return ((" AND " + " AND ".join(clauses)) if clauses else ""), params


# ---------------- balances per person ----------------
def owner_balances() -> list[dict]:
    """What I owe each farm owner (negative = he owes me, an advance)."""
    owners = query("SELECT id, name FROM farm_owners WHERE is_deleted = false ORDER BY lower(name)")
    settled: dict[int, Decimal] = {}
    for l in query("SELECT t.farm_owner_id AS pid, sl.qty, sl.rate FROM settlement_lines sl "
                   "JOIN trip_rows r ON r.id = sl.trip_row_id JOIN trips t ON t.id = r.trip_id "
                   "WHERE sl.is_deleted = false AND r.is_deleted = false AND t.is_deleted = false"):
        settled[l["pid"]] = settled.get(l["pid"], calc.ZERO) + calc.line_amount(l["qty"], l["rate"])
    opening = _grouped("SELECT farm_owner_id AS pid, SUM(amount) AS total FROM opening_balances "
                       "WHERE party_type = 'farm_owner' AND is_deleted = false GROUP BY farm_owner_id")
    costs = _grouped("SELECT farm_owner_id AS pid, SUM(amount) AS total FROM farm_owner_costs "
                     "WHERE borne_by = 'farm_owner' AND is_deleted = false GROUP BY farm_owner_id")
    paid = _grouped("SELECT farm_owner_id AS pid, SUM(amount) AS total FROM farm_owner_payments "
                    "WHERE is_deleted = false AND (method <> 'cheque' OR cheque_status = 'cleared') "
                    "GROUP BY farm_owner_id")
    return [{"id": o["id"], "name": o["name"],
             "balance": calc.farm_balance(settled.get(o["id"], calc.ZERO), opening.get(o["id"], calc.ZERO),
                                          costs.get(o["id"], calc.ZERO), paid.get(o["id"], calc.ZERO))}
            for o in owners]


def customer_balances() -> list[dict]:
    """What each customer owes me (negative = overpaid). Walk-in / Cash is never included."""
    customers = query("SELECT id, name FROM customers WHERE is_deleted = false AND is_walk_in = false "
                      "ORDER BY lower(name)")
    billed: dict[int, Decimal] = {}
    for b in all_bills_with_totals():
        if not b["is_walk_in"]:
            billed[b["customer_id"]] = billed.get(b["customer_id"], calc.ZERO) + b["totals"]["total"]
    opening = _grouped("SELECT customer_id AS pid, SUM(amount) AS total FROM opening_balances "
                       "WHERE party_type = 'customer' AND is_deleted = false GROUP BY customer_id")
    paid = _grouped("SELECT customer_id AS pid, SUM(amount) AS total FROM customer_payments "
                    "WHERE is_deleted = false AND (method <> 'cheque' OR cheque_status = 'cleared') "
                    "GROUP BY customer_id")
    writeoffs = _grouped("SELECT customer_id AS pid, SUM(amount) AS total FROM customer_adjustments "
                         "WHERE is_deleted = false GROUP BY customer_id")
    return [{"id": c["id"], "name": c["name"],
             "balance": calc.customer_balance(billed.get(c["id"], calc.ZERO), opening.get(c["id"], calc.ZERO),
                                              paid.get(c["id"], calc.ZERO), writeoffs.get(c["id"], calc.ZERO))}
            for c in customers]


def split_balances(items: list[dict]) -> tuple[list[dict], list[dict]]:
    """(people with a positive balance, people with a negative balance), biggest first.
    They are kept apart on purpose: a credit never hides a debt."""
    positive = sorted((i for i in items if i["balance"] > 0), key=lambda i: i["balance"], reverse=True)
    negative = sorted(({**i, "balance": -i["balance"]} for i in items if i["balance"] < 0),
                      key=lambda i: i["balance"], reverse=True)
    return positive, negative


# ---------------- paid / received (can be filtered by date) ----------------
def paid_total(d_from: date | None = None, d_to: date | None = None) -> Decimal:
    """Payments I made to farm owners (cash/bank/other, and cleared cheques)."""
    clause, params = _range("pay_date", d_from, d_to)
    return Decimal(query("SELECT COALESCE(SUM(amount), 0) AS total FROM farm_owner_payments "
                         "WHERE is_deleted = false AND (method <> 'cheque' OR cheque_status = 'cleared')" + clause,
                         params)[0]["total"])


def received_total(d_from: date | None = None, d_to: date | None = None) -> Decimal:
    """Money customers paid me: cleared payments, plus Walk-in / Cash sales (paid on the spot)."""
    clause, params = _range("pay_date", d_from, d_to)
    payments = Decimal(query("SELECT COALESCE(SUM(amount), 0) AS total FROM customer_payments "
                             "WHERE is_deleted = false AND (method <> 'cheque' OR cheque_status = 'cleared')" + clause,
                             params)[0]["total"])
    walk_in = sum((b["totals"]["total"] for b in all_bills_with_totals()
                   if b["is_walk_in"] and (d_from is None or b["day_date"] >= d_from)
                   and (d_to is None or b["day_date"] <= d_to)), calc.ZERO)
    return payments + walk_in


# ---------------- cheque lists ----------------
def _flag_due(rows: list[dict]) -> list[dict]:
    today = dubai_today()
    for r in rows:
        r["days_left"] = (r["due_date"] - today).days
        r["overdue"] = r["days_left"] < 0
    return rows


def customer_cheques_in_hand() -> list[dict]:
    """Pending customer cheques (Cheques in hand): not yet counted as received."""
    return _flag_due(query(
        "SELECT p.id, p.amount, p.cheque_no, p.bank, p.due_date, c.id AS party_id, c.name AS party_name "
        "FROM customer_payments p JOIN customers c ON c.id = p.customer_id "
        "WHERE p.is_deleted = false AND p.method = 'cheque' AND p.cheque_status = 'pending' "
        "ORDER BY p.due_date, p.id"))


def issued_cheques() -> list[dict]:
    """Pending cheques I gave to farm owners (Cheques I issued): not yet counted as paid."""
    return _flag_due(query(
        "SELECT p.id, p.amount, p.cheque_no, p.bank, p.due_date, f.id AS party_id, f.name AS party_name "
        "FROM farm_owner_payments p JOIN farm_owners f ON f.id = p.farm_owner_id "
        "WHERE p.is_deleted = false AND p.method = 'cheque' AND p.cheque_status = 'pending' "
        "ORDER BY p.due_date, p.id"))


def totals_overview(d_from: date | None = None, d_to: date | None = None) -> dict:
    owed_by_me, advances = split_balances(owner_balances())
    owed_to_me, credits = split_balances(customer_balances())
    hand, issued = customer_cheques_in_hand(), issued_cheques()
    return {
        "payable": sum((o["balance"] for o in owed_by_me), calc.ZERO), "payable_list": owed_by_me,
        "advances": sum((o["balance"] for o in advances), calc.ZERO), "advances_list": advances,
        "receivable": sum((c["balance"] for c in owed_to_me), calc.ZERO), "receivable_list": owed_to_me,
        "credits": sum((c["balance"] for c in credits), calc.ZERO), "credits_list": credits,
        "paid": paid_total(d_from, d_to), "received": received_total(d_from, d_to),
        "in_hand": hand, "in_hand_total": sum((c["amount"] for c in hand), calc.ZERO),
        "issued": issued, "issued_total": sum((c["amount"] for c in issued), calc.ZERO),
    }
