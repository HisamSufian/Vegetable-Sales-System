"""Opening balances (old debts) for a farm owner or a customer."""
from decimal import Decimal

from app.db import execute, query

COLUMN = {"farm_owner": "farm_owner_id", "customer": "customer_id"}


def list_openings(party_type: str, party_id: int) -> list[dict]:
    return query(f"SELECT * FROM opening_balances WHERE {COLUMN[party_type]} = %s "
                 f"AND is_deleted = false ORDER BY balance_date DESC, id DESC", [party_id])


def total(party_type: str, party_id: int) -> Decimal:
    rows = query(f"SELECT COALESCE(SUM(amount), 0) AS total FROM opening_balances "
                 f"WHERE {COLUMN[party_type]} = %s AND is_deleted = false", [party_id])
    return Decimal(rows[0]["total"])


def get_opening(opening_id: int) -> dict | None:
    rows = query("SELECT * FROM opening_balances WHERE id = %s AND is_deleted = false", [opening_id])
    return rows[0] if rows else None


def create_opening(party_type: str, party_id: int, amount: Decimal, when, note: str | None) -> int:
    farm = party_id if party_type == "farm_owner" else None
    customer = party_id if party_type == "customer" else None
    return execute(
        "INSERT INTO opening_balances (party_type, farm_owner_id, customer_id, amount, balance_date, note) "
        "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
        [party_type, farm, customer, amount, when, note])[0]["id"]


def update_opening(opening_id: int, amount: Decimal, when, note: str | None) -> None:
    execute("UPDATE opening_balances SET amount = %s, balance_date = %s, note = %s WHERE id = %s",
            [amount, when, note, opening_id])


def hide_opening(opening_id: int) -> None:
    execute("UPDATE opening_balances SET is_deleted = true WHERE id = %s", [opening_id])
