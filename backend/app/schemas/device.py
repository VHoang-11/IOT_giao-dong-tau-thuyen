from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.enums import AlarmLevel, DeviceState, MotionClass, SourceMode


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    device_id: str
    name: Optional[str] = None
    source_mode: SourceMode
    state: DeviceState
    last_seen: Optional[datetime] = None
    fw: Optional[str] = None
    boot_id: Optional[str] = None
    model_version: Optional[str] = None
    config_version: Optional[int] = None


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
    class_rf: MotionClass
    class_baseline_b: Optional[MotionClass] = None
    mai: Optional[int] = None
    alarm_level: AlarmLevel
    sensor_ok: bool
    server_rx_time: datetime
