from fastapi import FastAPI
from sqlalchemy import text

from app.database import engine
from app.routers import consignments, expenses, inventory, masters, vegetables

app = FastAPI(title="Al Aweer Produce System")

app.include_router(vegetables.router)
app.include_router(masters.router)
app.include_router(consignments.router)
app.include_router(expenses.router)
app.include_router(inventory.router)


@app.get("/")
def health_check():
    return {"status": "running"}


@app.get("/db-check")
def db_check():
    """Confirms the app can reach Supabase."""
    with engine.connect() as conn:
        tables = conn.execute(text(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
        )).scalar()
    return {"database": "connected", "tables_found": tables}
