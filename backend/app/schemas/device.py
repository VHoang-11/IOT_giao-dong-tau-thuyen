from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import AlarmLevel, DeviceState, MotionClass, NodeType, SourceMode


class DeviceCreate(BaseModel):
    """Dang ky thiet bi truoc khi no gui ban tin dau tien (Admin)."""
    model_config = ConfigDict(extra="forbid")
    device_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    name: Optional[str] = Field(None, max_length=128)
    # Bat buoc neu ro: khong co gia tri mac dinh ngam, vi moi du lieu phai gan nhan SENSOR/SIMULATION.
    # Gia tri nay duoc cap nhat theo ban tin telemetry that khi thiet bi bat dau gui.
    source_mode: SourceMode
    # Multi-Node: dang ky san Cargo Node (can khi AUTO_REGISTER_DEVICES=false). parent_device_id chi hop le voi CARGO.
    node_type: NodeType = NodeType.MOTION
    parent_device_id: Optional[str] = Field(None, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")

    @field_validator("name")
    @classmethod
    def _clean_name(cls, v: Optional[str]) -> Optional[str]:
        return _clean_name(v)

    @model_validator(mode="after")
    def _parent_only_for_cargo(self):
        if self.parent_device_id is not None and self.node_type != NodeType.CARGO:
            raise ValueError("parent_device_id chỉ dùng cho node_type=CARGO")
        if self.parent_device_id is not None and self.parent_device_id == self.device_id:
            raise ValueError("parent_device_id không được trùng device_id")
        return self


class DeviceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Optional[str] = Field(None, max_length=128)
    enabled: Optional[bool] = None
    # Gan Cargo Node vao tau chinh (Admin). null = go lien ket. Dat parent -> thiet bi tro thanh node_type=CARGO.
    parent_device_id: Optional[str] = Field(None, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")

    @field_validator("name")
    @classmethod
    def _clean(cls, v: Optional[str]) -> Optional[str]:
        return _clean_name(v)

    @model_validator(mode="after")
    def _not_empty(self):
        if not self.model_fields_set:
            raise ValueError("Cần ít nhất một trường (name, enabled hoặc parent_device_id)")
        return self


def _clean_name(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    v = v.strip()
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in v):
        raise ValueError("Tên thiết bị không được chứa ký tự điều khiển")
    return v or None   # chuoi rong sau khi cat khoang trang = xoa ten


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    device_id: str
    name: Optional[str] = None
    enabled: bool = True
    source_mode: SourceMode
    state: DeviceState
    last_seen: Optional[datetime] = None
    fw: Optional[str] = None
    boot_id: Optional[str] = None
    model_version: Optional[str] = None
    config_version: Optional[int] = None
    node_type: NodeType = NodeType.MOTION
    parent_device_id: Optional[str] = None


class CargoOut(BaseModel):
    """Mot ban ghi ham hang (Cargo Node). Gia tri khong doc duoc = null (khong phai 0)."""
    model_config = ConfigDict(from_attributes=True)
    device_id: str
    boot_id: str
    seq: int
    uptime_ms: int
    source_mode: SourceMode
    sensor_ok: bool
    cargo_water_pct: Optional[float] = None
    cargo_temp_c: Optional[float] = None
    cargo_humidity_pct: Optional[float] = None
    server_rx_time: datetime


class TelemetryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    device_id: str
    boot_id: str
    seq: int
    t_sim_s: float
    source_mode: SourceMode  # luon hien thi SENSOR/SIMULATION
    roll_deg: float
    pitch_deg: float
    rms_roll_deg: Optional[float] = None
    cargo_water_pct: Optional[float] = None
    cargo_temp_c: Optional[float] = None
    cargo_humidity_pct: Optional[float] = None
    class_rf: MotionClass
    class_baseline_b: Optional[MotionClass] = None
    mai: Optional[int] = None
    alarm_level: AlarmLevel
    sensor_ok: bool
    server_rx_time: datetime
