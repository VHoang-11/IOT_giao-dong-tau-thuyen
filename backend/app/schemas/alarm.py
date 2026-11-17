from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, computed_field

from app.models.enums import AlarmLabel, AlarmLevel, AlarmState, MotionClass, SourceMode


class AlarmOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    alarm_id: str
    device_id: str
    boot_id: str
    voyage_id: Optional[str] = None
    state: AlarmState
    level: AlarmLevel
    max_level: AlarmLevel
    motion_class: Optional[MotionClass] = None
    source_mode: SourceMode  # luon hien thi SENSOR/SIMULATION
    opened_at: datetime
    acked_at: Optional[datetime] = None
    acked_by: Optional[str] = None
    cleared_at: Optional[datetime] = None
    escalated: bool
    label: Optional[AlarmLabel] = None
    labeled_by: Optional[str] = None
    labeled_at: Optional[datetime] = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def time_to_ack_s(self) -> Optional[float]:
        if self.acked_at is None:
            return None
        return (self.acked_at.replace(tzinfo=None) - self.opened_at.replace(tzinfo=None)).total_seconds()


class AlarmLabelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: AlarmLabel  # bat buoc; muon 'chua chac' thi dung UNCLEAR


class AckResult(BaseModel):
    alarm: AlarmOut
    already_acked: bool


class AlarmStats(BaseModel):
    total: int
    active: int
    acked: int
    cleared: int
    escalated: int
    mtta_s: Optional[float] = None  # trung binh thoi gian tu luc mo den luc ACK
    escalation_rate: Optional[float] = None
    by_max_level: dict[str, int]
    labeled: int = 0                            # so canh bao da duoc danh gia
    by_label: dict[str, int] = {}
    label_coverage: Optional[float] = None      # labeled / total
    # FALSE / (TRUE + FALSE): chi tinh canh bao da ket luan, bo qua UNCLEAR; None neu chua co ket luan nao
    false_alarm_rate: Optional[float] = None
