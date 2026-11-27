"""SVMG backend entrypoint. Chay: uvicorn main:app --reload --port 8000"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models as _models  # noqa: F401  (dang ky bang cho create_all; ten rieng de khong che ten `app` = FastAPI)
from alarms.realtime import hub, telemetry_hub
from alarms.service import escalate_overdue
from app.core.config import settings
from app.core.db import Base, SessionLocal, engine
from app.core.logging import setup_logging
from app.core.security import validate_security_settings
from app.routers import (
    alarms, auth, cargo as cargo_router, commands, device_health, devices, health, ingest_stats,
    monitor as monitor_router,
    notify as notify_router,
    replay as replay_router,
    retention as retention_router,
    voyages,
)
from app.services.auth import bootstrap_admin
from app.services.retention import purge_old, retention_enabled
from commands.service import expire_overdue
from notify.service import dispatcher

setup_logging(settings.log_level)
log = logging.getLogger("svmg")


def _escalation_sweep() -> None:
    """Quet nen: leo thang canh bao chua ACK (M3-03) va TIMEOUT lenh qua TTL (M3-04)."""
    for job in (escalate_overdue, expire_overdue):
        db = SessionLocal()
        try:
            job(db)
        except Exception:  # loi quet khong duoc lam chet vong lap
            db.rollback()
            log.exception("background sweep failed", extra={"job": job.__name__})
        finally:
            db.close()


def _retention_sweep() -> None:
    db = SessionLocal()
    try:
        purge_old(db)
    except Exception:
        db.rollback()
        log.exception("retention sweep failed")
    finally:
        db.close()


async def _retention_loop() -> None:
    while True:
        await asyncio.to_thread(_retention_sweep)
        await asyncio.sleep(settings.retention_interval_s)


async def _escalation_loop() -> None:
    while True:
        await asyncio.sleep(settings.alarm_escalation_check_s)
        await asyncio.to_thread(_escalation_sweep)  # DB dong bo -> chay ngoai event loop


@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_security_settings()  # production + secret yeu -> tu choi khoi dong
    Base.metadata.create_all(bind=engine)  # dev; prod dung `alembic upgrade head`
    with SessionLocal() as db:
        bootstrap_admin(db)  # chi tao khi bang users rong va ADMIN_PASSWORD duoc dat
    log.info("backend started", extra={"database": engine.url.render_as_string(hide_password=True)})
    hub.bind_loop(asyncio.get_running_loop())  # de luong MQTT day tin sang WebSocket
    telemetry_hub.bind_loop(asyncio.get_running_loop())
    task = asyncio.create_task(_escalation_loop()) if settings.alarm_escalation_enabled else None
    retention_task = asyncio.create_task(_retention_loop()) if retention_enabled() else None  # mac dinh khong chay
    if settings.mqtt_enabled:
        from ingest.consumer import start_consumer, stop_consumer
        start_consumer()  # connect_async: khong chan neu broker chua len
    yield
    if settings.mqtt_enabled:
        stop_consumer()
    for t in (task, retention_task):
        if t:
            t.cancel()
    dispatcher.shutdown()


app = FastAPI(
    title="SVMG Backend",
    version="0.1.0",
    description="Smart Vessel Motion Guard - nguyên mẫu nghiên cứu/đào tạo, dữ liệu mô phỏng. "
                "Không phải hệ thống an toàn hàng hải.",
    lifespan=lifespan,
    # production: khong phuc vu tai lieu API cong khai (van xuat duoc file bang scripts/export_openapi.py)
    docs_url="/docs" if settings.docs_on else None,
    redoc_url="/redoc" if settings.docs_on else None,
    openapi_url="/openapi.json" if settings.docs_on else None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health.router)
app.include_router(devices.router)
app.include_router(cargo_router.router)
app.include_router(auth.router)
app.include_router(alarms.router)
app.include_router(alarms.ws_router)
app.include_router(commands.router)
app.include_router(device_health.router)
app.include_router(notify_router.router)
app.include_router(voyages.router)
app.include_router(replay_router.router)
app.include_router(monitor_router.router)
app.include_router(ingest_stats.router)
app.include_router(retention_router.router)
