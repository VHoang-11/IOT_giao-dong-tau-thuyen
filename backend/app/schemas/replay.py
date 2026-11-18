from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel

from app.models.enums import AlarmLevel, CommandState, MotionClass, SourceMode, VoyageStatus
from app.schemas.alarm import AlarmOut


class ReplayTelemetry(BaseModel):
    boot_id: str
    seq: int
    t_sim_s: float
    timewarp: int
    server_rx_time: datetime
    source_mode: SourceMode          # luon kem nhan SENSOR/SIMULATION
    sensor_ok: bool                  # false -> giao dien phai hien thi khac (so do co the sai)
    scenario_id: Optional[str] = None
    roll_deg: float
    pitch_deg: float
    rms_roll_deg: Optional[float] = None
    heel_offset_deg: Optional[float] = None
    trend_rms_deg_per_min: Optional[float] = None
    class_rf: MotionClass
    class_baseline_b: Optional[MotionClass] = None
    mai: Optional[int] = None
    alarm_level: AlarmLevel
    model_version: str
    config_version: int


class ReplayAlarmEvent(BaseModel):
    """Mot lan chuyen muc canh bao do THIET BI gui (ban tin `event`)."""
    boot_id: str
    seq: int
    alarm_id: str
    level: AlarmLevel
    prev_level: Optional[AlarmLevel] = None
    motion_class: Optional[MotionClass] = None
    t_sim_s: float
    acked_by: Optional[str] = None
    server_rx_time: datetime


class ReplayCommand(BaseModel):
    cmd_id: str
    cmd: str
    params: Optional[dict[str, Any]] = None
    state: CommandState
    issued_by: str
    reason: Optional[str] = None
    created_at: datetime
    finished_at: Optional[datetime] = None


class ReplayMeta(BaseModel):
    voyage_id: str
    device_id: str
    status: VoyageStatus
    source_modes: list[str]
    total_samples: int                       # toan chuyen
    window_samples: int                      # theo bo loc from/to (khong tinh con tro)
    boots: int
    first_sample_at: Optional[datetime] = None   # server_rx_time
    last_sample_at: Optional[datetime] = None
    duration_wall_s: Optional[float] = None      # last - first theo gio server
    t_sim_min_s: Optional[float] = None
    t_sim_max_s: Optional[float] = None
    # True neu t_sim_s KHONG giam theo thu tu nhan trong ca chuyen. False (vd. dem lai sau khi khoi dong lai)
    # -> khong dung t_sim_s lam truc thoi gian duy nhat. None neu chuyen chua co mau.
    t_sim_monotonic: Optional[bool] = None
    timewarps: list[int]                     # cac he so timewarp xuat hien (de giao dien dien giai toc do)


class ReplayResponse(BaseModel):
    meta: ReplayMeta
    telemetry: list[ReplayTelemetry]         # tang dan theo (server_rx_time, id)
    alarm_events: list[ReplayAlarmEvent]     # tang dan theo server_rx_time; moi su kien xuat hien DUNG 1 LAN qua cac trang
    alarms: list[AlarmOut]                   # canh bao dang hoat dong trong khoang cua trang (trang khac co the lap lai: dedup theo id)
    commands: list[ReplayCommand]
    limit: int
    truncated: bool                          # true -> con trang sau, dung next_cursor
    next_cursor: Optional[str] = None
