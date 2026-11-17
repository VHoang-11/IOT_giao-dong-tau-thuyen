from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from app.models.enums import CommandName, CommandState


class CommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cmd: CommandName
    params: dict[str, Any] = Field(default_factory=dict)
    ttl_s: int = Field(30, ge=1, le=300)
    cmd_id: Optional[str] = Field(None, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")


class CommandOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    cmd_id: str
    device_id: str
    cmd: str
    params: Optional[dict[str, Any]] = None
    ttl_s: int
    issued_by: str
    state: CommandState
    reason: Optional[str] = None
    created_at: datetime
    delivered_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def rtt_s(self) -> Optional[float]:
        if self.finished_at is None or self.state not in (CommandState.APPLIED, CommandState.REJECTED):
            return None
        return (self.finished_at.replace(tzinfo=None) - self.created_at.replace(tzinfo=None)).total_seconds()


class CommandStats(BaseModel):
    total: int
    by_state: dict[str, int]
    rtt_mean_s: Optional[float] = None
    rtt_p95_s: Optional[float] = None
    rtt_max_s: Optional[float] = None
    timeout_rate: Optional[float] = None


class ConfigUpdate(BaseModel):
    """Gioi han bam sat contracts/schemas/config.json (phi_hard 15-25, ...)."""
    model_config = ConfigDict(extra="forbid")
    profile: Optional[Literal["STANDARD", "SENSITIVE", "CONSERVATIVE"]] = None
    debounce_n: Optional[int] = Field(None, ge=1, le=10)
    phi_hard_deg: Optional[float] = Field(None, ge=15, le=25)
    mai_caution: Optional[int] = Field(None, ge=30, le=90)
    report_interval_s: Optional[int] = Field(None, ge=1, le=3600)
    primary_model: Optional[Literal["RF", "BASELINE_B"]] = None

    @model_validator(mode="after")
    def _not_empty(self):
        if not self.model_dump(exclude_none=True):
            raise ValueError("Cần ít nhất một trường cấu hình")
        return self


class RollbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    to_version: Optional[int] = Field(None, ge=1)  # mac dinh: phien ban ngay truoc ban moi nhat


class ConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    device_id: str
    config_version: int
    payload: dict[str, Any]
    created_by: str
    created_at: datetime
    applied: bool


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ts: datetime
    actor: str
    action: str
    target: Optional[str] = None
    detail: Optional[dict[str, Any]] = None
