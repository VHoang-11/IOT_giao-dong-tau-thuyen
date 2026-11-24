"""Test bộ pilot M2-R5: tái lập, ánh xạ lớp, loại cửa sổ, cô lập split, schema, tính nhân quả, manifest."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import re

import pytest

from ml.train import four_class_pilot_dataset as p
from ml.train.g1_simulation_dataset import ROOT, _core_rows, _features
from simulation.generator.config import DatasetSplit, LabelingVersion, ScenarioCode
from simulation.generator.scenarios import ScenarioRunner

SMALL_PLAN = {scenario: (1, 1, 1) for scenario in p.TARGET}


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("pilot")
    manifest = p.build_dataset(out, SMALL_PLAN, report=None)
    with (out / "windows.csv").open(encoding="utf-8") as f:
        return out, manifest, list(csv.DictReader(f))


def test_session_generation_is_deterministic():
    runner, _ = p.make_runner()
    first, meta1 = p.generate_session(runner, ScenarioCode.S2, DatasetSplit.TRAIN, p.session_seed(0))
    second, meta2 = p.generate_session(runner, ScenarioCode.S2, DatasetSplit.TRAIN, p.session_seed(0))
    assert first == second and json.dumps(meta1, default=str) == json.dumps(meta2, default=str)


def test_class_ids_match_firmware_enum_and_scenario_targets():
    header = (ROOT / "core/include/svmg_common.h").read_text()
    for name, class_id in p.CLASSES.items():
        assert re.search(rf"SVMG_{name}\s*=\s*{class_id}\b", header)
    for scenario, target in p.TARGET.items():
        assert ScenarioRunner._SCENARIO_TARGET[scenario] == target


def test_pre_event_and_transition_windows_abstain():
    runner, _ = p.make_runner()
    result = runner.generate(ScenarioCode.S1, seed=p.session_seed(7), dataset_split=DatasetSplit.TRAIN,
                             labeling_version=LabelingVersion.V2)
    rows, _ = p.generate_session(runner, ScenarioCode.S1, DatasetSplit.TRAIN, p.session_seed(7))
    t0 = result.events[0]["t0_s"]
    for row in rows:
        start, end = float(row["window_start_seconds"]), float(row["window_end_seconds"])
        if end < t0:
            assert row["label"] == "ABSTAIN" and row["exclusion_reason"] in ("PRE_EVENT", "CORE_FEATURE_INVALID")
        if row["label"] != "ABSTAIN":
            assert start >= t0 + 90.0 - 0.05, "cửa sổ đủ điều kiện chồng lên đoạn chuyển tiếp của sự kiện"


def test_split_isolation_and_seed_disjointness(built):
    _, manifest, rows = built
    split_of = {}
    for row in rows:
        assert split_of.setdefault(row["session_id"], row["split"]) == row["split"]
    seeds = [s["seed"] for s in manifest["sessions"]]
    assert len(seeds) == len(set(seeds)) == 12
    prior = set()
    for path in ("simulation/calibration/labeling_v2_candidate.json", "simulation/calibration/labeling_v2_independent_validation.json"):
        text = (ROOT / path).read_text()
        prior |= {int(x) for x in re.findall(r'"seed":\s*(\d+)', text) + re.findall(r'-(\d{6,10})"', text)}
    prior |= set(range(2026112300, 2026112400))   # seed của dataset G1 coursework
    assert not prior & set(seeds)
    assert len({round(s["sampled_parameters"]["t0_s"]) for s in manifest["sessions"] if s["scenario"] != "S0"}) >= 7


def test_schema_and_eligible_vectors(built):
    _, manifest, rows = built
    names = list(_features())
    assert manifest["feature_names"] == names and list(rows[0])[-23:] == names
    eligible = [r for r in rows if r["label"] != "ABSTAIN"]
    assert eligible, "pilot phải có cửa sổ đủ điều kiện"
    for row in eligible:
        assert int(row["feature_valid_mask"]) == (1 << 23) - 1 and all(math.isfinite(float(row[n])) for n in names)
        assert int(row["class_id"]) == p.CLASSES[row["label"]]
    for row in rows:   # đặc trưng không hợp lệ để trống, không bao giờ impute bằng 0
        if int(row["feature_valid_mask"]) != (1 << 23) - 1:
            assert row["label"] == "ABSTAIN" and any(row[n] == "" for n in names)
        assert row["dataset_source"] == "SIMULATION" and row["label_policy"] == p.LABEL_POLICY and row["seed"]


def test_features_do_not_use_future_samples():
    runner, _ = p.make_runner()
    result = runner.generate(ScenarioCode.S3, seed=p.session_seed(3), dataset_split=DatasetSplit.TRAIN,
                             labeling_version=LabelingVersion.V2)
    full = _core_rows(result.imu_samples)
    prefix = _core_rows(result.imu_samples[:12000])   # chỉ 600 s đầu
    same = lambda a, b: all(x == y or (math.isnan(x) and math.isnan(y)) for x, y in zip(a, b))  # noqa: E731
    assert len(prefix) == 59 and all(same(a, b) for a, b in zip(prefix, full))


def test_manifest_matches_csv(built):
    out, manifest, rows = built
    assert manifest["dataset_sha256"] == hashlib.sha256((out / "windows.csv").read_bytes()).hexdigest()
    assert manifest["window_count"] == len(rows)
    assert manifest["eligible_count"] == sum(r["label"] != "ABSTAIN" for r in rows)
    for split, by_label in manifest["counts"].items():
        for label, count in by_label.items():
            assert count["windows"] == sum(r["split"] == split and r["label"] == label for r in rows)
    assert manifest["label_policy_status"].startswith("PROPOSED")
