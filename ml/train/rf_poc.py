"""Random Forest PoC tái tạo proxy motion phenotype (KHÔNG phải bộ phân loại an toàn hàng hải).

Chạy từ repository root (cần chạy ``python -m ml.labeling.proxy_dataset`` trước)::

    python -m ml.train.rf_poc --config ml/train/rf_poc_config.yaml

Quy trình: chỉ target qua cổng readiness được huấn luyện; nested leave-one-experiment-group-out:
outer fold giữ một điều kiện thử nghiệm Hohai làm test; nhãn của fold dùng hiệu chuẩn fit trên nhóm train;
siêu tham số và ngưỡng xác suất chọn bằng GroupKFold bên trong tập train. Test không ảnh hưởng lựa chọn.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import platform
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
import yaml
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import average_precision_score

from ml.baselines.proxy_baselines import FEATURE_RULE_BASELINES, feature_quantile_rule, majority
from ml.eval.metrics import best_f1_threshold, binary_metrics, group_bootstrap_f1, per_group_metrics
from ml.labeling.ai_assisted_review import protected_checksums
from ml.labeling.human_review_workflow import ANGLE_FEATURES
from ml.labeling.proxy_rules import ABSTAIN, NEG, POS, load_spec
from ml.train.grouping import audit_split, inner_group_folds, leave_one_group_out

FEATURE_ORDER = tuple(ANGLE_FEATURES)


def feature_schema(columns=FEATURE_ORDER) -> dict:
    names = list(columns)
    return {"names": names, "count": len(names), "dtype": "float32-compatible float64",
            "sha256": hashlib.sha256("\n".join(names).encode()).hexdigest()}


def resolve_feature_set(definition) -> list[str]:
    if definition == "all":
        return list(FEATURE_ORDER)
    drop = set(definition["drop"])
    unknown = drop - set(FEATURE_ORDER)
    if unknown:
        raise ValueError(f"Feature không tồn tại trong schema 23: {sorted(unknown)}")
    return [name for name in FEATURE_ORDER if name not in drop]


def make_model(params: dict, config: dict, seed: int) -> RandomForestClassifier:
    return RandomForestClassifier(n_estimators=params.get("n_estimators", config["n_estimators"]),
                                  max_depth=params["max_depth"], min_samples_leaf=params["min_samples_leaf"],
                                  class_weight=params["class_weight"],
                                  max_features=params.get("max_features", config["max_features"]),
                                  random_state=seed, n_jobs=-1)


def validate_feature_frame(frame: pd.DataFrame, features: list[str]) -> np.ndarray:
    missing = [f for f in features if f not in frame.columns]
    if missing:
        raise ValueError(f"Thiếu feature theo schema: {missing}")
    X = frame[features].to_numpy(dtype=float)
    if not np.all(np.isfinite(X)):
        raise ValueError("Feature không hữu hạn; không được thay bằng 0. Hãy ABSTAIN các cửa sổ này.")
    return X


def select_hyperparameters(train: pd.DataFrame, features: list[str], config: dict, seed: int) -> dict:
    """Chọn siêu tham số bằng GroupKFold bên trong tập train; trả cấu hình, điểm và ngưỡng F1."""
    X, y = validate_feature_frame(train, features), train.y_true.to_numpy(int)
    folds = inner_group_folds(train.experiment_group.reset_index(drop=True), config["inner_group_splits"])
    trials = []
    for index, params in enumerate(config["grid"]):
        scores = np.full(len(train), np.nan)
        for fit_index, val_index in folds:
            if len(np.unique(y[fit_index])) < 2:
                continue
            model = make_model(params, config, seed).fit(X[fit_index], y[fit_index])
            scores[val_index] = model.predict_proba(X[val_index])[:, 1]
        mask = np.isfinite(scores)
        ap = float(average_precision_score(y[mask], scores[mask])) if mask.any() and 0 < y[mask].sum() < mask.sum() else -1.0
        trials.append({"index": index, "params": params, "inner_pooled_average_precision": ap, "scores": scores})
    best = max(trials, key=lambda t: (round(t["inner_pooled_average_precision"], 10), -t["index"]))
    mask = np.isfinite(best["scores"])
    threshold = best_f1_threshold(y[mask], best["scores"][mask])
    return {"params": best["params"], "inner_pooled_average_precision": best["inner_pooled_average_precision"],
            "probability_threshold": threshold,
            "trials": [{k: v for k, v in t.items() if k != "scores"} for t in trials]}


def fold_frame(measurements: pd.DataFrame, by_fold: pd.DataFrame, fold: int, target: str) -> pd.DataFrame:
    labels = by_fold.loc[by_fold.fold.eq(fold), ["window_id", f"{target}_status", "split_role", "calibration_id"]]
    frame = measurements.merge(labels, on="window_id", validate="one_to_one")
    frame["y_true"] = frame[f"{target}_status"].eq(POS).astype(int)
    return frame


def run_target(measurements: pd.DataFrame, by_fold: pd.DataFrame, calibrations: list[dict], target: str,
               config: dict, spec: dict) -> dict:
    seed = config["seed"]
    domain = measurements.loc[measurements.dataset_source.eq(config["domain"]) & measurements.angle23_complete].reset_index(drop=True)
    folds = leave_one_group_out(domain.experiment_group)
    q_rule = spec["rules"][target]["positive_quantile"] if target in spec["rules"] and "positive_quantile" in spec["rules"][target] else 0.9
    results = {"target": target, "folds": [], "feature_sets": {}, "split_audit": []}
    predictions = []
    importances = []
    for name, definition in config["feature_sets"].items():
        features = resolve_feature_set(definition)
        fold_records = []
        for fold in folds:
            frame = fold_frame(domain, by_fold, fold["fold"], target)
            train_all = frame.loc[frame.split_role.eq("train")]
            test_all = frame.loc[frame.split_role.eq("test")]
            if name == "full_23":
                audit = audit_split(frame[["dataset_source", "session_id", "segment_id", "experiment_group",
                                           "window_start_seconds", "window_end_seconds", *FEATURE_ORDER]],
                                    train_all.index, test_all.index)
                if not audit["passed"]:
                    raise RuntimeError(f"Rò rỉ giữa train/test ở fold {fold['fold']}: {audit}")
                results["split_audit"].append({"fold": fold["fold"], "test_groups": fold["test_groups"], **audit})
            labeled = frame[f"{target}_status"].isin([POS, NEG])
            train = frame.loc[frame.split_role.eq("train") & labeled].reset_index(drop=True)
            test = frame.loc[frame.split_role.eq("test") & labeled].reset_index(drop=True)
            selection = select_hyperparameters(train, features, config, seed)
            model = make_model(selection["params"], config, seed).fit(validate_feature_frame(train, features), train.y_true)
            score = model.predict_proba(validate_feature_frame(test, features))[:, 1] if len(test) else np.array([])
            pred = (score >= selection["probability_threshold"]).astype(int)
            out = test[["window_id", "experiment_group", "session_id", "window_end_seconds", "y_true", "roll_std_60",
                        "roll_rms_60", "pitch_std_60", "near_segment_end_audit"]].copy()
            out["feature_set"], out["fold"], out["rf_score"], out["rf_pred"] = name, fold["fold"], score, pred
            abstain_test = frame.loc[frame.split_role.eq("test") & frame[f"{target}_status"].eq(ABSTAIN)]
            abstain_pred = (model.predict_proba(validate_feature_frame(abstain_test, features))[:, 1] >= selection["probability_threshold"]).astype(int) if len(abstain_test) else np.array([])
            cal = calibrations[fold["fold"]]["domains"][config["domain"]].get(target, {})
            if name == "full_23":
                out["majority_pred"] = majority(test)
                for baseline, feature in FEATURE_RULE_BASELINES.items():
                    out[f"{baseline}_pred"], threshold = feature_quantile_rule(train_all, test, feature, q_rule)
                    out[f"{baseline}_threshold"] = threshold
                out["proxy_positive_threshold"] = cal.get("positive_threshold")
                out["proxy_negative_threshold"] = cal.get("negative_threshold")
                if 0 < test.y_true.sum() < len(test):
                    perm = permutation_importance(model, validate_feature_frame(test, features), test.y_true,
                                                  scoring="average_precision", n_repeats=config["permutation_repeats"],
                                                  random_state=seed, n_jobs=1)
                    importances.append({"fold": fold["fold"], "test_groups": fold["test_groups"],
                                        **{f: float(m) for f, m in zip(features, perm.importances_mean)}})
            predictions.append(out)
            fold_records.append({"fold": fold["fold"], "test_groups": fold["test_groups"], "train_groups": fold["train_groups"],
                                 "calibration_id": calibrations[fold["fold"]]["calibration_id"],
                                 "train_windows": int(len(train)), "train_positive": int(train.y_true.sum()),
                                 "train_positive_groups": int(train.loc[train.y_true.eq(1), "experiment_group"].nunique()),
                                 "test_windows": int(len(test)), "test_positive": int(test.y_true.sum()),
                                 "test_abstain_windows": int(len(abstain_test)),
                                 "test_abstain_predicted_positive": int(abstain_pred.sum()),
                                 "selected_params": selection["params"],
                                 "inner_pooled_average_precision": selection["inner_pooled_average_precision"],
                                 "probability_threshold": selection["probability_threshold"],
                                 "inner_trials": selection["trials"]})
        results["feature_sets"][name] = {"features": features, "folds": fold_records}
    pred_frame = pd.concat(predictions, ignore_index=True)
    for name in config["feature_sets"]:
        subset = pred_frame.loc[pred_frame.feature_set.eq(name)]
        results["feature_sets"][name]["pooled"] = binary_metrics(subset.y_true, subset.rf_pred, subset.rf_score)
        results["feature_sets"][name]["per_group"] = per_group_metrics(subset, "rf_pred", "rf_score")
        results["feature_sets"][name]["group_bootstrap"] = group_bootstrap_f1(subset, "rf_pred", config["bootstrap_replicates"], seed)
    full = pred_frame.loc[pred_frame.feature_set.eq("full_23")]
    results["baselines"] = {"majority": binary_metrics(full.y_true, full.majority_pred)}
    results["baselines"]["majority"]["note"] = "Luôn NEG; PR-AUC của điểm hằng số bằng prevalence."
    for baseline in FEATURE_RULE_BASELINES:
        results["baselines"][baseline] = binary_metrics(full.y_true, full[f"{baseline}_pred"])
        results["baselines"][baseline]["group_bootstrap"] = group_bootstrap_f1(full, f"{baseline}_pred", config["bootstrap_replicates"], seed)
    results["error_analysis"] = error_analysis(full)
    results["permutation_importance_test_folds"] = importances
    results["compact_model"] = run_compact(domain, by_fold, folds, target, config)
    return results, pred_frame


def error_analysis(full: pd.DataFrame) -> dict:
    errors = full.loc[full.y_true.ne(full.rf_pred)].copy()
    width = (full.proxy_positive_threshold - full.proxy_negative_threshold)
    full = full.assign(relative_position=(full.roll_std_60 - full.proxy_negative_threshold) / width)
    errors = full.loc[full.y_true.ne(full.rf_pred)]
    fp, fn = errors.loc[errors.rf_pred.eq(1)], errors.loc[errors.rf_pred.eq(0)]
    return {"false_positive": int(len(fp)), "false_negative": int(len(fn)),
            "errors_by_group": errors.groupby("experiment_group").size().to_dict(),
            "errors_by_session": errors.groupby("session_id").size().to_dict(),
            "fp_relative_position_median": float(fp.relative_position.median()) if len(fp) else None,
            "fn_relative_position_median": float(fn.relative_position.median()) if len(fn) else None,
            "errors_within_half_band_of_boundary": int(((errors.relative_position > -0.5) & (errors.relative_position < 1.5)).sum()),
            "errors_near_segment_end": int(errors.near_segment_end_audit.sum()),
            "note": "relative_position = (roll_std_60 - T_neg)/(T_pos - T_neg); 0 = ngưỡng NEG, 1 = ngưỡng POS của fold."}


def tree_statistics(model: RandomForestClassifier, X: np.ndarray) -> dict:
    nodes = [e.tree_.node_count for e in model.estimators_]
    leaves = [e.tree_.n_leaves for e in model.estimators_]
    depths = [e.tree_.max_depth for e in model.estimators_]
    path_lengths = np.zeros(len(X))
    for estimator in model.estimators_:
        path_lengths += np.asarray(estimator.decision_path(X).sum(axis=1)).ravel() - 1
    internal = int(sum(nodes) - sum(leaves))
    return {"n_estimators": len(model.estimators_), "total_nodes": int(sum(nodes)), "internal_nodes": internal,
            "leaves": int(sum(leaves)), "max_depth": int(max(depths)), "mean_depth": float(np.mean(depths)),
            "mean_comparisons_per_inference": float(path_lengths.mean()),
            "max_comparisons_per_inference": float(path_lengths.max()),
            "estimated_c_array_bytes": int(internal * 12 + sum(leaves) * 4),
            "estimate_note": "Ước tính: nút trong 12 B (feature int16, threshold float32, left/right int16, padding), lá 4 B (một xác suất float32). Chưa phải kích thước đo trên ESP32."}


def run_compact(domain: pd.DataFrame, by_fold: pd.DataFrame, folds: list[dict], target: str, config: dict) -> dict:
    params = dict(config["compact_model"])
    rows = []
    stats = []
    for fold in folds:
        frame = fold_frame(domain, by_fold, fold["fold"], target)
        labeled = frame[f"{target}_status"].isin([POS, NEG])
        train = frame.loc[frame.split_role.eq("train") & labeled]
        test = frame.loc[frame.split_role.eq("test") & labeled]
        X_train = validate_feature_frame(train, list(FEATURE_ORDER))
        model = make_model(params, config, config["seed"]).fit(X_train, train.y_true)
        score = model.predict_proba(validate_feature_frame(test, list(FEATURE_ORDER)))[:, 1]
        rows.append(test[["experiment_group", "session_id", "y_true"]].assign(score=score, pred=(score >= 0.5).astype(int)))
        stats.append(tree_statistics(model, X_train))
    pred = pd.concat(rows, ignore_index=True)
    return {"params": params, "probability_threshold": 0.5, "pooled": binary_metrics(pred.y_true, pred.pred, pred.score),
            "group_bootstrap": group_bootstrap_f1(pred, "pred", config["bootstrap_replicates"], config["seed"]),
            "tree_statistics_fold_median_bytes": float(np.median([s["estimated_c_array_bytes"] for s in stats])),
            "note": "Cấu hình khai báo trước, không tinh chỉnh trên test; ngưỡng 0.5 cố định."}


def train_final_model(measurements: pd.DataFrame, final_labels: pd.DataFrame, final_calibration: dict, target: str,
                      config: dict) -> tuple[RandomForestClassifier, dict]:
    """Mô hình cuối cho CLI dự đoán: hiệu chuẩn trên mọi nhóm Hohai, chọn tham số bằng GroupKFold. Không có test."""
    domain = measurements.loc[measurements.dataset_source.eq(config["domain"]) & measurements.angle23_complete]
    frame = domain.merge(final_labels[["window_id", f"{target}_status"]], on="window_id", validate="one_to_one")
    frame = frame.loc[frame[f"{target}_status"].isin([POS, NEG])].reset_index(drop=True)
    frame["y_true"] = frame[f"{target}_status"].eq(POS).astype(int)
    features = list(FEATURE_ORDER)
    selection = select_hyperparameters(frame, features, config, config["seed"])
    X = validate_feature_frame(frame, features)
    model = make_model(selection["params"], config, config["seed"]).fit(X, frame.y_true)
    domain_X = validate_feature_frame(domain, features)
    info = {"selection": {k: v for k, v in selection.items() if k != "trials"}, "inner_trials": selection["trials"],
            "training_windows": int(len(frame)), "training_positive": int(frame.y_true.sum()),
            "training_groups": sorted(frame.experiment_group.unique().tolist()),
            "training_sessions": int(frame.session_id.nunique()),
            "feature_ranges": {f: [float(domain[f].min()), float(domain[f].max())] for f in features},
            "mdi_importance": {f: float(v) for f, v in zip(features, model.feature_importances_)},
            "tree_statistics": tree_statistics(model, domain_X),
            "calibration_id": final_calibration["calibration_id"],
            "calibration_thresholds": final_calibration["domains"][config["domain"]][target]}
    return model, info


def serialize_model(model, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    joblib.dump(model, buffer)
    data = buffer.getvalue()
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def run(repo_root: Path, config_path: Path) -> dict:
    repo_root = repo_root.resolve()
    before = protected_checksums(repo_root)
    config = yaml.safe_load((repo_root / config_path).read_text(encoding="utf-8"))
    spec = load_spec(repo_root / "ml/labeling/proxy_spec.yaml")
    summary = json.loads((repo_root / config["proxy_summary"]).read_text(encoding="utf-8"))
    if summary["rule_version"] != spec["rule_version"]:
        raise ValueError("Proxy summary và spec khác rule_version; hãy dựng lại proxy dataset.")
    proxy_root = repo_root / config["proxy_output_root"]
    measurements = pd.read_parquet(proxy_root / "measurements.parquet")
    by_fold = pd.read_parquet(proxy_root / "proxy_labels_by_fold.parquet")
    final_labels = pd.read_parquet(proxy_root / "proxy_labels_final_calibration.parquet")
    calibration_payload = json.loads((proxy_root / "calibrations.json").read_text(encoding="utf-8"))
    calibrations = calibration_payload["folds"]
    readiness = summary["readiness"][config["domain"]]["targets"]
    trainable = [t for t, info in readiness.items() if info["decision"] == "TRAINABLE"]
    results = {"model_version": config["model_version"], "rule_version": spec["rule_version"],
               "feature_schema": feature_schema(), "seed": config["seed"], "domain": config["domain"],
               "readiness": {t: {"decision": v["decision"], "blockers": v["blockers"]} for t, v in readiness.items()},
               "trainable_targets": trainable, "environment": {"python": platform.python_version(),
               "sklearn": sklearn.__version__, "numpy": np.__version__, "pandas": pd.__version__},
               "targets": {}}
    if not trainable:
        results["status"] = "BLOCKED_NO_TRAINABLE_TARGET"
    else:
        started = time.time()
        all_predictions = []
        for target in trainable:
            target_results, predictions = run_target(measurements, by_fold, calibrations, target, config, spec)
            model, info = train_final_model(measurements, final_labels, calibration_payload["final_all_hohai_groups"], target, config)
            model_path = repo_root / config["model_output_root"] / f"{target.lower()}_rf.joblib"
            digest = serialize_model(model, model_path)
            card = {"model_version": config["model_version"], "target": target, "rule_version": spec["rule_version"],
                    "label_source": "PROXY_RULE", "not_a_safety_classifier": True,
                    "intended_use": "Nghiên cứu PoC tái tạo proxy RELATIVE phenotype trong miền Hohai model-scale; không dùng cho cảnh báo vận hành.",
                    "domain": config["domain"], "feature_schema": feature_schema(), "seed": config["seed"],
                    "model_path": model_path.relative_to(repo_root).as_posix(), "model_sha256": digest,
                    "environment": results["environment"], **info}
            target_results["final_model_card"] = card
            results["targets"][target] = target_results
            predictions.insert(0, "target", target)
            all_predictions.append(predictions)
            card_path = repo_root / config["model_output_root"] / f"{target.lower()}_model_card.json"
            card_path.write_text(json.dumps(card, indent=1, ensure_ascii=False, default=float), encoding="utf-8")
        pd.concat(all_predictions, ignore_index=True).to_parquet(repo_root / config["model_output_root"] / "outer_fold_predictions.parquet", index=False)
        results["status"] = "TRAINED_PROXY_POC"
        results["runtime_seconds"] = round(time.time() - started, 1)
        trained = [results["targets"][t]["feature_sets"]["full_23"]["pooled"]["f1"] for t in trainable]
        results["macro_f1_over_trainable_targets"] = float(np.mean(trained))
        results["macro_f1_note"] = (f"Macro F1 chỉ trên {len(trainable)} target TRAINABLE ({', '.join(trainable)}); "
                                    "các target NOT_TRAINABLE không có metric.")
    after = protected_checksums(repo_root)
    if after != before:
        raise RuntimeError("Human-review ledger/verified label bị thay đổi; dừng lại.")
    results["protected_files_unchanged"] = True
    (repo_root / config["results_path"]).write_text(json.dumps(results, indent=1, ensure_ascii=False, default=float), encoding="utf-8")
    if trainable:
        cards = {t: {k: v for k, v in results["targets"][t]["final_model_card"].items() if k != "inner_trials"} for t in trainable}
        (repo_root / config["model_card_path"]).write_text(json.dumps(cards, indent=1, ensure_ascii=False, default=float), encoding="utf-8")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Random Forest PoC cho proxy motion phenotype (không phải phân loại an toàn).")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--config", type=Path, default=Path("ml/train/rf_poc_config.yaml"))
    args = parser.parse_args()
    results = run(args.repo_root, args.config)
    brief = {"status": results["status"], "trainable_targets": results["trainable_targets"]}
    for target, payload in results["targets"].items():
        brief[target] = {name: {k: payload["feature_sets"][name]["pooled"][k] for k in ("precision", "recall", "f1", "pr_auc_average_precision")}
                         for name in payload["feature_sets"]}
        brief[target]["baselines"] = {k: v["f1"] for k, v in payload["baselines"].items()}
        brief[target]["compact"] = payload["compact_model"]["pooled"]["f1"]
    print(json.dumps(brief, indent=1, default=float))


if __name__ == "__main__":
    main()
