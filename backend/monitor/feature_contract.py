"""Doc hop dong dac trung (contracts/features23.json, do M1/M2 so huu). Backend CHI DOC, khong tu dinh nghia ten dac trung.

File thieu / hong -> tra None va Monitor bao 'chua co hop dong' (khong dung danh sach cu, khong doan)."""
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.core.config import settings


@dataclass(frozen=True)
class FeatureContract:
    schema_version: str
    preprocessing_version: str
    count: int
    names: tuple[str, ...]


def contract_path() -> Path:
    if settings.feature_contract_path:
        return Path(settings.feature_contract_path)
    schemas = Path(settings.contracts_dir) if settings.contracts_dir else Path(__file__).resolve().parents[2] / "contracts" / "schemas"
    return schemas.parent / "features23.json"


def load_contract() -> Optional[FeatureContract]:
    try:
        raw = json.loads(contract_path().read_text(encoding="utf-8"))
        feats = sorted(raw["features"], key=lambda f: f["index"])
        names = tuple(f["name"] for f in feats)
        if [f["index"] for f in feats] != list(range(len(feats))) or len(names) != raw["feature_count"]:
            return None  # hop dong tu mau thuan -> khong tin
        return FeatureContract(raw["feature_schema_version"], raw["preprocessing_version"], raw["feature_count"], names)
    except (OSError, ValueError, KeyError, TypeError):
        return None
