"""SVMG backend entrypoint. Chay: uvicorn main:app --reload --port 8000"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models  # noqa: F401
from app.core.config import settings
from app.core.db import Base, engine
from app.core.logging import setup_logging
from app.routers import devices, health

setup_logging(settings.log_level)
log = logging.getLogger("svmg")


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)  # dev; prod dung `alembic upgrade head`
    log.info("backend started", extra={"database": engine.url.render_as_string(hide_password=True)})
    # TODO: M3-02 - khoi dong MQTT consumer (ingest)
    yield


app = FastAPI(
    title="SVMG Backend",
    version="0.1.0",
    description="Smart Vessel Motion Guard - nguyên mẫu nghiên cứu/đào tạo, dữ liệu mô phỏng. "
                "Không phải hệ thống an toàn hàng hải.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health.router)
app.include_router(devices.router)
# TODO: M3-03 alarms, M3-04 commands, M3-05 auth, M3-06 voyages/reports, M3-07 replay/monitor
