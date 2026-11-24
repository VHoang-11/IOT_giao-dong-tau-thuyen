"""M2-R6c: đánh giá Test-G1 MỘT LẦN cho mô hình đóng băng `svmg-rf-four-class-m2r6a-0.1.0` (tau = 0,5), chỉ đọc.

Kiểm tra toàn vẹn (mô hình, dataset, manifest, header C99, schema, lớp, tách session) TRƯỚC khi đọc bất kỳ dòng Test-G1 nào.
Không huấn luyện, không chọn lại, không đổi tau/nhãn/đặc trưng. Kết quả lần đầu được khóa trong thư mục gitignored; chạy lại chỉ
được phép với ``--verify`` (tính lại và so khớp, không ghi đè).

    .venv/bin/python -m ml.eval.final_test_g1_m2r6c            # lần đánh giá duy nhất
    .venv/bin/python -m ml.eval.final_test_g1_m2r6c --verify   # tái lập: kết quả phải trùng bản đã khóa
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from ml.export import rf4_freeze_m2r6b as F
from ml.export import rf_c_export as E
from ml.train import four_class_experimental_dataset as v02
from ml.train import rf_four_class_m2r6 as R
from ml.train.g1_simulation_dataset import ROOT, _sha
from simulation.generator.config import DatasetSplit

TEST = DatasetSplit.TEST_G1.value
UNKNOWN = 4
OUT = F.MODEL_DIR / "test_g1"
REPORT = ROOT / "ml/reports/ml/m2_r6c_test_g1_final_report.md"


def verify_frozen() -> tuple:
    """Dừng (RuntimeError) nếu bất kỳ artifact đóng băng nào lệch; chưa đọc dữ liệu Test-G1."""
    manifest = json.loads(F.MANIFEST.read_text())
    model, meta = F.load_frozen()                    # SHA mô hình, metadata, schema/preprocessing so với Core C
    csv_path, dataset_sha = R.DATASETS["v0.3"]
    header = F.OUT / F.HEADER
    tau = manifest["unknown_policy"]["tau_conf"]
    regenerated = E.generate_model_h(model, R.FEATURES, F.c_metadata(meta), tau)[0]
    checks = {"manifest_status": manifest["status"] == "FROZEN_PENDING_TEST_G1",
              "model_sha256": manifest["model_sha256"] == F.FROZEN_MODEL_SHA256,
              "dataset_sha256": _sha(csv_path) == dataset_sha == manifest["dataset_sha256"],
              "tau_is_0_5": tau == 0.5, "feature_order": manifest["feature_names"] == R.FEATURES == list(meta["feature_names"]),
              "class_order": manifest["class_mapping"] == dict(zip(R.CLASSES, range(4))) and list(model.classes_) == [0, 1, 2, 3],
              "header_sha256": header.exists() and _sha(header) == manifest["c_artifact"]["sha256"],
              "header_regenerates_identically": E.hashlib.sha256(regenerated.encode()).hexdigest() == manifest["c_artifact"]["sha256"],
              "schema_preprocessing": (manifest["feature_schema_version"], manifest["preprocessing_version"])
              == (meta["feature_schema_version"], meta["preprocessing_version"])}
    sessions = json.loads((csv_path.parent / "manifest.json").read_text())["sessions"]
    test = [(s["scenario"], s["seed"]) for s in sessions if s["split"] == TEST]
    other = {s["seed"] for s in sessions if s["split"] != TEST}
    checks["test_g1_sessions_frozen"] = [(sc.value, seed) for sc, seed in v02.pilot_test_g1_sessions()] == test
    checks["test_g1_disjoint_from_train_validation"] = not {seed for _, seed in test} & other
    if not all(checks.values()):
        raise RuntimeError(f"Kiểm tra toàn vẹn thất bại, KHÔNG mở Test-G1: {[k for k, v in checks.items() if not v]}")
    return model, header, tau, checks, manifest


def apply_tau(proba: np.ndarray, tau: float) -> np.ndarray:
    """Như infer.cpp: conf (float32) < tau -> UNKNOWN (4); không bao giờ đổi thành NORMAL."""
    return np.where(proba.max(1).astype(np.float32) < np.float32(tau), UNKNOWN, proba.argmax(1))


def with_tau(y: np.ndarray, pred: np.ndarray) -> dict:
    """UNKNOWN tính là bỏ sót: recall/F1/accuracy hiệu dụng trên TOÀN BỘ cửa sổ, cộng độ phủ và accuracy trên phần được phân loại."""
    out = R.metrics(y, pred)
    accepted = pred != UNKNOWN
    out.update(coverage=round(float(accepted.mean()), 4), unknown=int((~accepted).sum()),
               selective_accuracy=round(float((pred == y)[accepted].mean()), 4) if accepted.any() else None,
               unknown_per_class={c: int((~accepted & (y == i)).sum()) for i, c in enumerate(R.CLASSES)})
    return out


def sessions_after_tau(frame: pd.DataFrame, pred: np.ndarray) -> dict:
    f = frame.assign(pred=pred, ok=pred == frame.y.to_numpy(), unk=pred == UNKNOWN)
    return {s: {"label": g.label.iloc[0], "windows": int(len(g)), "effective_accuracy": round(float(g.ok.mean()), 4),
                "unknown": int(g.unk.sum()), "wrong_class": int((~g.ok & ~g.unk).sum())} for s, g in f.groupby("session_id")}


def evaluate(split: str = TEST) -> dict:
    """``split`` khác Test-G1 chỉ dùng cho chạy thử/test pipeline (Validation phải tái tạo đúng số M2-R6a/R6b)."""
    model, header, tau, checks, manifest = verify_frozen()
    raw = pd.read_csv(R.DATASETS["v0.3"][0], low_memory=False)
    test_all = raw.loc[raw.split.eq(split)]
    test = test_all.loc[test_all.subset.eq("CORE") & test_all.label.ne("ABSTAIN")].reset_index(drop=True)
    test = test.assign(y=test.label.map(R.CLASSES.index))
    X = R.matrix(test)
    proba = model.predict_proba(X)
    pred, pred_tau = proba.argmax(1), apply_tau(proba, tau)
    with tempfile.TemporaryDirectory() as tmp:
        binary = E.build_runner4(header, Path(tmp))
        parity = E.parity4(binary, model, X, tau)
        c_rows = E.run_vectors4(binary, X.tolist())
    c_tau = np.array([UNKNOWN if r[0] < 0 or np.float32(r[3]) < np.float32(tau) else r[0] for r in c_rows])
    parity["c_final_class_mismatches_after_tau"] = int((c_tau != pred_tau).sum())
    y = test.y.to_numpy()
    growth = test.assign(pred=pred_tau, conf=proba.max(1).round(4))
    growth_fail = growth.loc[(growth.y.eq(3) & growth.pred.ne(3)) | (growth.y.ne(3) & growth.pred.eq(3))]
    validation = json.loads((F.MODEL_DIR / "metrics.json").read_text())["validation"]
    return {"task": "M2-R6c", "split": split, "integrity_checks": checks, "tau": tau,
            "test_g1_windows_all": int(len(test_all)), "test_g1_sessions": int(test_all.session_id.nunique()),
            "test_g1_abstain_reasons": test_all.loc[test_all.label.eq("ABSTAIN"), "exclusion_reason"].value_counts().sort_index().to_dict(),
            "labeled_windows": int(len(test)), "before_tau": R.evaluate(test, pred), "after_tau": with_tau(y, pred_tau),
            "sessions_after_tau": sessions_after_tau(test, pred_tau),
            "baseline_b": with_tau(y, R.baseline_b(X)), "c99_parity": parity,
            "growth_failures": growth_fail[["session_id", "window_end_seconds", "target_coverage_180", "label", "pred", "conf"]]
            .assign(pred=lambda d: d.pred.map(lambda p: (R.CLASSES + ["UNKNOWN"])[p])).to_dict("records"),
            "validation_reference": {k: validation[k] for k in ("accuracy", "macro_f1", "weighted_f1", "per_class")},
            "validation_tau_reference": manifest["policy_table"][str(tau)]["validation"]}


def run(verify: bool = False, out: Path = OUT, report: Path | None = REPORT, report_only: bool = False) -> dict:
    locked = out / "results.json"
    if report_only:                                   # chỉ dựng lại báo cáo từ kết quả đã khóa, không đánh giá lại
        result = json.loads(locked.read_text(encoding="utf-8"))
        write_report(result, report or REPORT)
        return result
    if locked.exists() and not verify:
        raise RuntimeError("Test-G1 đã được đánh giá; không chạy lại. Dùng --verify để kiểm tra tái lập.")
    if verify and not locked.exists():
        raise RuntimeError("Chưa có kết quả khóa để kiểm tra.")
    result = evaluate()
    text = json.dumps(result, indent=1, ensure_ascii=False, sort_keys=True, default=float) + "\n"
    if verify:
        if text != locked.read_text(encoding="utf-8"):
            raise RuntimeError("Kết quả tính lại KHÁC bản đã khóa.")
        return result
    out.mkdir(parents=True, exist_ok=True)
    locked.write_text(text, encoding="utf-8")
    if report:
        write_report(result, report)
    return result


SUMMARY = ROOT / "ml/reports/ml/m2_r6c_test_g1_metrics_summary.json"


def export_summary(out: Path = OUT, path: Path = SUMMARY) -> dict:
    """Tóm tắt gọn, commit được, từ kết quả Test-G1 ĐÃ KHÓA (chỉ đọc results.json; KHÔNG đánh giá lại) cho bản clone sạch."""
    locked = out / "results.json"
    r = json.loads(locked.read_text(encoding="utf-8"))
    pick = lambda d, keys: {k: d[k] for k in keys}  # noqa: E731
    base = ("n", "accuracy", "macro_f1", "weighted_f1", "confusion_labels", "confusion", "per_class", "pred_counts")
    s = {"source": "ml/data/models/rf_four_class_m2r6/v03/test_g1/results.json (M2-R6c, locked, read-only)",
         "source_sha256": _sha(locked), "model_version": R.MODEL_VERSION, "dataset_sha256": R.DATASETS["v0.3"][1], "tau": r["tau"],
         "test_g1_sessions": r["test_g1_sessions"], "labeled_windows": r["labeled_windows"],
         "before_tau": pick(r["before_tau"], (*base, "macro_f1_session_bootstrap_95", "sessions_per_class", "sessions_majority_correct",
                                              "by_coverage", "growth", "failures")),
         "after_tau": r["after_tau"], "baseline_b": pick(r["baseline_b"], (*base, "coverage")), "c99_parity": r["c99_parity"],
         "sessions_after_tau": r["sessions_after_tau"], "growth_failures": r["growth_failures"]}
    path.write_text("{\n" + ",\n".join(f" {json.dumps(k)}: {json.dumps(v, ensure_ascii=False, default=float)}" for k, v in s.items())
                    + "\n}\n", encoding="utf-8")
    return s


def demo_ready(r: dict) -> bool:
    """Tiêu chí khai báo TRƯỚC khi mở Test-G1 (cùng cổng M2-R6a, tính SAU tau): macro-F1 hiệu dụng >= 0,80, recall hiệu dụng mọi lớp
    >= 0,5 và parity C99 không lệch. Chỉ nói về demo Wokwi trên dữ liệu mô phỏng, không phải triển khai an toàn."""
    a, p = r["after_tau"], r["c99_parity"]
    return (a["macro_f1"] >= R.GATE["macro_f1"] and min(v["recall"] for v in a["per_class"].values()) >= R.GATE["min_class_recall"]
            and p["pred_mismatches"] == 0 and p["c_final_class_mismatches_after_tau"] == 0)


def write_report(r: dict, path: Path) -> None:
    b, a, base, v, vt, par = r["before_tau"], r["after_tau"], r["baseline_b"], r["validation_reference"], r["validation_tau_reference"], r["c99_parity"]
    names = R.CLASSES + ["UNKNOWN"]
    cm = lambda m: "\n".join(f"| {names[i]} | " + " | ".join(map(str, row)) + " |" for i, row in enumerate(m["confusion"][:4]))  # noqa: E731
    head = lambda m: ("| Thật \\ Dự đoán | " + " | ".join(m["confusion_labels"]) + " |\n|---|" + "---:|" * len(m["confusion_labels"]))  # noqa: E731
    prf = lambda d: f"{d['precision']:.3f} / {d['recall']:.3f} / {d['f1']:.3f}"  # noqa: E731
    bad = {k: s for k, s in r["sessions_after_tau"].items() if s["effective_accuracy"] < 1.0}
    ready = demo_ready(r)
    lines = [f"# Báo cáo đánh giá Test-G1 cuối cùng M2-R6c (`{R.MODEL_VERSION}`)", "",
             "> Đánh giá **một lần, chỉ đọc** mô hình đóng băng (M2-R6a/R6b) trên Test-G1 của `svmg-four-class-exp-0.3.0` (`SIMULATION`, "
             "nhãn proxy `SIMULATION_SCENARIO_V2_CANDIDATE`). Không huấn luyện/chọn lại, không đổi tau, nhãn, đặc trưng hay exporter. "
             "Sinh bởi `python -m ml.eval.final_test_g1_m2r6c`; kết quả khóa (gitignored) tại "
             "`ml/data/models/rf_four_class_m2r6/v03/test_g1/results.json`, kiểm tra tái lập bằng `--verify`.", "",
             "## 1. Xác minh artifact đóng băng (trước khi mở Test-G1)", "",
             ", ".join(f"`{k}`={val}" for k, val in r["integrity_checks"].items()) + f". tau = {r['tau']}.", "",
             "## 2. Phân bố Test-G1", "",
             f"- {r['test_g1_sessions']} session, {r['test_g1_windows_all']} cửa sổ; {r['labeled_windows']} cửa sổ CORE có nhãn được đánh giá.",
             "- Cửa sổ/session có nhãn theo lớp: " + "; ".join(f"{c} {b['per_class'][c]['support']}/{b['sessions_per_class'][c]}" for c in R.CLASSES) + ".",
             "- ABSTAIN (không đánh giá): " + ", ".join(f"{k} {n}" for k, n in r["test_g1_abstain_reasons"].items()) + ".", "",
             "## 3. Kết quả cuối cùng", "",
             "| Chỉ số | RF trước tau | RF sau tau = 0,5 (UNKNOWN = bỏ sót) | Baseline B (cùng cửa sổ) | RF Validation trước / sau tau |",
             "|---|---:|---:|---:|---:|",
             f"| Accuracy | {b['accuracy']} | {a['accuracy']} | {base['accuracy']} | {v['accuracy']} / – |",
             f"| Macro-F1 | {b['macro_f1']} | {a['macro_f1']} | {base['macro_f1']} | {v['macro_f1']} / – |",
             f"| Weighted-F1 | {b['weighted_f1']} | {a['weighted_f1']} | {base['weighted_f1']} | {v['weighted_f1']} / – |",
             f"| Tỉ lệ được phân loại | 1.0 | {a['coverage']} | {base['coverage']} | 1.0 / {vt['coverage']} |",
             f"| Accuracy trên phần được phân loại | {b['accuracy']} | {a['selective_accuracy']} | {base['selective_accuracy']} | – |",
             f"| KTC 95% macro-F1 trước tau (bootstrap theo session) | {b['macro_f1_session_bootstrap_95']} | – | – | – |", "",
             f"Macro-F1 trước tau giảm từ {v['macro_f1']} (Validation) xuống {b['macro_f1']} (Test-G1): Validation chỉ 12 session và đã "
             "dùng để chọn cấu hình nên lạc quan; Test-G1 là ước lượng trung thực hơn trong cùng miền mô phỏng.", "",
             "Precision / recall / F1 theo lớp (sau tau là recall hiệu dụng):", "",
             "| Lớp | RF trước tau | RF sau tau | Baseline B | Recall hiệu dụng Validation sau tau |", "|---|---:|---:|---:|---:|",
             *(f"| {c} | {prf(b['per_class'][c])} | {prf(a['per_class'][c])} | {prf(base['per_class'][c])} | "
               f"{vt['per_class'][c]['effective_recall']} |" for c in R.CLASSES), "",
             "Ma trận nhầm lẫn RF trước tau:", "", head(b), cm(b), "", "RF sau tau:", "", head(a), cm(a), "", "Baseline B:", "", head(base), cm(base), "",
             "## 4. UNKNOWN, độ phủ nhãn và lỗi", "",
             f"- UNKNOWN sau tau: {a['unknown']} cửa sổ, theo lớp thật {a['unknown_per_class']}; không UNKNOWN nào được tính là đúng.",
             "- Accuracy trước tau theo `target_coverage_180`: " + "; ".join(f"{k} {d['accuracy']} (n={d['n']})" for k, d in b["by_coverage"].items()) + ".",
             f"- AMPLITUDE_GROWTH: {b['growth']['windows']} cửa sổ/{b['growth']['sessions']} session; recall Wilson 95% trước tau "
             f"{b['growth']['recall_wilson_95']}, precision {b['growth']['precision_wilson_95']}. Ca lỗi liên quan GROWTH sau tau: "
             + ("; ".join(f"{g['session_id']} t={g['window_end_seconds']:.0f}s phủ {g['target_coverage_180']:.3f} {g['label']}→{g['pred']} "
                          f"(conf {g['conf']})" for g in r["growth_failures"]) or "không") + ".",
             "- Lỗi trước tau: " + ("; ".join(f"{k}: {d['windows']} cửa sổ/{d['sessions']} session" for k, d in b["failures"].items()) or "không") + ".",
             f"- Session đúng theo đa số (trước tau): {b['sessions_majority_correct']}. Session có lỗi/UNKNOWN sau tau: "
             + ("; ".join(f"{k} ({s['label']}): acc hiệu dụng {s['effective_accuracy']}, UNKNOWN {s['unknown']}, sai lớp {s['wrong_class']}"
                          for k, s in bad.items()) or "không") + ".", "",
             "## 5. Parity C99 / Python trên Test-G1", "",
             f"{par['vectors']} vector: lệch lớp {par['pred_mismatches']}, lệch lớp cuối sau tau {par['c_final_class_mismatches_after_tau']}, "
             f"lệch UNKNOWN {par['unknown_mismatches_at_tau']}, max |Δp| {par['proba_max_abs_diff']:.2e}, biên top-2 nhỏ nhất "
             f"{par['min_top2_margin']:.3g}, hòa chính xác {par['exact_ties_sklearn']}.", "",
             "## 6. Giới hạn", "",
             "- Nhãn và đặc trưng cùng sinh từ một bộ mô phỏng; nhãn là proxy theo ngưỡng labeling-v2 candidate, RF học lại các luật đó. "
             "Kết quả **không** phải độ chính xác phát hiện nguy hiểm, không phải dự báo lật tàu hay đánh giá GM/GZ.",
             "- Test-G1 cùng miền tham số với Train/Validation (không phải Test-G2 hay dữ liệu MPU6050 thật); số session mỗi lớp nhỏ, "
             "cửa sổ trong một session không độc lập. tau = 0,5 là giá trị dự phòng, độ tin cậy chưa hiệu chuẩn.", "",
             "## 7. Sẵn sàng tích hợp ESP32", "",
             f"- Tiêu chí khai báo trước (macro-F1 hiệu dụng ≥ {R.GATE['macro_f1']}, recall hiệu dụng mọi lớp ≥ {R.GATE['min_class_recall']}, "
             f"parity C99 không lệch): **{'ĐẠT' if ready else 'KHÔNG ĐẠT'}**.",
             f"- Rủi ro chính: {sum(row[3] for row in a['confusion'][:3])} cửa sổ không phải GROWTH bị báo AMPLITUDE_GROWTH sau tau "
             f"(precision GROWTH {a['per_class']['AMPLITUDE_GROWTH']['precision']}); UNKNOWN tập trung ở PERSISTENT_OFFSET "
             f"({a['unknown_per_class']['PERSISTENT_OFFSET']} cửa sổ). Firmware xử lý UNKNOWN là trạng thái UNKNOWN, không phải NORMAL.",
             ("- Có thể dùng header đóng băng cho **demo Wokwi trên dữ liệu mô phỏng** (M2-R7, cần M1 review `model.h`); chưa phải "
              "triển khai an toàn trên tàu thật, cần đo thời gian suy luận ESP32 và dữ liệu cảm biến thật." if ready else
              "- Không tích hợp vào demo cho tới khi có mô hình mới được chọn trên Validation và đánh giá trên tập kiểm tra mới; "
              "không chỉnh mô hình theo Test-G1."), ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="M2-R6c: đánh giá Test-G1 một lần cho RF bốn lớp đóng băng.")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--report-only", action="store_true")
    parser.add_argument("--export-summary", action="store_true", help="chỉ đọc kết quả đã khóa, ghi tóm tắt commit được")
    args = parser.parse_args()
    if args.export_summary:
        print(export_summary()["source_sha256"])
        return
    r = run(args.verify, report_only=args.report_only)
    print(json.dumps({"before_tau": {k: r["before_tau"][k] for k in ("accuracy", "macro_f1")},
                      "after_tau": {k: r["after_tau"][k] for k in ("accuracy", "macro_f1", "coverage", "unknown")},
                      "parity": r["c99_parity"]}, indent=1, default=float))


if __name__ == "__main__":
    main()
