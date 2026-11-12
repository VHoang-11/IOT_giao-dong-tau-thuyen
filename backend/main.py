"""SVMG backend entrypoint. Chạy: uvicorn main:app --reload --port 8000"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.core.db import Base, engine
from app.routers import health


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)  # dev only; prod dùng Alembic
    # TODO: M3-01 — khởi động MQTT consumer (ingest.consumer)
    yield


app = FastAPI(title="SVMG Backend", version="0.1.0", lifespan=lifespan)
app.include_router(health.router)
# TODO: include routers: auth, alarms, commands, reports, replay, monitor
