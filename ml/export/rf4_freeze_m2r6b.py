"""M2-R6b: export C99 RF bốn lớp đã chọn ở M2-R6a (KHÔNG huấn luyện/chọn lại), chọn chính sách UNKNOWN chỉ trên Validation,
parity Python/C và manifest đóng băng. Test-G1 KHÔNG được nạp. Không ghi ml/export/model.h (firmware tự nhận file đó).

    .venv/bin/python -m ml.export.rf4_freeze_m2r6b
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import joblib
import numpy as np
import sklearn

from ml.export import rf_c_export as E
from ml.train import rf_four_class_m2r6 as R
from ml.train.g1_simulation_dataset import ROOT, _sha

FROZEN_MODEL_SHA256 = "3d7ecf315e237b00e26da4338ed0aa313d6efc9e5488dd6b227e18cc80f41f89"
MODEL_DIR = R.OUT / "v03"
OUT = MODEL_DIR / "c99"
HEADER = "svmg_rf_four_class_m2r6a_0_1_0.h"
MANIFEST = ROOT / "ml/reports/ml/m2_r6b_frozen_model_manifest.json"
REPORT = ROOT / "ml/reports/ml/m2_r6b_c99_export_report.md"
# Chính sách UNKNOWN khai báo trước: conf = max xác suất lá trung bình (KHÔNG hiệu chuẩn). Chọn tau LỚN NHẤT trong lưới mà mọi
# lớp CORE Validation còn recall hiệu dụng (đúng và không UNKNOWN) >= 0,95; không có -> giữ 0,5 = mặc định của infer.cpp.
TAU_GRID, MIN_EFFECTIVE_RECALL, FALLBACK_TAU = (0.5, 0.6, 0.7, 0.8, 0.9), 0.95, 0.5
XTENSA = Path.home() / ".platformio/packages/toolchain-xtensa-esp-elf/bin"


def load_frozen() -> tuple:
    path = MODEL_DIR / "model.joblib"
    if _sha(path) != FROZEN_MODEL_SHA256:
        raise RuntimeError("model.joblib khác bản đã chọn ở M2-R6a; dừng (không huấn luyện lại).")
    meta = json.loads((MODEL_DIR / "metadata.json").read_text())
    schema = (ROOT / "core/include/svmg_feature_schema.h").read_text()
    core = {k: re.search(rf"#define {k} \"([^\"]+)\"", schema)[1] for k in ("SVMG_FEATURE_SCHEMA_VERSION", "SVMG_PREPROCESSING_VERSION")}
    if (meta["feature_names"] != R.FEATURES or meta["dataset_sha256"] != R.DATASETS["v0.3"][1]
            or meta["feature_schema_version"] != core["SVMG_FEATURE_SCHEMA_VERSION"]
            or meta["preprocessing_version"] != core["SVMG_PREPROCESSING_VERSION"] or meta["model_version"] != R.MODEL_VERSION):
        raise RuntimeError("Metadata mô hình không khớp schema/preprocessing của Core C hoặc dataset v0.3; dừng.")
    return joblib.load(path), meta


def c_metadata(meta: dict) -> dict:
    keys = ("model_version", "dataset_version", "dataset_sha256", "feature_schema_version", "preprocessing_version", "label_source")
    return {**{k: meta[k] for k in keys}, "model_sha256": FROZEN_MODEL_SHA256, "classes": R.CLASSES}


def policy(proba: np.ndarray, y: np.ndarray | None, tau: float) -> dict:
    """Áp tau như infer.cpp: conf (float32) < tau -> UNKNOWN. y None = S0b (mọi cửa sổ là NORMAL)."""
    pred, conf = proba.argmax(1), proba.max(1).astype(np.float32)
    accepted = conf >= np.float32(tau)
    y = np.zeros(len(pred), int) if y is None else y
    out = {"windows": int(len(y)), "unknown": int((~accepted).sum()), "coverage": round(float(accepted.mean()), 4),
           "accepted_errors": int((accepted & (pred != y)).sum()),
           "false_non_normal_on_normal": int((accepted & (y == 0) & (pred != 0)).sum())}
    out["per_class"] = {c: {"coverage": round(float(accepted[y == i].mean()), 4),
                            "effective_recall": round(float((accepted & (pred == y))[y == i].mean()), 4)}
                        for i, c in enumerate(R.CLASSES) if (y == i).any()}
    return out


def compile_checks(header: Path) -> dict:
    """Probe dùng header như infer.cpp (C++) và đo object -Os bằng toolchain ESP32 (nếu đã cài PlatformIO)."""
    probe = header.with_name("size_probe.c")
    probe.write_text(f'#include "{header.name}"\nint svmg_rf4_probe(const float *f, float *c) {{ return model_predict_conf(f, 23, c); }}\n')
    cxx = subprocess.run(["c++", "-std=gnu++11", "-Wall", "-Wextra", "-Werror", "-pedantic", "-fsyntax-only", "-x", "c++",
                          "-I", str(header.parent), str(probe)], capture_output=True, text=True)
    out = {"cxx_gnu11_probe_ok": cxx.returncode == 0}
    if (XTENSA / "xtensa-esp32-elf-gcc").is_file():
        out["esp32_xtensa_Os"] = E.object_size(probe, str(XTENSA / "xtensa-esp32-elf-gcc"), str(XTENSA / "xtensa-esp32-elf-size"),
                                               header.with_name("probe_esp32.o"))
    return out


def run(manifest_path: Path = MANIFEST, report: Path | None = REPORT) -> dict:
    model, meta = load_frozen()
    frame = R.load(R.DATASETS["v0.3"][0])             # chỉ Train/Validation có nhãn; Test-G1 bị loại khi đọc
    val, s0b = frame.loc[frame.subset.eq("CORE") & frame.split.eq(R.VAL)], frame.loc[frame.subset.eq("CHALLENGE_S0B")]
    X_val, X_s0b = R.matrix(val), R.matrix(s0b)
    p_val, p_s0b = model.predict_proba(X_val), model.predict_proba(X_s0b)
    saved = np.loadtxt(MODEL_DIR / "validation_predictions.csv", delimiter=",", skiprows=1, usecols=6, dtype=int)
    if not np.array_equal(saved, p_val.argmax(1)):
        raise RuntimeError("Dự đoán Validation khác bản lưu ở M2-R6a; dừng.")
    table = {str(t): {"validation": policy(p_val, val.y.to_numpy(), t), "s0b": policy(p_s0b, None, t)} for t in TAU_GRID}
    ok = [t for t in TAU_GRID if min(v["effective_recall"] for v in table[str(t)]["validation"]["per_class"].values())
          >= MIN_EFFECTIVE_RECALL]
    tau = max(ok) if ok else FALLBACK_TAU   # không tau nào đạt -> giữ mặc định firmware, ghi rõ trong manifest
    c_meta = c_metadata(meta)
    text, stats = E.generate_model_h(model, R.FEATURES, c_meta, tau)
    deterministic = E.generate_model_h(joblib.load(MODEL_DIR / "model.joblib"), R.FEATURES, c_meta, tau)[0] == text
    OUT.mkdir(parents=True, exist_ok=True)
    header = OUT / HEADER
    header.write_text(text, encoding="ascii")
    binary = E.build_runner4(header, OUT)
    sets = {"validation": X_val, "s0b": X_s0b, "threshold_boundaries": np.array(E.boundary_vectors4(model, X_val[0]))}
    evidence = {k: E.parity4(binary, model, X, tau) for k, X in sets.items()}
    m = {"status": "FROZEN_PENDING_TEST_G1", "model_version": meta["model_version"], "model_sha256": FROZEN_MODEL_SHA256,
         "dataset_version": meta["dataset_version"], "dataset_sha256": meta["dataset_sha256"], "dataset_source": "SIMULATION",
         "label_source": meta["label_source"], "label_policy": meta["label_policy"], "feature_schema_version": meta["feature_schema_version"],
         "preprocessing_version": meta["preprocessing_version"], "feature_names": R.FEATURES, "class_mapping": meta["class_mapping"],
         "hyperparameters": meta["params"], "seed": meta["seed"], "sklearn_version": sklearn.__version__,
         "unknown_policy": {"tau_conf": tau, "selected_by": "CORE Validation only", "grid": list(TAU_GRID), "fallback_tau": FALLBACK_TAU,
                            "rule": f"largest tau with every class effective recall >= {MIN_EFFECTIVE_RECALL}", "rule_satisfied_by": ok,
                            "confidence": "max mean leaf probability (sklearn predict_proba semantics), NOT calibrated",
                            "firmware_mapping": "conf < SVMG_TAU_CONF or pred < 0 -> SVMG_UNKNOWN (firmware/src/infer.cpp)"},
         "policy_table": table, "c_artifact": {"header": HEADER, "sha256": _sha(header), "bytes": header.stat().st_size,
                                               "deterministic_regeneration": deterministic, **stats, **compile_checks(header)},
         "parity": {**evidence, "invalid_inputs": E.invalid_inputs4(binary, X_val[0]), "cflags": list(E.CFLAGS)},
         "sources_sha256": {str(p.relative_to(ROOT)): _sha(p) for p in (ROOT / "ml/export/rf_c_export.py", E.RUNNER4_SOURCE,
                            Path(__file__).resolve(), ROOT / "ml/train/rf_four_class_m2r6.py", ROOT / "firmware/src/infer.cpp")},
         "test_g1": "NOT_EVALUATED; evaluate once, read-only, after this freeze"}
    manifest_path.write_text("{\n" + ",\n".join(f" {json.dumps(k)}: {json.dumps(v, ensure_ascii=False, default=float)}"
                                                 for k, v in m.items()) + "\n}\n", encoding="utf-8")
    if report:
        write_report(m, report)
    return m


def write_report(m: dict, path: Path) -> None:
    u, c, par = m["unknown_policy"], m["c_artifact"], m["parity"]
    row = lambda t, d: (f"| {t} | {d['validation']['coverage']} | "  # noqa: E731
                        + " / ".join(f"{v['effective_recall']}" for v in d["validation"]["per_class"].values())
                        + f" | {d['validation']['accepted_errors']} | {d['s0b']['unknown']} | {d['s0b']['false_non_normal_on_normal']} |")
    pv = lambda k: (f"| {k} | {par[k]['vectors']} | {par[k]['pred_mismatches']} | {par[k]['proba_max_abs_diff']:.2e} | "  # noqa: E731
                    f"{par[k]['min_top2_margin']:.3g} | {par[k]['exact_ties_sklearn']} | {par[k]['unknown_mismatches_at_tau']} |")
    size = "; ".join(f"{k}: text {v.get('text')} B, data {v.get('data')} B" for k, v in c.items() if k.endswith("_Os"))
    lines = [f"# Báo cáo export C99 RF bốn lớp M2-R6b (`{m['model_version']}`)", "",
             f"> Mô hình chọn ở M2-R6a, **không huấn luyện/chọn lại**; dữ liệu `SIMULATION` `{m['dataset_version']}`, nhãn proxy "
             f"`{m['label_source']}`; không phải độ chính xác ngoài thực tế. **Test-G1 chưa được nạp/đánh giá.** Sinh bởi "
             "`python -m ml.export.rf4_freeze_m2r6b`; header gitignored tại `ml/data/models/rf_four_class_m2r6/v03/c99/`, manifest "
             "đóng băng `ml/reports/ml/m2_r6b_frozen_model_manifest.json`. Không ghi `ml/export/model.h`, không sửa firmware.", "",
             "## Cấu trúc C99", "",
             f"- Header tự chứa `{c['header']}` (SHA-256 `{c['sha256'][:16]}…`, {c['bytes']} B), theo contract `model.h` của "
             "`firmware/src/infer.cpp`: `model_predict`, `model_predict_conf`, `model_predict_proba`; macro `SVMG_MODEL_VERSION`, "
             "`SVMG_MODEL_N_FEATURES` = 23, `SVMG_MODEL_FEATURE_SCHEMA_VERSION`, `SVMG_MODEL_PREPROCESSING_VERSION`, `SVMG_MODEL_HAS_PROBA`, "
             f"`SVMG_TAU_CONF` = {u['tau_conf']}.",
             f"- {c['n_trees']} cây, {c['total_nodes']} nút ({c['leaves']} lá, độ sâu ≤ {c['max_depth']}); mảng: feature int8, ngưỡng "
             f"float32 làm tròn xuống (x ≤ t32 ⇔ x ≤ t64 như sklearn), trái/phải int16, xác suất lá float32 × 4. Lớp = argmax trung bình "
             f"xác suất lá (cộng double), hòa → chỉ số lớp nhỏ nhất như numpy. Đầu vào NULL/sai độ dài/không hữu hạn → −1 "
             f"(infer.cpp đổi thành UNKNOWN). Ước tính mảng {c['model_array_bytes']} B; object `-Os`: {size}.",
             f"- Biên dịch `{' '.join(par['cflags'])}` sạch; probe C++ gnu++11 `-pedantic` (cách infer.cpp dùng): {c['cxx_gnu11_probe_ok']}; sinh lại tất định: "
             f"{c['deterministic_regeneration']}.", "",
             "## Chính sách UNKNOWN (chọn chỉ trên CORE Validation)", "",
             f"Độ tin cậy = {u['confidence']}. Quy tắc khai báo trước: {u['rule']}; dự phòng {u['fallback_tau']}. **Chọn tau = "
             f"{u['tau_conf']}**" + (" (theo quy tắc)." if u["rule_satisfied_by"] else " — **không tau nào đạt quy tắc** (kể cả 0,5: một "
             "cửa sổ AMPLITUDE_GROWTH có conf < 0,5), nên giữ giá trị dự phòng = mặc định `SVMG_TAU_CONF` của infer.cpp; không "
             "hạ tau dưới mặc định và không ánh xạ UNKNOWN thành NORMAL."), "",
             "| tau | Phủ Validation | Recall hiệu dụng N / H / P / G | Lỗi được chấp nhận | S0b UNKNOWN | S0b báo sai bất thường |",
             "|---:|---:|---:|---:|---:|---:|", *(row(t, d) for t, d in m["policy_table"].items()), "",
             "## Parity Python (sklearn) / C", "",
             "| Tập | Vector | Lệch lớp | Max |Δp| | Biên top-2 nhỏ nhất | Hòa chính xác | Lệch UNKNOWN |", "|---|---:|---:|---:|---:|---:|---:|",
             *(pv(k) for k in ("validation", "s0b", "threshold_boundaries")), "",
             f"Đầu vào lỗi (độ dài 22/24/0, NaN, ±inf) trả −1: {par['invalid_inputs']}.", "",
             "## Giới hạn", "",
             "- Độ tin cậy là tỉ lệ phiếu/xác suất lá chưa hiệu chuẩn; Validation chỉ 12 session (AMPLITUDE_GROWTH 10 cửa sổ/3 session), "
             "nên tau chỉ là chính sách bảo thủ có thể tái lập, không phải xác suất đúng.",
             "- Chưa đánh giá Test-G1 (đánh giá một lần, chỉ đọc, sau đóng băng); chưa đo thời gian suy luận trên ESP32 thật; chưa "
             "tích hợp firmware (M2-R7 cần M1 review).", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    r = run()
    print(json.dumps({"tau": r["unknown_policy"]["tau_conf"], "header_sha256": r["c_artifact"]["sha256"],
                      "parity": {k: r["parity"][k] for k in ("validation", "s0b", "threshold_boundaries", "invalid_inputs")}},
                     indent=1, default=float))
