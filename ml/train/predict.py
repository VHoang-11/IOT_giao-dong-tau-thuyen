"""CLI dự đoán tối thiểu cho RF proxy PoC. Chạy từ repository root::

    python -m ml.train.predict --model-card ml/data/models/rf_poc_v1/relative_high_roll_model_card.json \
        --input ml/data/labels/proxy_v1/measurements.parquet --output /tmp/predictions.csv

Đầu ra là mức tái tạo proxy rule (``label_source = RF_PROXY_REPRODUCTION``), không phải cảnh báo an toàn.
Cửa sổ thiếu feature, feature không hữu hạn, ngoài miền huấn luyện hoặc ngoài dải feature -> ABSTAIN.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from ml.train.rf_poc import FEATURE_ORDER, feature_schema

RANGE_MARGIN = 0.01  # cùng quy ước biên 1 % mà firmware/src/infer.cpp mô tả cho SVMG_MODEL_HAS_RANGE


def load_model(card_path: Path, repo_root: Path = Path(".")):
    card = json.loads(card_path.read_text(encoding="utf-8"))
    model_path = repo_root / card["model_path"]
    data = model_path.read_bytes()
    if hashlib.sha256(data).hexdigest() != card["model_sha256"]:
        raise ValueError("SHA-256 của model không khớp model card; từ chối nạp.")
    if card["feature_schema"]["sha256"] != feature_schema()["sha256"]:
        raise ValueError("Feature schema của model khác schema 23 feature hiện hành.")
    model = joblib.load(model_path)
    if model.n_features_in_ != len(FEATURE_ORDER):
        raise ValueError("Số feature của model không khớp schema.")
    model.set_params(n_jobs=1)  # tổng xác suất theo thứ tự cố định -> dự đoán tái lập bit-đến-bit
    return model, card


def predict_frame(model, card: dict, frame: pd.DataFrame) -> pd.DataFrame:
    missing = [name for name in FEATURE_ORDER if name not in frame.columns]
    if missing:
        raise ValueError(f"Input thiếu cột feature bắt buộc: {missing}")
    X = frame[list(FEATURE_ORDER)].to_numpy(dtype=float)
    status = np.full(len(frame), "PREDICTED", dtype=object)
    reason = np.full(len(frame), "", dtype=object)
    if "dataset_source" in frame.columns:
        outside = frame.dataset_source.astype(str).ne(card["domain"]).to_numpy()
        status[outside], reason[outside] = "ABSTAIN", "OUT_OF_TRAINING_DOMAIN"
    if "angle23_complete" in frame.columns:
        incomplete = ~frame.angle23_complete.astype(bool).to_numpy()
        status[incomplete & (status == "PREDICTED")] = "ABSTAIN"
        reason[incomplete & (reason == "")] = "INCOMPLETE_ANGLE_FEATURES"
    nonfinite = ~np.all(np.isfinite(X), axis=1)
    status[nonfinite], reason[nonfinite & (reason == "")] = "ABSTAIN", "NON_FINITE_FEATURE"
    lo = np.array([card["feature_ranges"][f][0] for f in FEATURE_ORDER])
    hi = np.array([card["feature_ranges"][f][1] for f in FEATURE_ORDER])
    margin = RANGE_MARGIN * (hi - lo)
    with np.errstate(invalid="ignore"):
        out_of_range = np.any((X < lo - margin) | (X > hi + margin), axis=1) & ~nonfinite
    status[out_of_range & (status == "PREDICTED")] = "ABSTAIN"
    reason[out_of_range & (reason == "")] = "FEATURE_OUTSIDE_TRAINING_RANGE"
    score = np.full(len(frame), np.nan)
    ok = status == "PREDICTED"
    if ok.any():
        score[ok] = model.predict_proba(X[ok])[:, 1]
    threshold = card["selection"]["probability_threshold"]
    prediction = np.where(ok, np.where(score >= threshold, "POS", "NEG"), "ABSTAIN")
    return pd.DataFrame({"window_id": frame.get("window_id", pd.Series(range(len(frame)))).to_numpy(),
                         "target": card["target"], "proxy_score": score, "proxy_prediction": prediction,
                         "status": status, "abstain_reason": reason, "model_version": card["model_version"],
                         "label_source": "RF_PROXY_REPRODUCTION"})


def main() -> None:
    parser = argparse.ArgumentParser(description="Dự đoán proxy phenotype bằng RF PoC (không phải phân loại an toàn).")
    parser.add_argument("--model-card", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    model, card = load_model(args.model_card)
    frame = pd.read_parquet(args.input) if args.input.suffix == ".parquet" else pd.read_csv(args.input)
    result = predict_frame(model, card, frame)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.output, index=False)
    print(json.dumps(result.groupby(["status", "proxy_prediction"]).size().rename("windows").reset_index().to_dict("records"),
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
