"""M2-R7: tạo `model.h` cho firmware từ mô hình đóng băng M2-R6a/R6b, KHÔNG huấn luyện/chỉnh tau.

Sinh lại header từ `model.joblib` đã khóa (SHA mô hình kiểm trong `load_frozen`) và chỉ ghi khi SHA-256 trùng đúng header đóng
băng trong manifest. Ghi vào thư mục gitignored `ml/data/models/rf_four_class_m2r6/v03/firmware/` (KHÔNG ghi `ml/export/model.h`,
vì mọi env firmware có `-I../ml/export`). Chỉ env `esp32dev_rf4_shadow` thêm thư mục này và kiểm lại SHA trước khi build.

    .venv/bin/python -m ml.export.prepare_firmware_model_m2r7
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ml.export import rf4_freeze_m2r6b as F
from ml.export import rf_c_export as E
from ml.train import rf_four_class_m2r6 as R

FROZEN_HEADER_SHA256 = "f83d07cc1ed4b3d55b89933ba545425d7da7acf3eaa4e2f06021b505f342dd09"
FW_DIR = F.MODEL_DIR / "firmware"


def frozen_header_text() -> str:
    manifest = json.loads(F.MANIFEST.read_text(encoding="utf-8"))
    model, meta = F.load_frozen()
    tau = manifest["unknown_policy"]["tau_conf"]
    if manifest["model_sha256"] != F.FROZEN_MODEL_SHA256 or tau != 0.5 or manifest["c_artifact"]["sha256"] != FROZEN_HEADER_SHA256:
        raise RuntimeError("Manifest đóng băng khác bản đã duyệt (mô hình/tau/header); dừng.")
    text = E.generate_model_h(model, R.FEATURES, F.c_metadata(meta), tau)[0]
    if hashlib.sha256(text.encode()).hexdigest() != FROZEN_HEADER_SHA256:
        raise RuntimeError("Header sinh lại KHÁC SHA đóng băng; không cung cấp cho firmware.")
    return text


def prepare(out_dir: Path = FW_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "model.h"
    path.write_text(frozen_header_text(), encoding="ascii")
    (out_dir / "model.h.sha256").write_text(f"{FROZEN_HEADER_SHA256}  model.h\n", encoding="ascii")
    return path


if __name__ == "__main__":
    print(f"{prepare()} sha256={FROZEN_HEADER_SHA256}")
