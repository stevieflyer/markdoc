"""
Database initialization and session management.
"""

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .models import Base

# Database URL - using SQLite
DATABASE_URL = "sqlite:///./markdoc.db"

# Create engine
engine = create_engine(
    DATABASE_URL, echo=False, connect_args={"check_same_thread": False}
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database, create all tables"""
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        # Table already exists or other error - this is fine
        # Just log and continue
        import logging

        logging.debug(f"Database initialization: {e}")


def get_db():
    """Get database session (for use in Streamlit or other contexts)"""
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise


@contextmanager
def get_db_context():
    """Context manager for database sessions"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
