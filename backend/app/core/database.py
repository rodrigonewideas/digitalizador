"""Engine e sessão SQLAlchemy 2.x.

Os modelos ORM serão adicionados em app/models e herdarão de Base. Enquanto isso,
o schema é criado pelas migrations Alembic (fonte: database/schema.sql).
"""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

_settings = get_settings()

engine = create_engine(_settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


class Base(DeclarativeBase):
    """Base declarativa dos modelos ORM."""


def get_session() -> Iterator[Session]:
    """Dependency do FastAPI: uma sessão por requisição."""
    with SessionLocal() as session:
        yield session
