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
    duration_s: Optional[int] = Field(None, ge=1, le=600)


_MODELS: dict[CommandName, type[BaseModel]] = {
    CommandName.set_profile: SetProfileParams,
    CommandName.set_threshold: SetThresholdParams,
    CommandName.mute_alarm: MuteParams,
    CommandName.calibrate_zero: NoParams,
    CommandName.start_voyage: NoParams,
    CommandName.stop_voyage: NoParams,
    CommandName.restart_device: NoParams,
}


def validate_params(cmd: CommandName, params: dict[str, Any]) -> dict[str, Any]:
    """Tra ve params da lam sach (bo None); nem CommandInvalid neu sai."""
    try:
        return _MODELS[cmd](**params).model_dump(exclude_none=True)
    except ValidationError as e:
        msgs = "; ".join(f"{'.'.join(str(x) for x in err['loc']) or 'params'}: {err['msg']}"
                         for err in e.errors())
        raise CommandInvalid(f"Tham số lệnh '{cmd.value}' không hợp lệ: {msgs}") from e
