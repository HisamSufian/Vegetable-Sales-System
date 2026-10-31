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


def bill_totals(lines: list[dict], discount: Decimal) -> dict:
    """lines: dicts with 'qty' and 'rate'. total = subtotal - discount."""
    subtotal = sum((line_amount(l["qty"], l["rate"]) for l in lines), ZERO)
    return {
        "subtotal": subtotal,
        "discount": discount,
        "total": subtotal - discount,
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
