"""Schemas cho Monitor API (G6).

NGUYEN TAC: khong bao gio tra ve so lieu khong do duoc. Neu chua co nguon du lieu (vd. PSI can vector dac trung
day du tu M2) thi tra `available=false` kem ly do, KHONG dien so 0 hay 'on dinh' thay the.
"""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

# --------------------------------------------------------------------- agreement

class ClassAgreement(BaseModel):
    rf_total: int                    # so mau ma Random Forest ket luan lop nay
    matched: int                     # trong do Baseline B ket luan cung lop
    rate: Optional[float] = Field(None, ge=0.0, le=1.0)


class AgreementStats(BaseModel):
    """Ty le Random Forest trung Baseline B. Day la do NHAT QUAN giua hai mo hinh, KHONG phai do chinh xac
    (khong co nhan that) va khong phai du bao nguy hiem."""
    device_id: str
    voyage_id: Optional[str] = None
    source_label: str                # SIMULATION | SENSOR | MIXED | UNKNOWN (chua co mau)
    source_modes: list[str]
    samples_considered: int          # mau co du RF va Baseline, sensor_ok = true, toi da `limit` mau gan nhat
    excluded_sensor_fault: int       # mau co du RF+Baseline nhung sensor_ok = false: BI LOAI (toan pham vi)
    matched: int
    agreement_rate: Optional[float] = Field(None, ge=0.0, le=1.0, description="None neu samples_considered = 0")
    by_rf_class: dict[str, ClassAgreement]   # theo lop RF (NORMAL, HIGH_ROLL, ...), khong dat lai ten thanh muc canh bao
    limit: int
    first_sample_at: Optional[datetime] = None
    last_sample_at: Optional[datetime] = None
    notes: list[str]


# --------------------------------------------------------------------- drift

class DriftReport(BaseModel):
    """PSI cua mot dac trung. CHI xuat hien khi DriftStatus.available = true."""
    feature_index: int
    feature_name: str
    psi: float = Field(..., ge=0.0, description="Population Stability Index")
    flagged: bool = Field(..., description="Theo nguong do M2 dinh nghia (nguong chi la tham so demo)")


class DriftStatus(BaseModel):
    device_id: str
    window_hours: int
    window_samples: int              # so mau THAT trong cua so (du lieu co that, du chua tinh duoc PSI)
    source_modes: list[str]
    available: bool                  # false -> khong co PSI nao; doc `reason`
    reason: Optional[str] = None
    source: Literal["unavailable", "ml"] = "unavailable"
    expected_features: list[str]     # ten dac trung doc tu contracts/features23.json; rong neu chua co hop dong
    feature_contract_available: bool = False
    feature_schema_version: Optional[str] = None      # cua hop dong
    feature_count: Optional[int] = None
    device_feature_schema_version: Optional[str] = None   # thiet bi tu bao (status/health)
    device_feature_count: Optional[int] = None
    schema_match: Optional[bool] = None   # None = chua du thong tin de so (khong phai true)
    features: list[DriftReport] = []
    flagged_count: Optional[int] = None   # None khi khong co PSI (khong phai 0)
