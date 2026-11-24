"""Định dạng trao đổi kết quả feature giữa tham chiếu Python (golden) và hiện thực C/C++ của M1.

Hai định dạng tương đương, harness đọc được cả hai:

* CSV dạng dài: một dòng cho mỗi (case_id, endpoint_index, feature_index).
* JSONL: một dòng JSON cho mỗi (case_id, endpoint_index) với mảng ``values``/``status`` 23 phần tử theo thứ tự contract.

Quy tắc mã hóa giá trị: feature không VALID có giá trị rỗng (CSV) hoặc ``null`` (JSON), không bao giờ là 0.
"""
from __future__ import annotations

import csv
import io
import json
import math
from pathlib import Path

import pandas as pd

from ml.parity.contract import FEATURE_ORDER, SCHEMA_VERSION, STATUS_VOCABULARY

INTERCHANGE_SCHEMA = "svmg-parity-output-v1"
OUTPUT_COLUMNS = ("schema_version", "case_id", "input_sha256", "endpoint_index", "endpoint_time_seconds",
                  "feature_index", "feature_name", "status", "reason_code", "value")
REQUIRED_COLUMNS = tuple(c for c in OUTPUT_COLUMNS if c != "reason_code")
KEY = ("case_id", "endpoint_index", "feature_index")
PRODUCER_KINDS = ("independent_c_implementation", "python_float32_emulation", "python_reference_self_consistency")


class InterchangeError(ValueError):
    """File đầu ra không đúng định dạng trao đổi."""


def format_value(value) -> str:
    """Chuỗi thập phân round-trip float64 (repr); rỗng cho None; giữ 'nan'/'inf' để harness bắt lỗi."""
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return ""
    value = float(value)
    if math.isnan(value):
        return "nan"
    if math.isinf(value):
        return "inf" if value > 0 else "-inf"
    return repr(value)


def parse_value(text) -> float | None:
    """'' -> None; số thập phân -> float (có thể nan/inf để harness phân loại)."""
    if text is None:
        return None
    if isinstance(text, (int, float)) and not isinstance(text, bool):
        return float(text)
    text = str(text).strip()
    if text == "" or text.lower() in ("null", "none"):
        return None
    return float(text)


def write_csv(records: list[dict], path: Path) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=OUTPUT_COLUMNS, lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    for r in records:
        writer.writerow({**r, "value": format_value(r.get("value")), "reason_code": r.get("reason_code") or ""})
    data = buffer.getvalue().encode("utf-8")
    if path is not None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(data)
    return data


def write_jsonl(records: list[dict], path: Path | None) -> bytes:
    """Gom bản ghi dài thành một dòng JSON mỗi (case, endpoint), mảng theo feature_index."""
    groups: dict[tuple, dict] = {}
    for r in records:
        key = (r["case_id"], int(r["endpoint_index"]))
        g = groups.setdefault(key, {"schema_version": r["schema_version"], "case_id": r["case_id"],
                                    "input_sha256": r["input_sha256"], "endpoint_index": int(r["endpoint_index"]),
                                    "endpoint_time_seconds": float(r["endpoint_time_seconds"]),
                                    "feature_names": list(FEATURE_ORDER), "values": [None] * len(FEATURE_ORDER),
                                    "status": [None] * len(FEATURE_ORDER), "reason_code": [""] * len(FEATURE_ORDER)})
        i = int(r["feature_index"])
        value = r.get("value")
        g["values"][i] = None if value is None or (isinstance(value, str) and value == "") else float(value)
        g["status"][i] = r["status"]
        g["reason_code"][i] = r.get("reason_code") or ""
    lines = [json.dumps(g, ensure_ascii=False, separators=(",", ":"), allow_nan=True) for _, g in sorted(groups.items())]
    data = ("\n".join(lines) + "\n").encode("utf-8")
    if path is not None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(data)
    return data


def _normalise(frame: pd.DataFrame, source: str) -> pd.DataFrame:
    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise InterchangeError(f"{source}: thiếu cột bắt buộc {missing}")
    if "reason_code" not in frame.columns:
        frame["reason_code"] = ""
    out = frame[list(OUTPUT_COLUMNS)].copy()
    for column in ("case_id", "input_sha256", "feature_name", "status", "reason_code", "schema_version"):
        out[column] = out[column].fillna("").astype(str)
    try:
        out["endpoint_index"] = out["endpoint_index"].astype(int)
        out["feature_index"] = out["feature_index"].astype(int)
        out["endpoint_time_seconds"] = out["endpoint_time_seconds"].astype(float)
    except (TypeError, ValueError) as exc:
        raise InterchangeError(f"{source}: endpoint_index/feature_index/endpoint_time_seconds không phải số: {exc}") from exc
    raw = out["value"].tolist()
    parsed, problems = [], []
    for i, text in enumerate(raw):
        try:
            parsed.append(parse_value(text))
            problems.append("")
        except (TypeError, ValueError):
            parsed.append(None)
            problems.append("UNPARSEABLE_VALUE")
    out["value_text"] = ["" if v is None else str(v) for v in raw]
    out["value"] = pd.Series(parsed, dtype=object, index=out.index)  # giữ None khác NaN
    out["parse_problem"] = problems
    return out


def from_records(records: list[dict], source: str = "records") -> pd.DataFrame:
    """Bản ghi Python -> DataFrame chuẩn hóa (giữ None khác NaN, như khi đọc lại file CSV)."""
    rows = [{**{c: r.get(c, "") for c in OUTPUT_COLUMNS}, "value": format_value(r.get("value")),
             "reason_code": r.get("reason_code") or ""} for r in records]
    return _normalise(pd.DataFrame(rows, columns=OUTPUT_COLUMNS, dtype=object), source)


