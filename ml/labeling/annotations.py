from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .schemas import IDENTITY_COLUMNS, LABEL_COLUMNS
from .validation import validate_label_record

EXTERNAL_KEY = (*IDENTITY_COLUMNS, "label")


def load_external_annotations(path: Path) -> pd.DataFrame:
    """Đọc annotation ngoài ở CSV, JSONL hoặc Parquet; không tự sinh dữ liệu tham chiếu."""
    if path.suffix.lower() == ".parquet":
        frame = pd.read_parquet(path)
    elif path.suffix.lower() == ".csv":
        frame = pd.read_csv(path)
    elif path.suffix.lower() in {".jsonl", ".ndjson"}:
        frame = pd.read_json(path, lines=True)
    else:
        raise ValueError("External annotations chỉ hỗ trợ CSV, JSONL hoặc Parquet.")
    if frame.empty:
        return pd.DataFrame(columns=LABEL_COLUMNS)
    required = set(IDENTITY_COLUMNS) | {"label", "evidence_reference"}
    if missing := required - set(frame.columns):
        raise ValueError(f"External annotations thiếu cột: {sorted(missing)}")
    records = []
    for row in frame.to_dict("records"):
        record = {**row, "label_status": "VERIFIED", "label_source": "EXTERNAL_REFERENCE",
                  "labeling_method": "external_annotation", "rule_version": str(row.get("rule_version", "external_reference_v1")),
                  "review_status": "NOT_REVIEWED", "ambiguity_reason": row.get("ambiguity_reason"),
                  "quality_flags": row.get("quality_flags", "[]"), "phenotype_flags_json": row.get("phenotype_flags_json", "{}"),
                  "suggested_label": row.get("suggested_label")}
        validate_label_record(record)
        records.append({key: record.get(key) for key in LABEL_COLUMNS})
    result = pd.DataFrame(records, columns=LABEL_COLUMNS)
    if result.duplicated(list(IDENTITY_COLUMNS)).any():
        raise ValueError("External annotations có nhiều nhãn trên cùng một cửa sổ; cần xử lý xung đột trước.")
    return result


def apply_external_annotations(candidate_table: pd.DataFrame, external: pd.DataFrame) -> pd.DataFrame:
    """Chỉ ghi nhãn tham chiếu có khóa phiên/cửa sổ trùng chính xác."""
    if external.empty:
        return candidate_table.copy()
    keys = list(IDENTITY_COLUMNS)
    output = candidate_table.copy().set_index(keys)
    refs = external.set_index(keys)
    missing = refs.index.difference(output.index)
    if len(missing):
        raise ValueError(f"Có {len(missing)} external annotation không khớp đúng cửa sổ/session/segment.")
    for identity, annotation in refs.iterrows():
        for column in LABEL_COLUMNS:
            if column in annotation.index:
                output.loc[identity, column] = annotation[column]
        output.loc[identity, "label_source"] = "EXTERNAL_REFERENCE"
        output.loc[identity, "label_status"] = "VERIFIED"
        output.loc[identity, "labeling_method"] = "external_annotation"
    result = output.reset_index()
    for record in result.to_dict("records"):
        validate_label_record(record)
    return result.loc[:, LABEL_COLUMNS]
