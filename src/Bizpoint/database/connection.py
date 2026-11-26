
from pathlib import Path

from sqlalchemy import URL, create_engine, event
from sqlalchemy.orm import sessionmaker

from Bizpoint.database.base import Base

# 1. DATABASE LOCATION

PROJECT_ROOT = Path(__file__).resolve().parents[3]

DATABASE_DIR = PROJECT_ROOT / "database"

DATABASE_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_PATH = DATABASE_DIR / "bizpoint.db"


# 2. DATABASE CONNECTION URL

DATABASE_URL = URL.create(
    drivername="sqlite",
    database=str(DATABASE_PATH),
)


# 3. CREATE SQLALCHEMY ENGINE

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)


# 4. ENABLE SQLITE FOREIGN KEY ENFORCEMENT

@event.listens_for(engine, "connect")
def enable_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# 5. CREATE DATABASE SESSION FACTORY

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)
