"""Reads every table for the backup, and remembers when a backup was last downloaded."""
from datetime import datetime

from psycopg import sql

from app.db import execute, pool, query
from app.services.backup_files import build_zip
from app.timeutil import DUBAI


def read_all_tables() -> dict[str, tuple[list[str], list[dict]]]:
    names = [r["table_name"] for r in query(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' ORDER BY table_name")]
    tables = {}
    with pool.connection() as conn:
        for name in names:
            cursor = conn.execute(sql.SQL("SELECT * FROM {} ORDER BY 1").format(sql.Identifier(name)))
            columns = [c.name for c in cursor.description]
            tables[name] = (columns, cursor.fetchall())
    return tables


def make_backup() -> tuple[bytes, str]:
    """Returns (zip file bytes, suggested file name) and records the time."""
    when = datetime.now(DUBAI)
    data = build_zip(read_all_tables(), when)
    execute("UPDATE settings SET last_backup_at = now() WHERE id = 1")
    return data, f"sufi-backup-{when:%Y-%m-%d-%H%M}.zip"
