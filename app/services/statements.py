"""Statements: print-friendly summaries for a farm owner or a customer.
Both are built from a list of dated 'entries' and calc.running_balance, so the closing balance
always agrees with the profile page.
The farm owner statement NEVER contains selling rates, customer names, costs I bear, or profit."""
from datetime import date
from decimal import Decimal

from app.db import query
from app.services import calc, opening
from app.services.farm_money import METHOD_LABELS
from app.services.profiles import get_kind, get_profile


def _entry(when: date, rank: int, entry_id: int, text: str, plus: Decimal = calc.ZERO,
           minus: Decimal = calc.ZERO) -> dict:
    return {"date": when, "rank": rank, "id": entry_id, "text": text, "plus": plus, "minus": minus}


def _payment_text(p: dict) -> str:
    text = METHOD_LABELS.get(p["method"], p["method"])
    if p["method"] == "cheque":
        text += f" {p['cheque_no']}"
    return text


def _in_range(rows: list[dict], key: str, d_from: date, d_to: date) -> list[dict]:
    return [r for r in rows if d_from <= r[key] <= d_to]


# ======================= farm owner =======================
def farm_owner_statement(owner_id: int, d_from: date, d_to: date) -> dict:
    owner = get_profile(get_kind("farm-owners"), owner_id)

    lines = query("""
        SELECT sl.id, sl.qty, sl.rate, sl.line_date, r.id AS trip_row_id, veg.name AS vegetable_name,
               t.id AS trip_id, t.trip_no, d.day_date AS arrival_date, v.plate_number
        FROM settlement_lines sl
        JOIN trip_rows r ON r.id = sl.trip_row_id
        JOIN vegetables veg ON veg.id = r.vegetable_id
        JOIN trips t ON t.id = r.trip_id
        JOIN days d ON d.id = t.day_id
        JOIN vehicles v ON v.id = t.vehicle_id
        WHERE t.farm_owner_id = %s AND sl.is_deleted = false AND r.is_deleted = false AND t.is_deleted = false
        ORDER BY d.day_date, t.id, r.id, sl.line_date, sl.id
    """, [owner_id])
    for l in lines:
        l["amount"] = calc.line_amount(l["qty"], l["rate"])

    costs = query("SELECT c.id, c.cost_date, c.amount, c.note, t.trip_no FROM farm_owner_costs c "
                  "LEFT JOIN trips t ON t.id = c.trip_id WHERE c.farm_owner_id = %s AND c.borne_by = 'farm_owner' "
                  "AND c.is_deleted = false ORDER BY c.cost_date, c.id", [owner_id])
    payments = query("SELECT * FROM farm_owner_payments WHERE farm_owner_id = %s AND is_deleted = false "
                     "AND (method <> 'cheque' OR cheque_status = 'cleared') ORDER BY pay_date, id", [owner_id])
    pending_cheques = query("SELECT * FROM farm_owner_payments WHERE farm_owner_id = %s AND is_deleted = false "
                            "AND method = 'cheque' AND cheque_status = 'pending' AND pay_date <= %s "
                            "ORDER BY due_date, id", [owner_id, d_to])
    openings = opening.list_openings("farm_owner", owner_id)

    # ---- the ledger, all time; calc.running_balance cuts it to the period ----
    entries = []
    grouped: dict[tuple, dict] = {}
    for l in lines:
        key = (l["trip_id"], l["line_date"])
        if key in grouped:
            grouped[key]["plus"] += l["amount"]
        else:
            grouped[key] = _entry(l["line_date"], 1, l["id"], f"{l['trip_no']} settlement", plus=l["amount"])
    entries += list(grouped.values())
    for o in openings:
        text = "Opening balance" + (f" ({o['note']})" if o["note"] else "")
        entries.append(_entry(o["balance_date"], 0, o["id"], text,
                              plus=max(o["amount"], calc.ZERO), minus=max(-o["amount"], calc.ZERO)))
    for c in costs:
        text = "Deducted: " + (c["note"] or "extra cost") + (f" ({c['trip_no']})" if c["trip_no"] else "")
        entries.append(_entry(c["cost_date"], 2, c["id"], text, minus=c["amount"]))
    for p in payments:
        text = "Payment (" + _payment_text(p) + ")" + (f": {p['note']}" if p["note"] else "")
        entries.append(_entry(p["pay_date"], 3, p["id"], text, minus=p["amount"]))
    ledger = calc.running_balance(entries, d_from, d_to)

    # ---- trip tables: trips that arrived in the period or were settled in it ----
    trips: dict[int, dict] = {}
    for t in query("SELECT t.id, t.trip_no, d.day_date AS arrival_date, v.plate_number FROM trips t "
                   "JOIN days d ON d.id = t.day_id JOIN vehicles v ON v.id = t.vehicle_id "
                   "WHERE t.farm_owner_id = %s AND t.is_deleted = false AND d.day_date BETWEEN %s AND %s",
                   [owner_id, d_from, d_to]):
        trips[t["id"]] = {**t, "lines": [], "wasted": []}
    for l in _in_range(lines, "line_date", d_from, d_to):
        trip = trips.setdefault(l["trip_id"], {"id": l["trip_id"], "trip_no": l["trip_no"],
                                               "arrival_date": l["arrival_date"],
                                               "plate_number": l["plate_number"], "lines": [], "wasted": []})
        trip["lines"].append(l)
    if trips:
        for w in query("SELECT r.trip_id, veg.name AS vegetable_name, SUM(w.qty) AS qty FROM wastage w "
                       "JOIN trip_rows r ON r.id = w.trip_row_id JOIN vegetables veg ON veg.id = r.vegetable_id "
                       "WHERE r.trip_id = ANY(%s) AND w.is_deleted = false AND r.is_deleted = false "
                       "GROUP BY r.trip_id, r.id, veg.name ORDER BY veg.name", [list(trips)]):
            trips[w["trip_id"]]["wasted"].append({"vegetable_name": w["vegetable_name"], "qty": int(w["qty"])})
    trip_list = sorted(trips.values(), key=lambda t: (t["arrival_date"], t["id"]))
    for t in trip_list:
        t["total_cartons"] = sum(l["qty"] for l in t["lines"])
        t["total_amount"] = sum((l["amount"] for l in t["lines"]), calc.ZERO)

    return {"owner": owner, "trips": trip_list, "ledger": ledger,
            "costs": _in_range(costs, "cost_date", d_from, d_to),
            "costs_total": sum((c["amount"] for c in _in_range(costs, "cost_date", d_from, d_to)), calc.ZERO),
            "payments": [{**p, "text": _payment_text(p)} for p in _in_range(payments, "pay_date", d_from, d_to)],
            "payments_total": sum((p["amount"] for p in _in_range(payments, "pay_date", d_from, d_to)), calc.ZERO),
            "pending_cheques": pending_cheques,
            "settled_total": sum((l["amount"] for l in _in_range(lines, "line_date", d_from, d_to)), calc.ZERO)}


