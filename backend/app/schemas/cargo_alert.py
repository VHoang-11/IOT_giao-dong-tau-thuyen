from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AlarmLevel, AlarmState, SourceMode

MetricState = Literal["NORMAL", "WARNING", "CRITICAL", "UNKNOWN"]
DataClass = Literal["SIMULATION", "SENSOR_UNCALIBRATED", "SENSOR_CALIBRATED"]


class CargoMetricOut(BaseModel):
    """Trạng thái chính thức của một chỉ số hầm hàng (do Backend xác định). UNKNOWN luôn kèm `reason`."""
    metric: Literal["WATER", "TEMPERATURE", "HUMIDITY"]
    state: MetricState
    value: Optional[float] = None            # theo `unit`; nước đã quy ra mm. None khi không đánh giá được
    unit: str
    reason: Optional[str] = None             # NO_DATA | STALE | SENSOR_FAULT | VALUE_MISSING | OUT_OF_RANGE | NOT_CONFIGURED
    detail: Optional[str] = None
    warning: Optional[float] = None          # ngưỡng hiệu lực
    critical: Optional[float] = None
    basis: Optional[str] = None              # AIR_IN_HOLD: nhiệt độ/độ ẩm không khí trong hầm, KHÔNG phải nhiệt độ khối hàng
    reference: list[str] = []
    note: Optional[str] = None


class CargoNodeStatus(BaseModel):
    device_id: str                           # Cargo Node
    link: Literal["NO_DATA", "STALE", "ONLINE"]
    last_sample_at: Optional[datetime] = None
    age_s: Optional[float] = None
    stale_after_s: int
    sensor_ok: Optional[bool] = None
    source_mode: Optional[SourceMode] = None
    data_class: Optional[DataClass] = None
    raw_water_pct: Optional[float] = None    # chỉ khi dữ liệu còn tươi
    state: MetricState                       # tổng hợp của node (không bao giờ NORMAL khi còn chỉ số UNKNOWN)
    metrics: list[CargoMetricOut]
    config_version: int
    threshold_version: str
    missing_config: list[str]
    config_errors: list[str]
    open_alerts: int


class CargoStatusOut(BaseModel):
    device_id: str                           # id được hỏi (tàu chính hoặc Cargo Node)
    state: MetricState                       # UNKNOWN nếu chưa gắn Cargo Node
    link: Literal["NO_NODE", "NO_DATA", "STALE", "ONLINE"]
    nodes: list[CargoNodeStatus]
    profile: str
    profile_scope: str
    disclaimer: str


class CargoAlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    device_id: str
    parent_device_id: Optional[str] = None
    metric: str
    state: AlarmState
    level: AlarmLevel
    max_level: AlarmLevel
    value: float
    peak_value: float
    unit: str
    source_mode: SourceMode
    data_class: str
    threshold_warning: Optional[float] = None
    threshold_critical: Optional[float] = None
    threshold_version: str
    opened_at: datetime
    acked_at: Optional[datetime] = None
    acked_by: Optional[str] = None
    cleared_at: Optional[datetime] = None
    escalated: bool


class CargoConfigIn(BaseModel):
    """Cập nhật từng phần (chỉ trường được gửi). `null` = xóa giá trị. KHÔNG có giá trị mặc định cho kích thước hầm."""
    model_config = ConfigDict(extra="forbid")
    vessel_type: Optional[str] = Field(None, max_length=64)
    cargo_type: Optional[str] = Field(None, max_length=64)
    cargo_hold_depth_mm: Optional[float] = None
    water_sensor_full_scale_mm: Optional[float] = None
    sensor_calibrated: Optional[bool] = None
    # Ghi đè ngưỡng, ví dụ {"temperature": {"warning": 33, "critical": 38}}. null = quay về bộ mặc định.
    thresholds: Optional[dict[str, dict[str, float]]] = None


class CargoConfigOut(BaseModel):
    device_id: str
    configured: bool                         # đã có dòng cấu hình lưu trong CSDL
    version: int
    vessel_type: Optional[str] = None
    cargo_type: Optional[str] = None
    cargo_hold_depth_mm: Optional[float] = None
    water_sensor_full_scale_mm: Optional[float] = None
    sensor_calibrated: bool
    effective_thresholds: dict[str, Any]     # ngưỡng hiệu lực + đơn vị + nguồn tham chiếu + ghi chú phạm vi
    threshold_version: str
    uses_default_thresholds: bool
    missing_fields: list[str]                # trường còn thiếu để đánh giá đầy đủ (không tự giả định)
    errors: list[str]
    updated_by: Optional[str] = None
    updated_at: Optional[datetime] = None
    profile: str
    profile_scope: str
    disclaimer: str
