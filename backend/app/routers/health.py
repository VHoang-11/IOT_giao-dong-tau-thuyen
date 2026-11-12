from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthOut(BaseModel):
    status: str


@router.get("/healthz", response_model=HealthOut)
async def healthz() -> HealthOut:
    return HealthOut(status="ok")