# ======================= customer =======================
def customer_statement(customer_id: int, d_from: date, d_to: date) -> dict:
    customer = get_profile(get_kind("customers"), customer_id)

    bills = query("SELECT b.id, b.bill_no, b.discount_amount, d.day_date FROM sale_bills b "
                  "JOIN days d ON d.id = b.day_id WHERE b.customer_id = %s AND b.is_deleted = false "
                  "ORDER BY d.day_date, b.id", [customer_id])
    lines = query("SELECT l.id, l.bill_id, l.qty, l.rate, veg.name AS vegetable_name FROM sale_lines l "
                  "JOIN trip_rows r ON r.id = l.trip_row_id JOIN vegetables veg ON veg.id = r.vegetable_id "
                  "WHERE l.bill_id = ANY(%s) AND l.is_deleted = false ORDER BY l.id", [[b["id"] for b in bills]])
    by_bill: dict[int, list[dict]] = {}
    for l in lines:
        l["amount"] = calc.line_amount(l["qty"], l["rate"])
        by_bill.setdefault(l["bill_id"], []).append(l)

    returns = query("""
        SELECT rt.id, rt.qty, rt.credit_rate, rt.return_date, b.bill_no, veg.name AS vegetable_name
        FROM sale_returns rt
        JOIN sale_lines l ON l.id = rt.sale_line_id
        JOIN sale_bills b ON b.id = l.bill_id
        JOIN trip_rows r ON r.id = l.trip_row_id
        JOIN vegetables veg ON veg.id = r.vegetable_id
        WHERE b.customer_id = %s AND rt.is_deleted = false AND l.is_deleted = false AND b.is_deleted = false
        ORDER BY rt.return_date, rt.id
    """, [customer_id])
    for r in returns:
        r["amount"] = calc.line_amount(r["qty"], r["credit_rate"])
    payments = query("SELECT * FROM customer_payments WHERE customer_id = %s AND is_deleted = false "
                     "AND (method <> 'cheque' OR cheque_status = 'cleared') ORDER BY pay_date, id", [customer_id])
    cheques_in_hand = query("SELECT * FROM customer_payments WHERE customer_id = %s AND is_deleted = false "
                            "AND method = 'cheque' AND cheque_status = 'pending' AND pay_date <= %s "
                            "ORDER BY due_date, id", [customer_id, d_to])
    adjustments = query("SELECT * FROM customer_adjustments WHERE customer_id = %s AND is_deleted = false "
                        "ORDER BY adj_date, id", [customer_id])
    openings = opening.list_openings("customer", customer_id)

    # ---- the ledger (all time) ----
    entries = []
    for o in openings:
        text = "Opening balance" + (f" ({o['note']})" if o["note"] else "")
        entries.append(_entry(o["balance_date"], 0, o["id"], text,
                              plus=max(o["amount"], calc.ZERO), minus=max(-o["amount"], calc.ZERO)))
    bill_rows = []
    for b in bills:
        b_lines = by_bill.get(b["id"], [])
        totals = calc.bill_totals(b_lines, b["discount_amount"])          # returns are separate credits
        entries.append(_entry(b["day_date"], 1, b["id"], f"Bill {b['bill_no']}", plus=totals["total"]))
        bill_rows.append({**b, "lines": b_lines, "subtotal": totals["subtotal"], "net": totals["total"],
                          "pending_count": totals["pending_count"]})
    for r in returns:
        entries.append(_entry(r["return_date"], 2, r["id"], f"Return {r['qty']} {r['vegetable_name']} ({r['bill_no']})",
                              minus=r["amount"]))
    for p in payments:
        entries.append(_entry(p["pay_date"], 3, p["id"], "Payment received (" + _payment_text(p) + ")", minus=p["amount"]))
    for a in adjustments:
        entries.append(_entry(a["adj_date"], 4, a["id"], "Adjustment", minus=a["amount"]))
    ledger = calc.running_balance(entries, d_from, d_to)

    bills_in_range = _in_range(bill_rows, "day_date", d_from, d_to)
    return {"customer": customer, "ledger": ledger, "bills": bills_in_range,
            "returns": _in_range(returns, "return_date", d_from, d_to),
            "payments": [{**p, "text": _payment_text(p)} for p in _in_range(payments, "pay_date", d_from, d_to)],
            "adjustments": _in_range(adjustments, "adj_date", d_from, d_to),
            "cheques_in_hand": cheques_in_hand,
            "pending_lines": sum(b["pending_count"] for b in bills_in_range)}
