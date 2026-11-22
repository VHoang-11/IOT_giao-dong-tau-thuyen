from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, computed_field

from app.models.enums import CommandState, DeviceState, SourceMode


class DeviceHealthOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    device_id: str
    free_heap_bytes: int
    min_free_heap_bytes: Optional[int] = None
    uptime_ms: int
    sensor_ok: bool
    i2c_errors: Optional[int] = None
    inference_ms: Optional[float] = None
    mqtt_reconnects: Optional[int] = None
    buffer_used: Optional[int] = None
    buffer_capacity: Optional[int] = None
    server_rx_time: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def buffer_used_pct(self) -> Optional[float]:
        if self.buffer_used is None or not self.buffer_capacity:
            return None
        return round(100.0 * self.buffer_used / self.buffer_capacity, 1)


class DeviceHealthSummary(BaseModel):
    device_id: str
    state: DeviceState
    source_mode: SourceMode
    last_seen: Optional[datetime] = None
    seconds_since_seen: Optional[float] = None
    # stale = qua health_stale_s khong thay thiet bi gui gi (chua tung thay cung tinh la stale)
    stale: bool
    latest: Optional[DeviceHealthOut] = None
    # Hieu chuan (G5): chi phan anh lenh `calibrate_zero` da duoc thiet bi xac nhan APPLIED qua backend.
    # Hieu chuan bang nut/chiet ap tren thiet bi KHONG duoc ghi nhan. None = chua co lan nao (khong phai 'khong can').
    last_calibrated_at: Optional[datetime] = None
    last_calibration_state: Optional[CommandState] = None   # ket qua lan gui lenh gan nhat (APPLIED/REJECTED/TIMEOUT/SENT...)