def read_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    return _normalise(frame, str(path))


def read_jsonl(path: Path) -> pd.DataFrame:
    rows = []
    for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise InterchangeError(f"{path}:{n}: JSON không hợp lệ: {exc}") from exc
        values, status = record.get("values"), record.get("status")
        if not isinstance(values, list) or not isinstance(status, list) or len(values) != len(status):
            raise InterchangeError(f"{path}:{n}: 'values' và 'status' phải là mảng cùng độ dài.")
        names = record.get("feature_names") or list(FEATURE_ORDER)[:len(values)]
        reasons = record.get("reason_code") or [""] * len(values)
        if len(names) != len(values):
            raise InterchangeError(f"{path}:{n}: 'feature_names' khác độ dài 'values'.")
        for i, (value, st) in enumerate(zip(values, status)):
            rows.append({"schema_version": record.get("schema_version", ""), "case_id": record.get("case_id", ""),
                         "input_sha256": record.get("input_sha256", ""), "endpoint_index": record.get("endpoint_index"),
                         "endpoint_time_seconds": record.get("endpoint_time_seconds"), "feature_index": i,
                         "feature_name": names[i], "status": st if st is not None else "", "reason_code": reasons[i] or "",
                         "value": "" if value is None else value})
    return _normalise(pd.DataFrame(rows, columns=OUTPUT_COLUMNS), str(path))


def read_any(path: Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() in (".jsonl", ".ndjson"):
        return read_jsonl(path)
    return read_csv(path)


def metadata_template() -> dict:
    return {"interchange_schema": INTERCHANGE_SCHEMA, "schema_version": SCHEMA_VERSION,
            "producer": {"kind": "independent_c_implementation", "name": "svmg_feature23_host_test",
                         "version": "0.0.0", "source_commit": "<git commit của mã C>", "compiler": "<vd. gcc 13.2 / xtensa-esp32-elf-gcc>",
                         "compiler_flags": "<vd. -O2 -ffp-contract=off>", "target": "host|esp32",
                         "float_type": "float32|float64", "accumulator_type": "float32|float64",
                         "quantile_algorithm": "<vd. sort + Type-7>", "std_algorithm": "<two-pass|Welford>"},
            "golden_manifest_sha256": "<sha256 của ml/parity/fixtures/manifest.json đã dùng>",
            "notes": ""}


def interchange_document() -> dict:
    return {
        "interchange_schema": INTERCHANGE_SCHEMA, "schema_version": SCHEMA_VERSION,
        "feature_order": list(FEATURE_ORDER), "status_vocabulary": list(STATUS_VOCABULARY),
        "c_output_csv_columns": list(OUTPUT_COLUMNS), "required_columns": list(REQUIRED_COLUMNS), "record_key": list(KEY),
        "c_output_jsonl_record": {"schema_version": "string", "case_id": "string", "input_sha256": "hex sha256",
                                  "endpoint_index": "int (chỉ số 0-based trong file input)",
                                  "endpoint_time_seconds": "float", "feature_names": "23 tên theo thứ tự contract (tùy chọn)",
                                  "values": "23 số hoặc null", "status": "23 chuỗi trạng thái", "reason_code": "23 chuỗi (tùy chọn)"},
        "c_output_metadata_json": metadata_template(), "producer_kinds": list(PRODUCER_KINDS),
        "rules": ["Một bản ghi cho mỗi (case_id, endpoint_index, feature_index) có trong golden expected_features.csv; không thiếu, không thừa, không trùng.",
                  "endpoint_index là chỉ số 0-based của dòng trong file input (cột sample_index); khóa so khớp chính.",
                  "endpoint_time_seconds phải khớp golden trong 1e-6 s (kiểm tra chéo).",
                  "endpoint_time_seconds phải là số hữu hạn; NaN/Inf bị từ chối.",
                  "feature_name phải khớp feature_index theo thứ tự contract.",
                  "input_sha256 là sha256 của file input đã đọc (chứng minh cùng chuỗi đầu vào).",
                  "status thuộc VALID|INSUFFICIENT_WINDOW|INVALID_INPUT|UNDEFINED_MATHEMATICALLY.",
                  "value: thập phân >= 9 chữ số có nghĩa (float32) hoặc 17 (float64) khi VALID; rỗng/null khi không VALID. Ghi 0 cho feature không VALID là FAIL.",
                  "reason_code tùy chọn; harness chỉ báo khác biệt reason_code như cảnh báo.",
                  "Kèm file metadata JSON (interchange_schema, schema_version và golden_manifest_sha256 phải khớp; producer.kind = independent_c_implementation, source_commit, compiler, float_type). Schema/manifest sai -> FAIL_METADATA; thiếu metadata -> UNATTRIBUTED, không chứng minh parity C."],
        "input_csv_columns": ["sample_index", "time_seconds", "roll_deg", "pitch_deg", "source_sample_index"],
        "input_notes": ["time_seconds: float64 repr; roll_deg/pitch_deg: chuỗi float32 ngắn nhất round-trip (đọc bằng strtof); 'nan'/'inf'/'-inf' là mẫu không hữu hạn có timestamp.",
                        "source_sample_index nhảy cóc = timestamp bị bỏ (gap) — C phải phát hiện bằng time_seconds, không bằng chỉ số.",
                        "C đánh giá tại các endpoint_index liệt kê trong golden; không tự chọn endpoint."]}
