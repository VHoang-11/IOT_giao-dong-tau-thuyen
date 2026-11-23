"""Pre-build PlatformIO: biên dịch model C99 do M2-R1 sinh (gitignored) vào target cô lập; thiếu thì chạy exporter M2-R1."""
import hashlib, json, subprocess, sys  # noqa: E401
from pathlib import Path

Import("env")  # noqa: F821  (SCons)

ROOT = Path(env.subst("$PROJECT_DIR")).resolve().parents[1]  # noqa: F821
MODEL_DIR, NAME = ROOT / "ml/data/models/rf_demo_m2r1", "svmg_rf_proxy_demo"
if not all((MODEL_DIR / f).is_file() for f in (f"{NAME}.h", f"{NAME}.c", "results.json")):
    print("M2-R2: chưa có model C M2-R1 -> chạy python -m ml.train.rf_demo_m2r1")
    subprocess.run([sys.executable, "-m", "ml.train.rf_demo_m2r1"], cwd=ROOT, check=True)
results = json.loads((MODEL_DIR / "results.json").read_text(encoding="utf-8"))
text = (MODEL_DIR / f"{NAME}.h").read_text(encoding="ascii") + (MODEL_DIR / f"{NAME}.c").read_text(encoding="ascii")
digest = hashlib.sha256(text.encode()).hexdigest()
if digest != results["demo_model"]["export"]["generated_sha256"]:
    sys.exit("M2-R2: model C không khớp results.json; chạy lại python -m ml.train.rf_demo_m2r1")
env.Append(CPPPATH=[str(MODEL_DIR)], CPPDEFINES=[  # noqa: F821
    ("RF_DEMO_MODEL_SHA256", env.StringifyMacro(digest)),  # noqa: F821
    ("RF_DEMO_MODEL_VERSION", env.StringifyMacro(results["metadata"]["model_version"]))])  # noqa: F821
env.BuildSources("$BUILD_DIR/rf_model", str(MODEL_DIR), src_filter=f"-<*> +<{NAME}.c>")  # noqa: F821
print(f"M2-R2: model {results['metadata']['model_version']} sha256={digest}")
