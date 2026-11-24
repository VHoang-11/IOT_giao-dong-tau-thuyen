"""Khóa nhóm độc lập và chia tập theo nhóm cho Motion Phenotype PoC.

Hohai: tên sheet ``Berth X_Tn_Type Y`` = bến × điều kiện thử nghiệm Tn × cấu hình dây neo
(theo ``ml/data/raw/hohai/Data Description Example.pdf``). Các session cùng Tn có Roll tương quan
chéo rõ rệt (xem ``session_cross_correlation``), nên nhóm độc lập là điều kiện Tn chứ không phải session.
Seafar/Southampton chỉ có một session/run nên nhóm = session.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

HOHAI_PATTERN = re.compile(r"^Berth_(?P<berth>[A-Z])_(?P<condition>T\d+)_Type_(?P<mooring>[A-Z])$")


def experiment_group(dataset_source: str, session_id: str) -> str:
    """Khóa nhóm độc lập mạnh nhất có căn cứ cho một session."""
    if dataset_source == "hohai":
        match = HOHAI_PATTERN.match(session_id)
        if not match:
            raise ValueError(f"Tên session Hohai không đúng mẫu Berth_X_Tn_Type_Y: {session_id}")
        return f"hohai|{match.group('condition')}"
    return f"{dataset_source}|{session_id}"


def hohai_session_parts(session_id: str) -> dict:
    match = HOHAI_PATTERN.match(session_id)
    if not match:
        raise ValueError(f"Tên session Hohai không đúng mẫu: {session_id}")
    return match.groupdict()


def leave_one_group_out(groups: pd.Series) -> list[dict]:
    """Outer folds xác định: mỗi nhóm làm tập test đúng một lần, thứ tự theo tên nhóm."""
    unique = sorted(groups.unique())
    folds = []
    for index, test_group in enumerate(unique):
        folds.append({"fold": index, "test_groups": [test_group],
                      "train_groups": [g for g in unique if g != test_group]})
    return folds


def inner_group_folds(groups: pd.Series, n_splits: int) -> list[tuple[np.ndarray, np.ndarray]]:
    """Chia nhóm xác định (round-robin theo tên nhóm) cho validation bên trong tập train."""
    unique = sorted(groups.unique())
    n_splits = min(n_splits, len(unique))
    if n_splits < 2:
        raise ValueError("Cần ít nhất hai nhóm cho validation theo nhóm.")
    assignment = {group: i % n_splits for i, group in enumerate(unique)}
    fold_of_row = groups.map(assignment).to_numpy()
    return [(np.where(fold_of_row != k)[0], np.where(fold_of_row == k)[0]) for k in range(n_splits)]


def audit_split(frame: pd.DataFrame, train_index, test_index) -> dict:
    """Kiểm toán rò rỉ: nhóm, session, segment và khoảng thời gian nguồn không được dùng chung."""
    train, test = frame.iloc[train_index], frame.iloc[test_index]
    key = ["dataset_source", "session_id", "segment_id"]
    shared_groups = sorted(set(train.experiment_group) & set(test.experiment_group))
    shared_sessions = sorted(set(map(tuple, train[key[:2]].to_numpy())) & set(map(tuple, test[key[:2]].to_numpy())))
    shared_segments = set(map(tuple, train[key].to_numpy())) & set(map(tuple, test[key].to_numpy()))
    overlapping_intervals = 0
    for segment in shared_segments:
        a = train.loc[(train[key] == segment).all(axis=1), ["window_start_seconds", "window_end_seconds"]].to_numpy()
        b = test.loc[(test[key] == segment).all(axis=1), ["window_start_seconds", "window_end_seconds"]].to_numpy()
        overlapping_intervals += int(sum(((a[:, 0] < e) & (s < a[:, 1])).sum() for s, e in b))
    feature_columns = [c for c in frame.columns if c.startswith(("roll_", "pitch_")) and c in frame.columns]
    duplicates = 0
    if feature_columns:
        train_vectors = set(map(tuple, np.round(train[feature_columns].to_numpy(float), 9)))
        duplicates = int(sum(tuple(v) in train_vectors for v in np.round(test[feature_columns].to_numpy(float), 9)))
    return {"shared_groups": shared_groups, "shared_sessions": [list(s) for s in shared_sessions],
            "shared_segments": len(shared_segments), "overlapping_intervals": overlapping_intervals,
            "duplicate_feature_vectors": duplicates,
            "passed": not shared_groups and not shared_sessions and not shared_segments and duplicates == 0}


def session_cross_correlation(processed_root: Path, sessions: list[str], max_lag_seconds: float = 30.0,
                              sampling_hz: float = 10.0) -> pd.DataFrame:
    """Tương quan chéo cực đại |ρ| (lag ±max_lag) giữa Roll đã trừ mean của các session Hohai."""
    series = {}
    for session in sessions:
        frame = pd.read_parquet(processed_root / "hohai" / session / "segment_000" / "timeseries.parquet",
                                columns=["roll_deg"])
        x = frame.roll_deg.to_numpy(float)
        series[session] = x - x.mean()
    max_lag = int(round(max_lag_seconds * sampling_hz))
    rows = []
    for i, a in enumerate(sessions):
        for b in sessions[i + 1:]:
            x, y = series[a], series[b]
            n = min(len(x), len(y))
            x, y = x[:n], y[:n]
            spectrum = np.fft.irfft(np.fft.rfft(x, 2 * n) * np.conj(np.fft.rfft(y, 2 * n)))
            corr = spectrum / (np.std(x) * np.std(y) * n)
            lags = np.r_[corr[:max_lag + 1], corr[-max_lag:]]
            pa, pb = hohai_session_parts(a), hohai_session_parts(b)
            rows.append({"session_a": a, "session_b": b, "max_abs_xcorr": float(np.max(np.abs(lags))),
                         "same_condition": pa["condition"] == pb["condition"],
                         "same_berth": pa["berth"] == pb["berth"]})
    return pd.DataFrame(rows)
