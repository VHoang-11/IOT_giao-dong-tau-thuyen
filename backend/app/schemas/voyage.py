from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import SourceMode, VoyageStatus
from app.schemas.alarm import AlarmStats

VOYAGE_ID_PATTERN = r"^[A-Za-z0-9_.-]{1,64}$"

DISCLAIMER = ("Nguyên mẫu nghiên cứu/đào tạo, KHÔNG phải hệ thống an toàn hàng hải. "
              "Các ngưỡng chỉ là tham số demo. Không phải dự báo lật tàu hay đánh giá ổn định tàu.")


class VoyageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    # Tuy chon: neu thiet bi da phat telemetry mang voyage_id nay thi truyen vao de khop. Bo trong -> backend sinh V-YYYY-NNN.
    voyage_id: Optional[str] = Field(None, pattern=VOYAGE_ID_PATTERN)


class VoyageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    voyage_id: str
    device_id: str
    source_mode: SourceMode
    status: VoyageStatus
    started_by: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    ended_by: Optional[str] = None


class DataQuality(BaseModel):
    """Chat luong nhan theo BANG CHUNG (reports/metrics.py). seq dung chung telemetry/event/health/trace nen khoang trong
    seq khong dong nghia mat goi; ty le nhan chi co khi moi khoang trong da duoc xac minh."""
    samples: int
    receive_status: Literal["VERIFIED", "NO_LOSS_EVIDENCE", "INSUFFICIENT_EVIDENCE", "NO_DATA"] = "NO_DATA"
    expected_samples: Optional[int] = None   # chi khi VERIFIED: so telemetry thiet bi da gui trong dai seq (= da nhan)
    missing_samples: Optional[int] = None    # chi khi VERIFIED (= 0); None = chua du bang chung, KHONG phai 0
    received_rate: Optional[float] = None    # chi khi VERIFIED; None khi chua du bang chung hoac chua co mau
    received_rate_lower_bound: Optional[float] = None   # truong hop xau nhat: moi khoang trong chua xac minh la telemetry mat
    seq_span: int = 0                        # tong (seq_max - seq_min + 1) cua TUNG boot_id
    seq_gaps: int = 0                        # seq_span - samples
    seq_used_by_events: int = 0              # da xac minh: seq cua AlarmEvent cung boot
    seq_telemetry_outside_voyage: int = 0    # da xac minh: telemetry cung boot o chuyen khac / khong chuyen (den tre)
    seq_gaps_health_timing: int = 0          # phu hop ban tin health theo thoi gian (health khong mang seq)
    seq_gaps_unclassified: int = 0           # chua phan loai
    boots: int                       # so lan khoi dong (boot_id) trong chuyen
    sensor_fault_samples: int        # mau co sensor_ok = false (bi LOAI khoi thong ke chuyen dong)


class MotionStats(BaseModel):
    samples_used: int                # mau co sensor_ok = true
    max_abs_roll_deg: Optional[float] = None
    p95_abs_roll_deg: Optional[float] = None    # nearest-rank tren |roll|
    mean_rms_roll_deg: Optional[float] = None   # trung binh cac gia tri rms_roll_deg thiet bi gui (khong tu tinh lai)
    max_abs_pitch_deg: Optional[float] = None
    max_abs_heel_offset_deg: Optional[float] = None


class Distribution(BaseModel):
    counts: dict[str, int] = {}
    share: dict[str, float] = {}     # ty le theo SO MAU (khong phai theo thoi gian)


class CommandSummary(BaseModel):
    total: int
    by_state: dict[str, int] = {}


class ReportSummary(BaseModel):
    voyage: VoyageOut
    provisional: bool                # True khi chuyen dang chay: so lieu chi la TAM THOI
    generated_at: datetime
    source_label: str                # SIMULATION | SENSOR | MIXED | UNKNOWN (chua co mau)
    source_modes: list[str]
    first_sample_at: Optional[datetime] = None   # theo server_rx_time
    last_sample_at: Optional[datetime] = None
    duration_s: Optional[float] = None
    data_quality: DataQuality
    motion: MotionStats
    class_rf: Distribution
    class_baseline_b: Distribution
    rf_baseline_agreement_rate: Optional[float] = None   # ty le mau RF == Baseline B (chi mau co ca hai)
    alarm_levels: Distribution
    alarms: AlarmStats
    false_alarms_per_hour: Optional[float] = None        # so canh bao SAI / gio (duration), chi khi co duration > 0
    commands: CommandSummary
    notes: list[str]
    telemetry_rows: int
    telemetry_csv_sha256: str        # SHA-256 cua file telemetry.csv: de doi chieu "cung du lieu dau vao" (T11)
    disclaimer: str = DISCLAIMER
