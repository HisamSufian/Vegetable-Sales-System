"""Profit. Exact for a date range when every sale has a rate and every sold carton is settled.
Which date counts for each part:
  sales and discounts      -> the Day of the bill
  returns                  -> the return date (so a late return never changes a closed month)
  settled amounts          -> the settlement line date
  costs, expenses, write-offs -> their own dates"""
from datetime import date
from decimal import Decimal

from app.db import query
from app.services import calc
from app.services.settlement import unsettled_trips


def _lines_total(rows: list[dict], rate_key: str = "rate") -> Decimal:
    return sum((calc.line_amount(r["qty"], r[rate_key]) for r in rows), calc.ZERO)


def _scalar(sql: str, params: list) -> Decimal:
    return Decimal(query(sql, params)[0]["total"])


def profit_for_range(d_from: date, d_to: date) -> dict:
    span = [d_from, d_to]
    sales = _lines_total(query(
        "SELECT l.qty, l.rate FROM sale_lines l JOIN sale_bills b ON b.id = l.bill_id "
        "JOIN days d ON d.id = b.day_id WHERE l.is_deleted = false AND b.is_deleted = false "
        "AND d.day_date BETWEEN %s AND %s", span))
    discounts = _scalar("SELECT COALESCE(SUM(b.discount_amount), 0) AS total FROM sale_bills b "
                        "JOIN days d ON d.id = b.day_id WHERE b.is_deleted = false "
                        "AND d.day_date BETWEEN %s AND %s", span)
    returns = _lines_total(query(
        "SELECT rt.qty, rt.credit_rate FROM sale_returns rt JOIN sale_lines l ON l.id = rt.sale_line_id "
        "JOIN sale_bills b ON b.id = l.bill_id WHERE rt.is_deleted = false AND l.is_deleted = false "
        "AND b.is_deleted = false AND rt.return_date BETWEEN %s AND %s", span), "credit_rate")
    writeoffs = _scalar("SELECT COALESCE(SUM(amount), 0) AS total FROM customer_adjustments "
                        "WHERE is_deleted = false AND adj_date BETWEEN %s AND %s", span)
    settled = _lines_total(query(
        "SELECT sl.qty, sl.rate FROM settlement_lines sl JOIN trip_rows r ON r.id = sl.trip_row_id "
        "JOIN trips t ON t.id = r.trip_id WHERE sl.is_deleted = false AND r.is_deleted = false "
        "AND t.is_deleted = false AND sl.line_date BETWEEN %s AND %s", span))
    costs_me = _scalar("SELECT COALESCE(SUM(amount), 0) AS total FROM farm_owner_costs "
                       "WHERE is_deleted = false AND borne_by = 'me' AND cost_date BETWEEN %s AND %s", span)
    expenses = _scalar("SELECT COALESCE(SUM(amount), 0) AS total FROM expenses "
                       "WHERE is_deleted = false AND expense_date BETWEEN %s AND %s", span)
    result = calc.profit(sales, discounts, returns, writeoffs, settled, costs_me, expenses)
    result.update(sales=sales, discounts=discounts, returns=returns, writeoffs=writeoffs,
                  settled=settled, costs_me=costs_me, expenses=expenses)
    return result


def trip_profit(trip_id: int) -> dict:
    """Profit of one trip. It ignores bill discounts and write-offs (they belong to bills, not trips)."""
    p = [trip_id]
    sales = _lines_total(query(
        "SELECT l.qty, l.rate FROM sale_lines l JOIN sale_bills b ON b.id = l.bill_id "
        "JOIN trip_rows r ON r.id = l.trip_row_id WHERE r.trip_id = %s AND l.is_deleted = false "
        "AND b.is_deleted = false", p))
    returns = _lines_total(query(
        "SELECT rt.qty, rt.credit_rate FROM sale_returns rt JOIN sale_lines l ON l.id = rt.sale_line_id "
        "JOIN sale_bills b ON b.id = l.bill_id JOIN trip_rows r ON r.id = l.trip_row_id "
        "WHERE r.trip_id = %s AND rt.is_deleted = false AND l.is_deleted = false AND b.is_deleted = false", p),
        "credit_rate")
    settled = _lines_total(query(
        "SELECT sl.qty, sl.rate FROM settlement_lines sl JOIN trip_rows r ON r.id = sl.trip_row_id "
        "WHERE r.trip_id = %s AND sl.is_deleted = false AND r.is_deleted = false", p))
    costs_me = _scalar("SELECT COALESCE(SUM(amount), 0) AS total FROM farm_owner_costs "
                       "WHERE trip_id = %s AND is_deleted = false AND borne_by = 'me'", p)
    expenses = _scalar("SELECT COALESCE(SUM(amount), 0) AS total FROM expenses "
                       "WHERE trip_id = %s AND is_deleted = false", p)
    result = calc.profit(sales, calc.ZERO, returns, calc.ZERO, settled, costs_me, expenses)
    result.update(sales=sales, returns=returns, settled=settled, costs_me=costs_me, expenses=expenses)
    return result


def unsettled_summary() -> dict:
    """Cartons sold but not yet in a settlement, over all trips not marked settled."""
    trips = unsettled_trips()
    return {"trips": trips, "cartons": sum(t["unsettled"] for t in trips)}
