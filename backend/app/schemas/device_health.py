from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, computed_field

from app.models.enums import DeviceState, SourceMode


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
