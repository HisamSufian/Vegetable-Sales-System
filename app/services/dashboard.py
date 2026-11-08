"""The numbers on the Home page."""
from datetime import date, timedelta

from app.services import calc
from app.services.reports import unsettled_summary
from app.services.sales import bills_for_day, pending_count
from app.services.stock import stock_overview
from app.services.totals import customer_cheques_in_hand, issued_cheques


def dashboard(today: date, today_day: dict | None) -> dict:
    sales_today = (sum((b["totals"]["total"] for b in bills_for_day(today_day["id"])), calc.ZERO)
                   if today_day else calc.ZERO)
    stock = stock_overview()
    soon = today + timedelta(days=7)
    customer_due = [c for c in customer_cheques_in_hand() if c["due_date"] <= soon]   # includes overdue
    issued_due = [c for c in issued_cheques() if c["due_date"] <= soon]
    return {
        "sales_today": sales_today,
        "cartons_left": sum(r["stock_left"] for r in stock if r["stock_left"] > 0),
        "negative_rows": sum(1 for r in stock if r["stock_left"] < 0),
        "customer_due": customer_due, "customer_due_total": sum((c["amount"] for c in customer_due), calc.ZERO),
        "issued_due": issued_due, "issued_due_total": sum((c["amount"] for c in issued_due), calc.ZERO),
        "unsettled": unsettled_summary(), "pending": pending_count(),
    }
