"""Xuat OpenAPI -> contracts/openapi.yaml.  Chay tu thu muc backend/: python scripts/export_openapi.py"""
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from main import app  # noqa: E402

out = Path(__file__).resolve().parents[2] / "contracts" / "openapi.yaml"
out.write_text(yaml.safe_dump(app.openapi(), sort_keys=False, allow_unicode=True), encoding="utf-8")
print("wrote", out)
