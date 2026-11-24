"""M2-R6a: Random Forest bốn lớp (NORMAL, HIGH_ROLL, PERSISTENT_OFFSET, AMPLITUDE_GROWTH) trên dataset SIMULATION v0.2/v0.3.

Fit trên CORE Train, chọn cấu hình chỉ bằng CORE Validation trong một lưới nhỏ khai báo trước; đúng 23 đặc trưng theo contract
(không dùng độ phủ, session, nhãn, kịch bản, split hay provenance). Test-G1 KHÔNG được nạp ở bước này (chờ đóng băng). Không export
model.h, không tích hợp ESP32. Nhãn là proxy mô phỏng, không phải độ chính xác phát hiện nguy hiểm ngoài thực tế.

    .venv/bin/python -m ml.train.rf_four_class_m2r6
"""
from __future__ import annotations

import ctypes as ct
import json
import re
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_recall_fscore_support

from ml.train import four_class_experimental_dataset as v02
from ml.train import four_class_pilot_dataset as pilot
from ml.train import four_class_v03_dataset as v03
from ml.train.g1_simulation_dataset import ROOT, _features, _sha
from ml.train.rf_poc import serialize_model, tree_statistics, validate_feature_frame
from simulation.generator.config import DatasetSplit

MODEL_VERSION = "svmg-rf-four-class-m2r6a-0.1.0"
SEED = 20261124
FEATURES = list(_features())
CLASSES = list(pilot.CLASSES)                      # chỉ số = svmg_class_t 0..3
DATASETS = {"v0.2": (v02.OUT / "windows.csv", "b4b249d08dc2fae17476a62c2b596d14ead0ea1b8de75fd412a96d5110b4ad5c"),
            "v0.3": (v03.OUT / "windows.csv", "f3c893fcaa498fba9ebac62ffe9ab4a06632f50b0d97fd332547cf04fa15370c")}
# Lưới khai báo trước, từ gọn đến lớn (đều nằm trong ngân sách ESP32); hòa macro-F1 (3 chữ số) -> chọn cấu hình đứng trước.
GRID = [{"n_estimators": n, "max_depth": d, "min_samples_leaf": leaf, "class_weight": w}
        for n, d, leaf in ((15, 4, 5), (25, 6, 5), (40, 8, 3)) for w in (None, "balanced_subsample")]
GATE = {"macro_f1": 0.80, "min_class_recall": 0.50}  # cổng đủ dùng trên Validation, khai báo trước
COVERAGE_BINS = [0.0, 0.25, 0.5, 0.75, 1.0, 1.0001]
OUT = ROOT / "ml/data/models/rf_four_class_m2r6"
REPORT = ROOT / "ml/reports/ml/m2_r6a_four_class_rf_report.md"
TRAIN, VAL = DatasetSplit.TRAIN.value, DatasetSplit.VALIDATION.value


def load(path: Path) -> pd.DataFrame:
    """Chỉ cửa sổ có nhãn của Train/Validation (CORE + S0b); Test-G1 bị loại ngay khi đọc."""
    frame = pd.read_csv(path, low_memory=False)
    frame = frame.loc[frame.split.isin([TRAIN, VAL]) & frame.label.ne("ABSTAIN")].reset_index(drop=True)
    return frame.assign(y=frame.label.map(pilot.CLASSES).astype(int))


def matrix(frame: pd.DataFrame) -> np.ndarray:
    """Đúng 23 cột theo thứ tự contract, float32 như ESP32; không hữu hạn -> lỗi (không thay bằng 0)."""
    return validate_feature_frame(frame, FEATURES).astype(np.float32)


def make_model(params: dict) -> RandomForestClassifier:
    return RandomForestClassifier(**params, max_features="sqrt", random_state=SEED, n_jobs=1)


