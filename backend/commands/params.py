"""Kiem tra tham so lenh. Moi lenh co 'khuon' rieng, extra='forbid' -> tham so la bi loai.

AN TOAN: khong co lenh/tham so nao cho phep tat canh bao cuc bo; phi_hard_deg bi kep trong 15-25.
"""
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.models.enums import CommandName

PHI_HARD_MIN, PHI_HARD_MAX = 15.0, 25.0


class CommandInvalid(Exception):
    """Tham so lenh khong hop le (HTTP 422)."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NoParams(_Strict):
    pass


class SetProfileParams(_Strict):
    profile: Literal["STANDARD", "SENSITIVE", "CONSERVATIVE"]


class SetThresholdParams(_Strict):
    phi_hard_deg: Optional[float] = Field(None, ge=PHI_HARD_MIN, le=PHI_HARD_MAX)
    mai_caution: Optional[int] = Field(None, ge=30, le=90)
    debounce_n: Optional[int] = Field(None, ge=1, le=10)
    report_interval_s: Optional[int] = Field(None, ge=1, le=3600)

    @model_validator(mode="after")
    def _not_empty(self):
        if not self.model_dump(exclude_none=True):
            raise ValueError("set_threshold cần ít nhất một tham số")
        return self


class MuteParams(_Strict):
    # Thiet bi tu choi duration_s > 300 (BAD_PARAM; mac dinh 60 s theo Bang 3.1 de cuong) -> backend chan truoc (M1 A3)
    duration_s: Optional[int] = Field(None, ge=1, le=300)


class AckAlarmParams(_Strict):
    alarm_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")   # ma do THIET BI cap (vd. A-0001)


_MODELS: dict[CommandName, type[BaseModel]] = {
    CommandName.set_profile: SetProfileParams,
    CommandName.set_threshold: SetThresholdParams,
    CommandName.mute_alarm: MuteParams,
    CommandName.calibrate_zero: NoParams,
    CommandName.start_voyage: NoParams,
    CommandName.stop_voyage: NoParams,
    CommandName.restart_device: NoParams,
    CommandName.ack_alarm: AckAlarmParams,
}

# --- Quy tac theo THIET BI THAT (M1: firmware/docs/CONTRACT_PROPOSALS.md) ---------------------------------------
# start/stop_voyage: thiet bi tra UNSUPPORTED vi chuyen di do BACKEND quan ly (POST /voyages), khong gui xuong thiet bi.
DEVICE_UNSUPPORTED = {
    CommandName.start_voyage: "Chuyến đi do backend quản lý (dùng POST /api/v1/voyages và /voyages/{id}/end); "
                              "thiết bị không xử lý lệnh này (trả UNSUPPORTED)",
    CommandName.stop_voyage: "Chuyến đi do backend quản lý (dùng POST /api/v1/voyages và /voyages/{id}/end); "
                             "thiết bị không xử lý lệnh này (trả UNSUPPORTED)",
}
# ack_alarm chi duoc gui kem viec ACK tren backend (POST /alarms/{id}/ack) de DB va thiet bi khong lech nhau
INTERNAL_ONLY = {CommandName.ack_alarm: "Dùng POST /api/v1/alarms/{id}/ack (backend vừa ghi nhận ACK vừa báo xuống thiết bị)"}

DEFAULT_TTL_S = 30
# calibrate_zero tra ACK bat dong bo sau ~30 s => TTL phai >= 45 s, neu khong lenh het han trong luc thiet bi dang hieu chuan (M1 B14)
CALIBRATE_MIN_TTL_S = 45
CALIBRATE_DEFAULT_TTL_S = 60


def resolve_ttl(cmd: CommandName, ttl_s: Optional[int]) -> int:
    """TTL hieu luc: mac dinh theo lenh; calibrate_zero bat buoc >= 45 s."""
    if ttl_s is None:
        return CALIBRATE_DEFAULT_TTL_S if cmd == CommandName.calibrate_zero else DEFAULT_TTL_S
    if cmd == CommandName.calibrate_zero and ttl_s < CALIBRATE_MIN_TTL_S:
        raise CommandInvalid(f"calibrate_zero cần ttl_s ≥ {CALIBRATE_MIN_TTL_S} giây "
                             "(thiết bị hiệu chuẩn mất khoảng 30 giây rồi mới trả ACK)")
    return ttl_s


def validate_params(cmd: CommandName, params: dict[str, Any]) -> dict[str, Any]:
    """Tra ve params da lam sach (bo None); nem CommandInvalid neu sai."""
    try:
        return _MODELS[cmd](**params).model_dump(exclude_none=True)
    except ValidationError as e:
        msgs = "; ".join(f"{'.'.join(str(x) for x in err['loc']) or 'params'}: {err['msg']}"
                         for err in e.errors())
        raise CommandInvalid(f"Tham số lệnh '{cmd.value}' không hợp lệ: {msgs}") from e
