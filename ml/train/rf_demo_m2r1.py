"""M2-R1: RF compact trên Hohai đã xử lý + export C cho demo replay CÔ LẬP (không tích hợp firmware). Chạy từ repo root:
``.venv/bin/python -m ml.train.rf_demo_m2r1`` (cần ml/data/labels/proxy_v1). NEG = proxy-negative (KHÔNG phải NORMAL đã
kiểm chứng), POS = RELATIVE_HIGH_ROLL proxy-positive; ABSTAIN loại khỏi train/metric, báo cáo riêng. Tiền xử lý Hohai
KHÔNG tương đương chuỗi IMU production."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from ml.eval.metrics import binary_metrics, group_bootstrap_f1, per_group_metrics
from ml.export import rf_c_export
from ml.labeling.ai_assisted_review import protected_checksums
from ml.labeling.proxy_rules import ABSTAIN, NEG, POS
from ml.train.grouping import leave_one_group_out
from ml.train.rf_poc import FEATURE_ORDER, feature_schema, fold_frame, make_model, tree_statistics, validate_feature_frame

FEATURES = list(FEATURE_ORDER)
XTENSA_BIN = Path.home() / ".platformio/packages/toolchain-xtensa-esp-elf/bin"
PROXY_NOTE = ("Nhãn sinh từ luật ngưỡng trên chính các feature (roll_std_60 theo phân vị hiệu chuẩn); điểm cao chủ yếu cho "
              "thấy RF tái tạo được luật proxy, KHÔNG chứng minh phân loại nguy hiểm đã kiểm chứng.")


def fold_data(domain, by_fold, fold, target):
    frame = fold_frame(domain, by_fold, fold, target)
    status = frame[f"{target}_status"]
    train = frame.loc[frame.split_role.eq("train") & status.isin([POS, NEG])]
    return train, frame.loc[frame.split_role.eq("test")], status.loc[frame.split_role.eq("test")]


def grouped_evaluation(domain, by_fold, folds, target, config):
    rows, per_fold = [], []
    for fold in folds:
        train, test, status = fold_data(domain, by_fold, fold["fold"], target)
        model = make_model(config["compact_model"], config, config["seed"]).fit(validate_feature_frame(train, FEATURES), train.y_true)
        score = model.predict_proba(validate_feature_frame(test, FEATURES))[:, 1]
        out = test[["experiment_group", "session_id", "y_true"]].assign(status=status.to_numpy(), score=score, pred=(score >= 0.5).astype(int))
        rows.append(out)
        per_fold.append({"test_group": fold["test_groups"][0], "train_windows": int(len(train)),
                         "train_positive": int(train.y_true.sum()), "total_nodes": int(sum(e.tree_.node_count for e in model.estimators_)),
                         "abstain_windows": int(out.status.eq(ABSTAIN).sum()),
                         "abstain_predicted_positive": int(out.pred[out.status.eq(ABSTAIN)].sum())})
    pred = pd.concat(rows, ignore_index=True)
    labeled = pred.loc[pred.status.isin([POS, NEG])]
    return {"pooled_confusion": binary_metrics(labeled.y_true, labeled.pred, labeled.score),
            "per_group": per_group_metrics(labeled, "pred", "score"),
            "group_bootstrap": group_bootstrap_f1(labeled, "pred", config["bootstrap_replicates"], config["seed"]),
            "independent_groups": int(labeled.experiment_group.nunique()),
            "groups_with_positive": int(labeled.loc[labeled.y_true.eq(1), "experiment_group"].nunique()),
            "folds": per_fold, "probability_threshold": 0.5}


def parity(binary: Path, model, X: np.ndarray, tol: float = 1e-6) -> dict:
    py_score = model.predict_proba(X)[:, 1]
    status, c_pred, c_score = map(np.array, zip(*rf_c_export.run_vectors(binary, X.tolist())))
    diff = np.abs(c_score - py_score)
    return {"vectors": int(len(X)), "c_status_nonzero": int((status != 0).sum()),
            "pred_mismatches": int((c_pred != (py_score >= 0.5)).sum()), "score_max_abs_diff": float(diff.max()),
            "score_tolerance": tol, "score_over_tolerance": int((diff > tol).sum()),
            "min_abs_margin_to_threshold": float(np.abs(py_score - 0.5).min()), "python_positive": int((py_score >= 0.5).sum())}


def invalid_input_checks(binary: Path, x: np.ndarray) -> dict:
    cases = {"length_22": (x[:22], "ERR_LENGTH"), "length_24": (np.r_[x, 0.0], "ERR_LENGTH"), "length_0": (x[:0], "ERR_LENGTH"),
             "nan_feature": (np.where(np.arange(23) == 3, np.nan, x), "ERR_NONFINITE"),
             "inf_feature": (np.where(np.arange(23) == 20, np.inf, x), "ERR_NONFINITE")}
    results = rf_c_export.run_vectors(binary, [v.tolist() for v, _ in cases.values()])
    return {k: {"status": s, "pred": p, "expected": e, "passed": s == rf_c_export.STATUS[e] and p == -1}
            for (k, (_, e)), (s, p, _) in zip(cases.items(), results)}


def run(repo_root: Path, config_path: Path) -> dict:
    repo_root = repo_root.resolve()
    before = protected_checksums(repo_root)
    config = yaml.safe_load((repo_root / config_path).read_text(encoding="utf-8"))
    demo, proxy_root = config["demo_export"], repo_root / config["proxy_output_root"]
    target, out_dir, name = demo["target"], repo_root / demo["output_root"], demo["c_name"]
    summary = json.loads((repo_root / config["proxy_summary"]).read_text(encoding="utf-8"))
    if summary["readiness"][config["domain"]]["targets"][target]["decision"] != "TRAINABLE":
        raise RuntimeError(f"{target} không TRAINABLE theo readiness; dừng.")
    measurements = pd.read_parquet(proxy_root / "measurements.parquet")
    by_fold = pd.read_parquet(proxy_root / "proxy_labels_by_fold.parquet")
    hohai = measurements.loc[measurements.dataset_source.eq(config["domain"])]
    domain = hohai.loc[hohai.angle23_complete].reset_index(drop=True)
    folds = leave_one_group_out(domain.experiment_group)
    evaluation = grouped_evaluation(domain, by_fold, folds, target, config)

    fold = next(f for f in folds if f["test_groups"] == [demo["holdout_group"]])
    train, heldout, held_status = fold_data(domain, by_fold, fold["fold"], target)
    X_train, X_held = validate_feature_frame(train, FEATURES), validate_feature_frame(heldout, FEATURES)
    model, refit = (make_model(config["compact_model"], config, config["seed"]).fit(X_train, train.y_true) for _ in range(2))
    metadata = {"model_version": demo["model_version"], "target": f"{target}_PROXY_BINARY", "label_source": "PROXY_RULE",
                "rule_version": summary["rule_version"], "domain": config["domain"], "seed": config["seed"],
                "params": config["compact_model"], "train_groups": fold["train_groups"], "holdout_group": demo["holdout_group"],
                "feature_spec_version": "|".join(sorted(domain.feature_spec_version.unique())),
                "preprocessing_configuration_sha256": "|".join(sorted(domain.preprocessing_configuration_sha256.unique())),
                "production_preprocessing_equivalent": False, "not_a_safety_classifier": True}
    export = rf_c_export.write_c(model, FEATURES, metadata, out_dir, name)
    deterministic = rf_c_export.generate_c(refit, FEATURES, metadata, name)[:2] == rf_c_export.generate_c(model, FEATURES, metadata, name)[:2]
    binary = rf_c_export.build_runner(export, name, out_dir)
    size = {"host": rf_c_export.object_size(export["paths"]["source"], shutil.which("cc"), "size", out_dir / "model_host.o")}
    if (XTENSA_BIN / "xtensa-esp32-elf-gcc").is_file():
        size["esp32_xtensa_Os"] = rf_c_export.object_size(export["paths"]["source"], str(XTENSA_BIN / "xtensa-esp32-elf-gcc"),
                                                          str(XTENSA_BIN / "xtensa-esp32-elf-size"), out_dir / "model_esp32.o")
    labeled, held_score = held_status.isin([POS, NEG]).to_numpy(), model.predict_proba(X_held)[:, 1]
    replay = heldout[["window_id", "session_id", "window_end_seconds"]].assign(
        proxy_status=held_status.to_numpy(), python_score=held_score, python_pred=(held_score >= 0.5).astype(int)).reset_index(drop=True)
    pd.concat([replay, pd.DataFrame(X_held.astype(np.float32), columns=FEATURES)], axis=1).to_csv(
        out_dir / "heldout_replay_vectors.csv", index=False, float_format="%.9g")
    results = {
        "task": "M2-R1", "status": "EXPERIMENTAL_ISOLATED_DEMO", "proxy_note": PROXY_NOTE, "feature_schema": feature_schema(),
        "metadata": metadata, "data": {"hohai_windows": int(len(hohai)), "angle23_complete_windows": int(len(domain)),
                                       "sessions": int(domain.session_id.nunique()), "independent_groups": int(domain.experiment_group.nunique())},
        "grouped_evaluation": evaluation,
        "demo_model": {"train_windows": int(len(train)), "train_positive": int(train.y_true.sum()),
                       "heldout_windows": int(len(heldout)), "heldout_abstain": int((~labeled).sum()),
                       "heldout_metrics": binary_metrics(heldout.y_true[labeled], held_score[labeled] >= 0.5, held_score[labeled]),
                       "deterministic_refit_identical_c": bool(deterministic), "tree_statistics": tree_statistics(model, X_held),
                       "export": {**export, "paths": {k: p.relative_to(repo_root).as_posix() for k, p in export["paths"].items()}},
                       "object_size_bytes": size},
        "parity": {"heldout": parity(binary, model, X_held),
                   "all_hohai_complete_windows": parity(binary, model, validate_feature_frame(domain, FEATURES)),
                   "invalid_inputs": invalid_input_checks(binary, X_held[0])}}
    if protected_checksums(repo_root) != before:
        raise RuntimeError("Human-review ledger/verified label bị thay đổi; dừng lại.")
    results["protected_files_unchanged"] = True
    (out_dir / "results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False, default=float), encoding="utf-8")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="M2-R1: RF compact Hohai + export C demo cô lập.")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--config", type=Path, default=Path("ml/train/rf_poc_config.yaml"))
    args = parser.parse_args()
    r = run(args.repo_root, args.config)
    brief = {"data": r["data"], "pooled": r["grouped_evaluation"]["pooled_confusion"], "parity": r["parity"],
             **{k: r["demo_model"][k] for k in ("heldout_metrics", "object_size_bytes", "deterministic_refit_identical_c")}}
    print(json.dumps(brief, indent=1, default=float))


if __name__ == "__main__":
    main()