def metrics(y, pred) -> dict:
    p, r, f, s = precision_recall_fscore_support(y, pred, labels=range(4), zero_division=0)
    names = CLASSES + ["UNKNOWN"]
    labels = sorted(set(range(4)) | set(int(v) for v in pred))
    return {"n": int(len(y)), "accuracy": round(accuracy_score(y, pred), 4),
            "macro_f1": round(f1_score(y, pred, labels=range(4), average="macro", zero_division=0), 4),
            "weighted_f1": round(f1_score(y, pred, labels=range(4), average="weighted", zero_division=0), 4),
            "per_class": {c: {"precision": round(p[i], 4), "recall": round(r[i], 4), "f1": round(f[i], 4), "support": int(s[i])}
                          for i, c in enumerate(CLASSES)},
            "confusion_labels": [names[i] for i in labels], "confusion": confusion_matrix(y, pred, labels=labels).tolist(),
            "pred_counts": {names[i]: int((np.asarray(pred) == i).sum()) for i in labels}}


def wilson(k: int, n: int, z: float = 1.96) -> list[float] | None:
    if n == 0:
        return None
    p, d = k / n, 1 + z * z / n
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(float((p + z * z / (2 * n)) / d - half), 4), round(float(min(1.0, (p + z * z / (2 * n)) / d + half)), 4)]


def session_bootstrap(frame: pd.DataFrame, pred: np.ndarray, reps: int = 1000) -> list[float]:
    """KTC 95% macro-F1 khi lấy mẫu lại theo SESSION (cửa sổ trong một session không độc lập)."""
    rng, groups = np.random.default_rng(SEED), [np.flatnonzero(frame.session_id.eq(s)) for s in sorted(frame.session_id.unique())]
    scores = []
    for _ in range(reps):
        idx = np.concatenate([groups[i] for i in rng.integers(0, len(groups), len(groups))])
        scores.append(f1_score(frame.y.to_numpy()[idx], pred[idx], labels=range(4), average="macro", zero_division=0))
    return [round(float(np.percentile(scores, q)), 4) for q in (2.5, 97.5)]


def evaluate(frame: pd.DataFrame, pred: np.ndarray) -> dict:
    out, f = metrics(frame.y, pred), frame.assign(pred=pred, ok=pred == frame.y.to_numpy())
    sess = f.groupby("session_id").agg(label=("label", "first"), n=("ok", "size"), acc=("ok", "mean"),
                                       major=("pred", lambda p: CLASSES[int(p.mode().iloc[0])]))
    out["sessions"] = {k: {"label": r.label, "windows": int(r.n), "accuracy": round(r.acc, 4), "majority_pred": r.major}
                       for k, r in sess.iterrows()}
    out["sessions_majority_correct"] = f"{int((sess.label == sess.major).sum())}/{len(sess)}"
    out["sessions_per_class"] = {c: int(f.loc[f.label.eq(c), "session_id"].nunique()) for c in CLASSES}
    bins = pd.cut(f.target_coverage_180, COVERAGE_BINS, right=False)
    out["by_coverage"] = {str(b): {"n": int(len(g)), "accuracy": round(float(g.ok.mean()), 4)} for b, g in f.groupby(bins, observed=True)}
    out["macro_f1_session_bootstrap_95"] = session_bootstrap(frame, pred)
    g = f.loc[f.label.eq("AMPLITUDE_GROWTH")]
    tp, npred = int(g.ok.sum()), int((f.pred == 3).sum())
    out["growth"] = {"windows": int(len(g)), "sessions": int(g.session_id.nunique()), "recall_wilson_95": wilson(tp, len(g)),
                     "precision_wilson_95": wilson(tp, npred), "per_session_recall": g.groupby("session_id").ok.mean().round(4).to_dict()}
    wrong = f.loc[~f.ok]
    out["failures"] = {f"{t}->{CLASSES[p]}": {"windows": int(len(w)), "sessions": int(w.session_id.nunique()),
                                             "coverage_median": round(float(w.target_coverage_180.median()), 3)}
                       for (t, p), w in wrong.groupby(["label", "pred"])}
    return out


@lru_cache(maxsize=1)
def _baseline_lib() -> ct.CDLL:
    lib_path = Path(tempfile.mkdtemp(prefix="svmg-baseline-b-")) / "libbaseline_b.so"
    subprocess.run(["cc", "-std=c99", "-O2", "-shared", "-fPIC", "-I", str(ROOT / "core/include"),
                    str(ROOT / "core/src/baseline.c"), "-lm", "-o", str(lib_path)], check=True)
    lib = ct.CDLL(str(lib_path))
    lib.svmg_baseline_b.restype = ct.c_int
    return lib


