from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings

_MEMORY_URLS = ("sqlite://", "sqlite:///:memory:")


def build_engine(url: str) -> Engine:
    if not url.startswith("sqlite"):
        return create_engine(url, pool_pre_ping=True)
    kw: dict = {"connect_args": {"check_same_thread": False}}
    if url in _MEMORY_URLS:
        kw["poolclass"] = StaticPool  # dung cho test
    eng = create_engine(url, **kw)
    if url not in _MEMORY_URLS:
        @event.listens_for(eng, "connect")
        def _sqlite_pragmas(dbapi_conn, _):
            # Backend ghi DB tu nhieu luong (MQTT, API, quet nen). Mac dinh SQLite chi cho 1 ben ghi va ben kia
            # bao 'database is locked' NGAY -> mat ban tin. WAL cho doc/ghi song song; busy_timeout cho ben den sau cho.
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA busy_timeout=5000")
            cur.execute("PRAGMA synchronous=NORMAL")
            cur.close()
    return eng


engine = build_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
