"""Business details (name, phone, statement footer) from the one-row settings table."""
from app.db import execute, query


def get_business() -> dict:
    return query("SELECT * FROM settings WHERE id = 1")[0]


def save_business(name: str, phone: str, footer: str) -> None:
    execute("UPDATE settings SET business_name = %s, business_phone = %s, "
            "statement_footer = %s WHERE id = 1", [name, phone, footer])
