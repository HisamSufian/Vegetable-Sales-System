from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

# URL.create() builds the connection address safely, so passwords containing
# special characters (@ # / etc.) work without any manual encoding.
database_url = URL.create(
    drivername="postgresql+psycopg2",
    username=settings.db_user,
    password=settings.db_password,
    host=settings.db_host,
    port=settings.db_port,
    database=settings.db_name,
)

engine = create_engine(
    database_url,
    pool_pre_ping=True,   # drop dead connections automatically
    pool_size=3,          # keep small: the free tier allows few connections
    max_overflow=2,
    connect_args={"sslmode": "require"},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: gives each request its own database session
    and always closes it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