def baseline_b(X: np.ndarray) -> np.ndarray:
    """Baseline B của Core C với tham số demo mặc định (không hiệu chỉnh lại). 23 float đầu của svmg_features_t theo thứ tự
    contract; vùng đệm 64 float phủ toàn bộ struct."""
    lib, params, buf = _baseline_lib(), (ct.c_float * 6)(), (ct.c_float * 64)()
    lib.svmg_baseline_default(ct.byref(params))
    out = []
    for row in X:
        buf[:23] = [float(v) for v in row]
        out.append(lib.svmg_baseline_b(ct.byref(params), ct.byref(buf)))
    return np.array(out)


def c_contract_check(model: RandomForestClassifier) -> dict:
    """Tương thích svmg_rf_fn: lớp = svmg_class_t 0..3, 23 đặc trưng đúng thứ tự SVMG_FEATURE_FIELDS, chỉ số nút vừa int16."""
    common = (ROOT / "core/include/svmg_common.h").read_text()
    enum = {m[0]: int(m[1]) for m in re.findall(r"SVMG_([A-Z_]+) = (\d)", common)}
    schema = (ROOT / "core/include/svmg_feature_schema.h").read_text()
    order = re.findall(r"X\((\w+)\)", schema.split("SVMG_FEATURE_FIELDS(X)")[1].split("#define")[0])
    n_features = int(re.search(r"SVMG_N_FEATURES (\d+)", schema)[1])
    return {"classes_match_svmg_class_t": [int(c) for c in model.classes_] == [enum[c] for c in CLASSES] == [0, 1, 2, 3],
            "feature_order_matches_core_header": order == FEATURES and n_features == model.n_features_in_ == 23,
            "nodes_fit_int16_index": sum(e.tree_.node_count for e in model.estimators_) <= 32767}


