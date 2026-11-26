from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, computed_field

from app.models.enums import AlarmLabel, AlarmLevel, AlarmState, MotionClass, SourceMode


class DeviceAck(BaseModel):
    """ACK tren THIET BI (khac ACK cua nguoi truc tren backend: acked_by/acked_at).
    CONFIRMED chi khi thiet bi phat ALARM_STATE kem acked_by sau lenh ack_alarm (hoac ACK bang nut tren thiet bi);
    APPLIED cua lenh ack_alarm KHONG du: thiet bi tra APPLIED ca khi id cu / muc < WARNING (khong tac dung, M1 A2)."""
    state: Literal["NOT_REQUESTED", "PENDING", "CONFIRMED", "APPLIED_UNCONFIRMED", "REJECTED", "TIMEOUT"]
    cmd_id: Optional[str] = None          # lenh ack_alarm tuong ung ('ack-<id canh bao>'); None neu khong co lenh
    reason: Optional[str] = None
    confirmed_at: Optional[datetime] = None


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
    # Canh bao thuoc lan khoi dong HIEN TAI cua thiet bi? False = boot cu: thiet bi khong con giu canh bao nay trong RAM
    # (lich su van giu nguyen, khong tu dong CLEARED). None = chua biet boot hien tai cua thiet bi.
    boot_current: Optional[bool] = None
    device_ack: Optional[DeviceAck] = None   # None khi nguoi truc chua ACK

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
    # Day lenh ack_alarm xuong thiet bi (best-effort, KHONG anh huong ket qua ACK tren server):
    # sent | not_applicable (da ACK truoc do / thiet bi khoi dong lai) | unsupported (hop dong chua co lenh) | failed
    # 'sent' chi nghia la DA TAO lenh ack_alarm, KHONG phai thiet bi da ACK: xem alarm.device_ack.state.
    device_ack: str = "not_applicable"
    device_ack_detail: Optional[str] = None
    device_ack_cmd_id: Optional[str] = None


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
    # canh bao chua giai toa nhung thuoc lan khoi dong TRUOC cua thiet bi (thiet bi khong con giu): lich su, khong chan mute
    open_previous_boot: int = 0
