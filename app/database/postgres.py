import logging
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config.settings import settings

logger = logging.getLogger(__name__)

engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator:
    """Dependency for yielding database sessions per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_postgres_connection() -> bool:
    """Verifies active connection to PostgreSQL by executing a test query."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"PostgreSQL connection check failed: {e}")
        return False
