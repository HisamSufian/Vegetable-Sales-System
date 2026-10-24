"""Database connection (Supabase Postgres) with a small connection pool."""
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import settings

pool = ConnectionPool(
    kwargs={
        "host": settings.db_host,
        "port": settings.db_port,
        "dbname": settings.db_name,
        "user": settings.db_user,
        "password": settings.db_password,
        "sslmode": "require",
        "row_factory": dict_row,     # rows come back as dicts: row["name"]
        "prepare_threshold": None,   # safe with Supabase's pooler
    },
    min_size=1,
    max_size=3,                      # free tier allows only a few connections
    open=False,                      # opened when the app starts (see main.py)
    timeout=15,
    check=ConnectionPool.check_connection,   # replaces dead connections automatically
)


def query(sql: str, params=None) -> list[dict]:
    """Run a SELECT and return all rows as a list of dicts."""
    with pool.connection() as conn:
        return conn.execute(sql, params).fetchall()


def execute(sql: str, params=None) -> list[dict]:
    """Run an INSERT / UPDATE / DELETE. Saved (committed) when it succeeds,
    undone if it fails. Returns the rows of a RETURNING clause, if any."""
    with pool.connection() as conn:
        cursor = conn.execute(sql, params)
        return cursor.fetchall() if cursor.description else []
