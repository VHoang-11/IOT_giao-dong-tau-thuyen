"""Validate ban tin MQTT theo JSON Schema trong contracts/schemas/."""
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator

from app.core.config import settings

# kind -> ten file schema
SCHEMA_FILES = {
    "telemetry": "telemetry.json",
    "event": "event.json",
    "status": "status.json",
    "health": "health.json",
    "cmd/ack": "command_ack.json",
    "cmd": "command.json",      # downlink: validate truoc khi gui
    "config": "config.json",    # downlink: validate truoc khi gui
}


def schema_dir() -> Path:
    if settings.contracts_dir:
        return Path(settings.contracts_dir)
    return Path(__file__).resolve().parents[2] / "contracts" / "schemas"


@lru_cache(maxsize=None)
def _validator(kind: str) -> Draft7Validator:
    schema = json.loads((schema_dir() / SCHEMA_FILES[kind]).read_text(encoding="utf-8"))
    Draft7Validator.check_schema(schema)
    return Draft7Validator(schema)


def validate(kind: str, payload: Any) -> list[str]:
    """Tra ve danh sach loi (rong = hop le)."""
    errs = sorted(_validator(kind).iter_errors(payload), key=lambda e: list(e.path))
    return [f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}" for e in errs]
