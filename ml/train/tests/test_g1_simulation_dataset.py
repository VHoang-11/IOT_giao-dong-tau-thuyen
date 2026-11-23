from dataclasses import replace
import json

from ml.train.g1_simulation_dataset import _features, generate_session
from simulation.generator.config import DatasetSplit, ScenarioCode, SimulationConfig, SimulationTimeConfig


def test_g1_core_feature_export_is_deterministic_and_23_wide():
    config = replace(SimulationConfig(), time=SimulationTimeConfig(duration_s=600.0, dt_s=0.05))
    first = generate_session(ScenarioCode.S0, DatasetSplit.TRAIN, 2026112301, config)
    second = generate_session(ScenarioCode.S0, DatasetSplit.TRAIN, 2026112301, config)
    assert len(_features()) == 23
    assert first == second
    assert first
    assert all(row["dataset_source"] == "SIMULATION" for row in first)
    assert all(row["label_source"] == "SIMULATION_SCENARIO_PROXY" for row in first)
    assert any(row["feature_valid_mask"] == (1 << 23) - 1 and row["ready_long"] and
               all(isinstance(row[name], float) for name in _features()) for row in first)


def test_window_transition_and_proxy_disagreement_are_excluded():
    class Flags:
        high_roll_active = persistent_offset_active = observed_amplitude_growth = False

    class Result:
        timestamps_s = tuple(i * 0.05 for i in range(4001))
        labels_v1 = ("NORMAL",) * 4001
        transition_flags = (False,) * 4001
        phenotype_flags_v2 = (Flags(),) * 4001

    from ml.train.g1_simulation_dataset import _window_evidence
    result = Result()
    assert _window_evidence(result, 200.0, "NORMAL") == (True, "")
    result.transition_flags = result.transition_flags[:1000] + (True,) + result.transition_flags[1001:]
    assert _window_evidence(result, 200.0, "NORMAL") == (False, "TRANSITION_IN_WINDOW")
