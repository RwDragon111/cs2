from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def sqlite_path_from_url(database_url: str) -> Path | None:
    if not database_url.startswith("sqlite:///"):
        return None
    return Path(database_url.replace("sqlite:///", "", 1))


def create_session_factory(database_url: str) -> sessionmaker[Session]:
    db_path = sqlite_path_from_url(database_url)
    if db_path is not None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        database_url,
        echo=False,
        future=True,
        connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {},
    )
    return sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


def init_db(database_url: str) -> sessionmaker[Session]:
    from app.db import models  # noqa: F401

    session_factory = create_session_factory(database_url)
    Base.metadata.create_all(session_factory.kw["bind"])
    return session_factory

