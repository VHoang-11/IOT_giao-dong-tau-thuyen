# M2-R7: PlatformIO pre-script cho env esp32dev_rf4_shadow. Dừng build nếu model.h thiếu hoặc khác SHA đóng băng (không tự sinh).
# Tạo/khôi phục: .venv/bin/python -m ml.export.prepare_firmware_model_m2r7
import hashlib
from pathlib import Path

Import("env")  # noqa: F821  (SCons của PlatformIO)

FROZEN = "f83d07cc1ed4b3d55b89933ba545425d7da7acf3eaa4e2f06021b505f342dd09"
header = Path(env.subst("$PROJECT_DIR")).parent / "ml/data/models/rf_four_class_m2r6/v03/firmware/model.h"  # noqa: F821
actual = hashlib.sha256(header.read_bytes()).hexdigest() if header.is_file() else "MISSING"
if actual != FROZEN:
    print(f"[RF4] model.h {actual} != {FROZEN}; chay: python -m ml.export.prepare_firmware_model_m2r7")
    env.Exit(1)  # noqa: F821
print(f"[RF4] model.h OK sha256={FROZEN}")
