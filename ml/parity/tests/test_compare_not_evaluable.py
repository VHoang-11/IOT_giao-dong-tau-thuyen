"""Ngữ nghĩa NOT_EVALUABLE do producer khai báo trong harness compare/readiness (không cần trình biên dịch C)."""
from __future__ import annotations

import copy
from pathlib import Path

import pytest

from ml.parity import compare, interchange, readiness

REPO_ROOT = Path(__file__).resolve().parents[3]
C_META = {"producer": {"kind": "independent_c_implementation"}}


@pytest.fixture(scope="module")
def golden():
    return compare.load_golden(REPO_ROOT, "synthetic")


@pytest.fixture(scope="module")
def records():
    return readiness._golden_records(REPO_ROOT, "synthetic")


def _declare_not_evaluable(recs: list[dict], n: int, value=None, reason="C_API_NO_TIMESTAMP_INPUT") -> list[dict]:
    out = copy.deepcopy(recs)
    for r in out[:n]:
        r.update(status=compare.NOT_EVALUABLE_STATUS, value=value, reason_code=reason)
    return out


def _summary(golden, recs):
    expected, cases = golden
    return compare.compare_frames(expected, interchange.from_records(recs), cases, C_META)


def test_not_evaluable_is_never_pass_and_caps_verdict_at_partial(golden, records):
    result = _summary(golden, _declare_not_evaluable(records, 23))
    s = result["summary"]
    assert s["outcome_counts"]["NOT_EVALUABLE"] == 23 and s["not_evaluable_records"] == 23
    assert s["fail_records"] == 0 and s["verdict"] == "C_PARITY_PARTIAL"
    flagged = result["rows"].loc[result["rows"].outcome.eq("NOT_EVALUABLE")]
    assert not flagged.outcome.isin(compare.PASS_OUTCOMES).any()
    assert sum(f["not_evaluable"] for f in s["per_feature"]) == 23
    assert "NOT_EVALUABLE: 23" in compare.markdown_report(result, "t")


def test_not_evaluable_with_value_or_without_reason_fails(golden, records):
    with_value = _summary(golden, _declare_not_evaluable(records, 1, value=1.0))["summary"]
    assert with_value["outcome_counts"]["FAIL_INVALID_HAS_VALUE"] == 1 and with_value["verdict"] == "C_PARITY_FAIL"
    no_reason = _summary(golden, _declare_not_evaluable(records, 1, reason=""))["summary"]
    assert no_reason["outcome_counts"]["FAIL_UNKNOWN_STATUS"] == 1


def test_fail_takes_precedence_over_partial(golden, records):
    recs = _declare_not_evaluable(records, 23)
    recs[23]["input_sha256"] = "0" * 64
    s = _summary(golden, recs)["summary"]
    assert s["not_evaluable_records"] == 23 and s["fail_records"] == 1 and s["verdict"] == "C_PARITY_FAIL"


def test_not_evaluable_still_checks_record_identity(golden, records):
    recs = _declare_not_evaluable(records, 1)
    recs[0]["input_sha256"] = "0" * 64
    assert _summary(golden, recs)["summary"]["outcome_counts"]["FAIL_INPUT_SHA256"] == 1


def test_readiness_does_not_count_partial_as_verified():
    base = {"is_c_parity_evidence": True, "fail_records": 0, "not_evaluable_records": 0}
    assert readiness.suite_passed(base)
    assert not readiness.suite_passed({**base, "not_evaluable_records": 46})
    assert not readiness.suite_passed({**base, "fail_records": 1})
    assert not readiness.suite_passed({**base, "is_c_parity_evidence": False})