def train_dataset(tag: str, path: Path, sha: str | None, out_dir: Path | None) -> dict:
    if sha and _sha(path) != sha:
        raise RuntimeError(f"SHA dataset {tag} khác bản lịch sử; dừng.")
    data = load(path)
    core = data.loc[data.subset.eq("CORE")]
    train, val, s0b = core.loc[core.split.eq(TRAIN)], core.loc[core.split.eq(VAL)], data.loc[data.subset.eq("CHALLENGE_S0B")]
    if set(train.session_id) & set(val.session_id):
        raise RuntimeError("Session trùng giữa Train và Validation.")
    X_train, X_val = matrix(train), matrix(val)
    trials = []
    for i, params in enumerate(GRID):
        model = make_model(params).fit(X_train, train.y)
        m = metrics(val.y, model.predict(X_val))
        trials.append({"index": i, "params": params, "macro_f1": m["macro_f1"], "total_nodes": tree_statistics(model, X_val)["total_nodes"],
                       "min_class_recall": float(min(v["recall"] for v in m["per_class"].values()))})
    best = max(trials, key=lambda t: (round(t["macro_f1"], 3), -t["index"]))
    model, refit = (make_model(best["params"]).fit(X_train, train.y) for _ in range(2))
    pred, proba = model.predict(X_val), model.predict_proba(X_val)
    stats = tree_statistics(model, X_val)
    stats["estimated_c_bytes_4class"] = int(stats["internal_nodes"] * 12 + stats["leaves"] * 16)
    validation = evaluate(val.reset_index(drop=True), pred)
    gate = validation["macro_f1"] >= GATE["macro_f1"] and min(v["recall"] for v in validation["per_class"].values()) >= GATE["min_class_recall"]
    manifest = json.loads((path.parent / "manifest.json").read_text())
    result = {"dataset": tag, "dataset_version": manifest["dataset_version"], "dataset_sha256": _sha(path), "trials": trials,
              "selected": best, "validation": validation, "validation_gate_passed": bool(gate),
              "baseline_b_validation": metrics(val.y, baseline_b(X_val)),
              "s0b_challenge": {s: metrics(g.y, model.predict(matrix(g))) for s, g in s0b.groupby("split")},
              "train": {"windows": int(len(train)), "sessions": int(train.session_id.nunique()),
                        "sessions_per_class": {c: int(train.loc[train.label.eq(c), "session_id"].nunique()) for c in CLASSES}},
              "tree_statistics": stats, "c_contract": c_contract_check(model),
              "deterministic_refit": bool(np.array_equal(proba, refit.predict_proba(X_val)) and all(
                  np.array_equal(a.tree_.threshold, b.tree_.threshold) for a, b in zip(model.estimators_, refit.estimators_))),
              "mdi_importance_top5": dict(sorted(zip(FEATURES, model.feature_importances_.round(4).tolist()), key=lambda kv: -kv[1])[:5])}
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        meta = {"model_version": MODEL_VERSION, "dataset_version": manifest["dataset_version"], "dataset_sha256": result["dataset_sha256"],
                "sim_extension_version": manifest.get("sim_extension_version"), "label_source": manifest["label_source"],
                "label_policy": manifest["label_policy"], "dataset_source": "SIMULATION", "feature_names": FEATURES,
                "feature_schema_version": manifest["feature_schema_version"], "preprocessing_version": manifest["preprocessing_version"],
                "class_mapping": pilot.CLASSES, "seed": SEED, "params": {**best["params"], "max_features": "sqrt"}, "grid": GRID,
                "selection_rule": "max Validation macro-F1 (3 d.p.), tie -> earlier grid entry", "gate": GATE,
                "sklearn_version": sklearn.__version__, "numpy_version": np.__version__, "test_g1": "NOT_EVALUATED (frozen, pending)",
                "dataset_sources_sha256": manifest["sources_sha256"], "trainer_sha256": _sha(Path(__file__).resolve()),
                "not_a_safety_classifier": True}
        meta["model_sha256"] = serialize_model(model, out_dir / "model.joblib")
        (out_dir / "metadata.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n")
        (out_dir / "metrics.json").write_text(json.dumps(result, indent=1, ensure_ascii=False, default=float) + "\n")
        val[["session_id", "scenario", "window_end_seconds", "target_coverage_180", "label", "y"]].assign(
            pred=pred, **{f"proba_{CLASSES[c]}": proba[:, i].round(6) for i, c in enumerate(model.classes_)}).to_csv(
            out_dir / "validation_predictions.csv", index=False)
        result["model_sha256"] = meta["model_sha256"]
    return result


def run(out: Path = OUT, report: Path | None = REPORT) -> dict:
    results = {tag: train_dataset(tag, path, sha, out / tag.replace(".", "")) for tag, (path, sha) in DATASETS.items()}
    passed = [t for t in ("v0.3", "v0.2") if results[t]["validation_gate_passed"]]
    results["candidate"] = {"dataset": passed[0] if passed else None,
                            "rule": "v0.3 (gần miền cảm biến hơn) nếu qua cổng Validation, nếu không thì v0.2; không dùng Test-G1"}
    (out / "summary.json").write_text(json.dumps(results, indent=1, ensure_ascii=False, default=float) + "\n")
    if report:
        write_report(results, report)
    return results


