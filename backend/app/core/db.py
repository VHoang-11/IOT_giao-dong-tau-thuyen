from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings

_url = settings.database_url
if _url.startswith("sqlite"):
    _kw: dict = {"connect_args": {"check_same_thread": False}}
    if _url in ("sqlite://", "sqlite:///:memory:"):
        _kw["poolclass"] = StaticPool  # dung cho test
else:
    _kw = {"pool_pre_ping": True}

engine = create_engine(_url, **_kw)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
