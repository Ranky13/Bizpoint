
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine, text
from sqlalchemy.orm import sessionmaker

from Bizpoint.database.base import Base


# Locate the Bizpoint project root.
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Load environment variables from the project root.
ENV_FILE = PROJECT_ROOT / ".env"
load_dotenv(ENV_FILE)


# Read PostgreSQL configuration.
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

required_settings = {
    "DB_HOST": DB_HOST,
    "DB_NAME": DB_NAME,
    "DB_USER": DB_USER,
    "DB_PASSWORD": DB_PASSWORD,
}

missing_settings = [
    name for name, value in required_settings.items()
    if not value
]

if missing_settings:
    raise RuntimeError(
        f"Missing database settings: {', '.join(missing_settings)}"
    )


# Build the PostgreSQL connection URL safely.
DATABASE_URL = URL.create(
    drivername="postgresql+psycopg",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=int(DB_PORT),
    database=DB_NAME,
)


# Create the SQLAlchemy engine.
engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)


# Create database sessions.
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)
