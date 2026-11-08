"""Money calculations in ONE place (no database here, so they are easy to test).
All amounts are AED with 2 decimals, using exact Decimal numbers (never floats)."""
import re
from decimal import Decimal, InvalidOperation

CENTS = Decimal("0.01")
ZERO = Decimal("0.00")
MAX_AMOUNT = Decimal("1000000000")


def line_amount(qty: int, rate: Decimal | None) -> Decimal:
    """cartons x rate. A line whose rate is still empty (Rate pending) counts as 0."""
    if rate is None:
        return ZERO
    return (Decimal(qty) * rate).quantize(CENTS)


def bill_totals(lines: list[dict], discount: Decimal, returns: list[dict] | None = None) -> dict:
    """lines: dicts with 'qty' and 'rate'. returns: dicts with 'qty' and 'credit_rate'.
    total = subtotal - returns credit - discount."""
    subtotal = sum((line_amount(l["qty"], l["rate"]) for l in lines), ZERO)
    returns_credit = sum((line_amount(r["qty"], r["credit_rate"]) for r in (returns or [])), ZERO)
    return {
        "subtotal": subtotal,
        "returns_credit": returns_credit,
        "discount": discount,
        "total": subtotal - returns_credit - discount,
        "pending_count": sum(1 for l in lines if l["rate"] is None),
    }


def parse_money(text, *, blank=None) -> tuple[Decimal | None, str | None]:
    """Reads an amount typed by the user. Returns (value, error_message).
    Empty text gives `blank`. Negative numbers, more than 2 decimals,
    and non-numbers are rejected."""
    cleaned = (text or "").strip().replace(",", "")
    if cleaned == "":
        return blank, None
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None, "Enter a number like 25 or 25.50."
    if not value.is_finite():
        return None, "Enter a number like 25 or 25.50."
    if value < 0:
        return None, "The amount cannot be negative."
    if value >= MAX_AMOUNT:
        return None, "That amount is too large."
    if value != value.quantize(CENTS):
        return None, "Use at most 2 decimals (for example 25.50)."
    return value.quantize(CENTS), None


def parse_signed_int(text) -> int | None:
    """'5', '+5' or '-3' -> a whole number. Anything else (blank, 1.5, text) -> None."""
    cleaned = (text or "").strip().replace(" ", "")
    if re.fullmatch(r"[+-]?\d{1,9}", cleaned):
        return int(cleaned)
    return None


def farm_balance(settled: Decimal, opening: Decimal, costs_borne_by_owner: Decimal, payments: Decimal) -> Decimal:
    """What I owe a farm owner (negative = he owes me, for example an advance):
    settled amounts + opening balance - extra costs he bears - payments (cleared)."""
    return settled + opening - costs_borne_by_owner - payments


def parse_signed_money(text) -> tuple[Decimal | None, str | None]:
    """Like parse_money but a leading + or - is allowed, and 0 is not."""
    cleaned = (text or "").strip().replace(",", "").replace(" ", "")
    sign = Decimal(1)
    if cleaned.startswith("-"):
        sign, cleaned = Decimal(-1), cleaned[1:]
    elif cleaned.startswith("+"):
        cleaned = cleaned[1:]
    value, error = parse_money(cleaned, blank=None)
    if error:
        return None, error
    if value is None:
        return None, "Enter an amount like 1000 or -200."
    if value == 0:
        return None, "The amount cannot be 0."
    return (value * sign).quantize(CENTS), None


def customer_balance(bills_total: Decimal, opening: Decimal, payments: Decimal, writeoffs: Decimal) -> Decimal:
    """What a customer owes me (negative = I owe him, for example an overpayment):
    bills (after returns and discounts) + opening balance - payments (cleared) - write-offs."""
    return bills_total + opening - payments - writeoffs


def profit(sales: Decimal, discounts: Decimal, returns: Decimal, writeoffs: Decimal,
           settled: Decimal, costs_i_bear: Decimal, expenses: Decimal) -> dict:
    """Profit = customer sales after discounts and returns
                - write-offs (a loss) - farm owner settled amounts - extra costs I bear - general expenses."""
    net_sales = sales - discounts - returns
    return {"net_sales": net_sales,
            "profit": net_sales - writeoffs - settled - costs_i_bear - expenses}
