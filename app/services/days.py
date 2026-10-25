"""Days: one record per calendar date, open (Current) or closed (Previous)."""
from datetime import date

from app.db import execute, query


def list_days() -> dict:
    """All days with how many trips and cartons they hold, split into
    Current (open) and Previous (closed), newest first."""
    rows = query("""
        SELECT d.*,
               COUNT(DISTINCT t.id) FILTER (WHERE t.is_deleted = false) AS trip_count,
               COALESCE(SUM(r.arrived_qty)
                        FILTER (WHERE r.is_deleted = false AND t.is_deleted = false), 0) AS cartons
        FROM days d
        LEFT JOIN trips t ON t.day_id = d.id
        LEFT JOIN trip_rows r ON r.trip_id = t.id
        WHERE d.is_deleted = false
        GROUP BY d.id
        ORDER BY d.day_date DESC
    """)
    return {
        "current": [d for d in rows if d["status"] == "open"],
        "previous": [d for d in rows if d["status"] == "closed"],
    }


def get_day(day_id: int) -> dict | None:
    rows = query("SELECT * FROM days WHERE id = %s AND is_deleted = false", [day_id])
    return rows[0] if rows else None


def get_day_by_date(day_date: date) -> dict | None:
    rows = query("SELECT * FROM days WHERE day_date = %s AND is_deleted = false", [day_date])
    return rows[0] if rows else None


def start_day(day_date: date) -> tuple[int, bool]:
    """Starts a Day. Returns (day_id, created). If that date already has a Day,
    nothing is created and the existing id is returned."""
    rows = execute("INSERT INTO days (day_date) VALUES (%s) "
                   "ON CONFLICT (day_date) DO NOTHING RETURNING id", [day_date])
    if rows:
        return rows[0]["id"], True
    return get_day_by_date(day_date)["id"], False


def set_day_status(day_id: int, status: str) -> None:
    execute("UPDATE days SET status = %s WHERE id = %s", [status, day_id])