def write_report(r: dict, path: Path) -> None:
    a, b = r["v0.2"], r["v0.3"]
    va, vb, ba, bb = a["validation"], b["validation"], a["baseline_b_validation"], b["baseline_b_validation"]
    prf = lambda d: f"{d['precision']:.3f} / {d['recall']:.3f} / {d['f1']:.3f}"  # noqa: E731
    cm = lambda m: "; ".join(f"{n}: {row}" for n, row in zip(CLASSES, m["confusion"])) + f" (cột: {', '.join(m['confusion_labels'])})"  # noqa: E731
    cov = lambda v: "; ".join(f"{k} {d['accuracy']:.3f} (n={d['n']})" for k, d in v["by_coverage"].items())  # noqa: E731
    fail = lambda v: "; ".join(f"{k}: {d['windows']} cửa sổ/{d['sessions']} session, phủ trung vị {d['coverage_median']}"  # noqa: E731
                               for k, d in v["failures"].items()) or "không"
    s0b = lambda x: "; ".join(f"{s} {m['accuracy']:.3f} (dự đoán {m['pred_counts']})" for s, m in x["s0b_challenge"].items())  # noqa: E731
    size = lambda x: (f"{x['tree_statistics']['n_estimators']} cây, độ sâu ≤ {x['tree_statistics']['max_depth']}, "  # noqa: E731
                      f"{x['tree_statistics']['total_nodes']} nút ({x['tree_statistics']['leaves']} lá), so sánh trung bình/tối đa mỗi lần suy luận "
                      f"{x['tree_statistics']['mean_comparisons_per_inference']:.0f}/{x['tree_statistics']['max_comparisons_per_inference']:.0f}, "
                      f"ước tính mảng C ≈ {x['tree_statistics']['estimated_c_bytes_4class']} B (12 B/nút trong + 16 B/lá 4 xác suất float32)")
    trials = [f"| {i} | {t['params']['n_estimators']} | {t['params']['max_depth']} | {t['params']['min_samples_leaf']} | "
              f"{t['params']['class_weight'] or 'None'} | {t['macro_f1']:.4f} / {t['total_nodes']} | {u['macro_f1']:.4f} / {u['total_nodes']} |"
              for i, (t, u) in enumerate(zip(a["trials"], b["trials"]))]
    row = lambda name, f: f"| {name} | {f(va)} | {f(vb)} | {f(ba)} | {f(bb)} |"  # noqa: E731
    lines = [f"# Báo cáo đánh giá Random Forest bốn lớp M2-R6a (`{MODEL_VERSION}`)", "",
             "> Dữ liệu `SIMULATION` (`svmg-four-class-exp-0.2.0` roll-only và `0.3.0` có pitch + nhiễu IMU), nhãn proxy "
             "`SIMULATION_SCENARIO_V2_CANDIDATE` sinh từ roll thật bằng ngưỡng đóng băng; RF học lại các luật này nên điểm cao "
             "**không** phải độ chính xác phát hiện nguy hiểm ngoài thực tế. Fit trên CORE Train (886 cửa sổ, 30 session), chọn chỉ bằng "
             "CORE Validation (469 cửa sổ, 12 session); **Test-G1 chưa được nạp/đánh giá**. Sinh bởi "
             "`python -m ml.train.rf_four_class_m2r6`; mô hình/artifact gitignored tại `ml/data/models/rf_four_class_m2r6/`.", "",
             f"## Cấu hình khai báo trước (Validation macro-F1 / tổng nút), seed {SEED}, `max_features=sqrt`", "",
             "| # | Cây | Độ sâu | Lá tối thiểu | class_weight | v0.2 | v0.3 |", "|---:|---:|---:|---:|---|---:|---:|", *trials, "",
             f"Quy tắc chọn: macro-F1 Validation lớn nhất (3 chữ số), hòa → cấu hình gọn hơn đứng trước. Cổng đủ dùng khai báo trước: "
             f"macro-F1 ≥ {GATE['macro_f1']} và recall mọi lớp ≥ {GATE['min_class_recall']}. Chọn: v0.2 #{a['selected']['index']}, "
             f"v0.3 #{b['selected']['index']}; qua cổng: v0.2 {a['validation_gate_passed']}, v0.3 {b['validation_gate_passed']}.", "",
             "## Validation CORE (cùng cửa sổ), so với Baseline B của Core C (tham số demo mặc định, không hiệu chỉnh lại)", "",
             "| Chỉ số | RF v0.2 | RF v0.3 | Baseline B v0.2 | Baseline B v0.3 |", "|---|---:|---:|---:|---:|",
             row("Accuracy", lambda m: m["accuracy"]), row("Macro-F1", lambda m: m["macro_f1"]), row("Weighted-F1", lambda m: m["weighted_f1"]),
             f"| KTC 95% macro-F1 (bootstrap theo session) | {va['macro_f1_session_bootstrap_95']} | {vb['macro_f1_session_bootstrap_95']} | – | – |",
             f"| Session đúng theo đa số | {va['sessions_majority_correct']} | {vb['sessions_majority_correct']} | – | – |",
             row("Số dự đoán theo lớp", lambda m: ", ".join(f"{k} {v}" for k, v in m["pred_counts"].items())), "",
             f"Ma trận nhầm lẫn (hàng = thật). RF v0.2: {cm(va)}. RF v0.3: {cm(vb)}. Baseline B v0.3: {cm(bb)}.", "",
             "| Lớp | Validation cửa sổ/session | Train session | RF v0.2 P / R / F1 | RF v0.3 P / R / F1 | Baseline B v0.3 P / R / F1 |",
             "|---|---:|---:|---:|---:|---:|",
             *(f"| {c} | {va['per_class'][c]['support']}/{va['sessions_per_class'][c]} | {a['train']['sessions_per_class'][c]} | "
               f"{prf(va['per_class'][c])} | {prf(vb['per_class'][c])} | {prf(bb['per_class'][c])} |" for c in CLASSES), "",
             "## Theo độ phủ `target_coverage_180`, S0b và lỗi chính", "",
             f"- Accuracy theo độ phủ, v0.2: {cov(va)}. v0.3: {cov(vb)}.",
             f"- S0b challenge (NORMAL, không dùng để fit): v0.2 {s0b(a)}; v0.3 {s0b(b)}.",
             f"- Lỗi RF v0.2: {fail(va)}. Lỗi RF v0.3: {fail(vb)}.", "",
             "## AMPLITUDE_GROWTH: nhóm Validation rất nhỏ", "",
             f"- Validation chỉ {vb['growth']['windows']} cửa sổ từ {vb['growth']['sessions']} session (Train: "
             f"{b['train']['sessions_per_class']['AMPLITUDE_GROWTH']} session). Recall Wilson 95%: v0.2 {va['growth']['recall_wilson_95']}, "
             f"v0.3 {vb['growth']['recall_wilson_95']}; precision Wilson 95%: v0.2 {va['growth']['precision_wilson_95']}, "
             f"v0.3 {vb['growth']['precision_wilson_95']}. Khoảng Wilson coi cửa sổ là độc lập nên còn lạc quan; theo session chỉ có 3 quan sát.",
             "- Chênh lệch v0.2/v0.3 ở lớp này đến từ một session NORMAL duy nhất bị đoán nhầm thành growth; KTC bootstrap theo session "
             "chồng lấn, nên chưa đủ bằng chứng nói pitch/nhiễu cải thiện mô hình.", "",
             "## Kích thước, tái lập và ứng viên", "",
             f"- RF v0.2: {size(a)}. RF v0.3: {size(b)}. Đặc trưng quan trọng nhất (MDI) v0.3: {b['mdi_importance_top5']}.",
             f"- Fit lại cùng seed cho cùng xác suất và cùng ngưỡng: v0.2 {a['deterministic_refit']}, v0.3 {b['deterministic_refit']}. "
             f"Kiểm tra contract C (`svmg_class_t`, thứ tự `SVMG_FEATURE_FIELDS`, chỉ số nút int16): v0.3 {b['c_contract']}.",
             f"- **Ứng viên: `{r['candidate']['dataset']}`** (quy tắc khai báo trước: {r['candidate']['rule']}). SHA mô hình: "
             f"`{b.get('model_sha256', '–')}`; SHA dataset `{b['dataset_sha256'][:12]}…`.",
             "- Giới hạn: 3 session mỗi lớp ở Validation; chọn trong 6 cấu hình trên chính Validation nên điểm lạc quan; chưa có Test-G1, "
             "Test-G2 hay dữ liệu MPU6050 thật; chưa export `model.h` và chưa đo trên ESP32.", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    r = run()
    print(json.dumps({t: {k: r[t][k] for k in ("selected", "validation_gate_passed", "deterministic_refit", "c_contract")}
                      for t in DATASETS} | {"candidate": r["candidate"]}, indent=1, default=float))
