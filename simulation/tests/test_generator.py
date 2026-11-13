"""Standard-library tests for simulation configuration (M2-01.1)."""

import json
import math
import statistics
import unittest

from simulation.generator.config import (
    DatasetPlanConfig,
    DatasetSplit,
    GrowthCriterion,
    IMUNoiseConfig,
    LabelingVersion,
    MotionLabelConfig,
    ParameterRange,
    ProfileCalibrationStatus,
    RollDynamicsConfig,
    ScenarioCode,
    SimulationConfig,
    SimulationTimeConfig,
    ScenarioDefinition,
    SeaStateProfileConfig,
    WaveExcitationConfig,
    WaveGenerator,
)
from simulation.generator.rng import UINT32_MASK, XorShift32
from simulation.generator.roll_dynamics import (
    RollDynamics,
    RollState,
    reference_nonlinear_coefficient_rad_minus2,
)
from simulation.generator.wave_generator import CorrelatedWaveGenerator
from simulation.generator.imu_simulator import GRAVITY_M_S2, IMUSimulator
from simulation.generator.scenarios import (
    CausalMotionLabelerV2,
    ScenarioRunner,
    assign_motion_label,
    generate_scenario,
)
from simulation.visualization.plot_scenarios import (
    parse_sea_state_profile,
    run_validation,
)
from simulation.calibration.calibrate_labeling_v2 import build_pilot_plan
from simulation.calibration.validate_labeling_v2_independent import (
    build_confirmation_plan,
    load_frozen_candidate,
)


class SimulationConfigTests(unittest.TestCase):
    def test_independent_confirmation_plan_is_fixed_reproducible_and_disjoint(self):
        excluded_ids = {"pilot-s0", "pilot-s2"}
        excluded_seeds = {20261202, 20261209}
        first = build_confirmation_plan(20261202, excluded_ids=excluded_ids,
                                        excluded_seeds=excluded_seeds)
        second = build_confirmation_plan(20261202, excluded_ids=excluded_ids,
                                         excluded_seeds=excluded_seeds)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 60)
        self.assertEqual(len({item.session_id for item in first}), 60)
        self.assertEqual(len({item.seed for item in first}), 60)
        self.assertFalse({item.session_id for item in first} & excluded_ids)
        self.assertFalse({item.seed for item in first} & excluded_seeds)
        self.assertTrue(all(item.split is DatasetSplit.VALIDATION for item in first))
        for scenario in ScenarioCode:
            self.assertEqual(sum(item.scenario is scenario for item in first), 10)

    def test_independent_validator_loads_frozen_candidate_without_calibrating(self):
        config, document = load_frozen_candidate()
        self.assertAlmostEqual(config.high_roll_centered_threshold_deg, 8.40884426)
        self.assertEqual(config.persistent_offset_threshold_deg, 3.0)
        self.assertEqual(config.persistent_offset_duration_s, 120.0)
        self.assertEqual(config.growth_criterion, GrowthCriterion.SLOPE)
        self.assertAlmostEqual(config.growth_slope_threshold_deg_per_min,
                               1.769349623333755)
        self.assertEqual(config.growth_confirmation_s, 10.0)
        self.assertIsNone(config.growth_ratio_threshold)
        self.assertIsNone(config.growth_ratio_floor_deg)
        self.assertEqual(config.threshold_calibration_status,
                         ProfileCalibrationStatus.CANDIDATE)
        self.assertEqual(document["recommended_thresholds"]["calibration_status"],
                         "candidate")

    def test_documented_defaults_and_scenario_codes(self):
        config = SimulationConfig()
        self.assertEqual(config.time.sample_rate_hz, 20.0)
        self.assertEqual(config.time.output_rate_hz, 2.0)
        self.assertEqual(config.time.dt_s, 0.05)
        self.assertEqual(config.time.duration_s, 1200.0)
        self.assertEqual(config.time.sample_count, 24000)
        self.assertEqual(config.dataset.total_sessions, 605)
        self.assertEqual(config.dataset.session_counts, {
            DatasetSplit.TRAIN: 280,
            DatasetSplit.VALIDATION: 85,
            DatasetSplit.TEST_G1: 120,
            DatasetSplit.TEST_G2: 120,
        })
        self.assertEqual(config.dataset.scenario_counts, {
            ScenarioCode.S0: {DatasetSplit.TRAIN: 80, DatasetSplit.VALIDATION: 20,
                              DatasetSplit.TEST_G1: 30, DatasetSplit.TEST_G2: 30},
            ScenarioCode.S0B: {DatasetSplit.TRAIN: 30, DatasetSplit.VALIDATION: 10,
                               DatasetSplit.TEST_G1: 15, DatasetSplit.TEST_G2: 15},
            ScenarioCode.S1: {DatasetSplit.TRAIN: 50, DatasetSplit.VALIDATION: 15,
                              DatasetSplit.TEST_G1: 20, DatasetSplit.TEST_G2: 20},
            ScenarioCode.S2: {DatasetSplit.TRAIN: 50, DatasetSplit.VALIDATION: 15,
                              DatasetSplit.TEST_G1: 20, DatasetSplit.TEST_G2: 20},
            ScenarioCode.S3: {DatasetSplit.TRAIN: 50, DatasetSplit.VALIDATION: 15,
                              DatasetSplit.TEST_G1: 20, DatasetSplit.TEST_G2: 20},
            ScenarioCode.H1: {DatasetSplit.TRAIN: 20, DatasetSplit.VALIDATION: 10,
                              DatasetSplit.TEST_G1: 15, DatasetSplit.TEST_G2: 15},
        })
        self.assertEqual(config.random_seed, 1)
        self.assertFalse(config.labeling.labeling_v2_ready)
        self.assertFalse(config.official_dataset_ready)
        self.assertEqual(config.sea_state_profile.calibration_status,
                         ProfileCalibrationStatus.CANDIDATE)
        self.assertEqual(config.sea_state_profile.sigma_w_by_state_deg, {
            "SS0": 0.5, "SS1": 0.9, "SS2": 1.5,
            "SS3": 2.2, "SS4": 3.0, "SS5": 4.5,
        })
        self.assertEqual(
            tuple(item.code for item in config.scenarios),
            (ScenarioCode.S0, ScenarioCode.S0B, ScenarioCode.S1,
             ScenarioCode.S2, ScenarioCode.S3, ScenarioCode.H1),
        )
        self.assertEqual(config.waves.generator, WaveGenerator.G1)
        self.assertEqual(config.dataset.domains.train.parameters["natural_period_s"],
                         ParameterRange(14.0, 26.0, "s"))
        self.assertEqual(config.dataset.domains.validation.parameters["damping_ratio"],
                         ParameterRange(0.03, 0.06, "1"))
        for split in (config.dataset.domains.test_g1,
                      config.dataset.domains.test_g2):
            self.assertEqual(split.parameters["natural_period_s"],
                             ParameterRange(12.0, 32.0, "s"))
            self.assertEqual(split.parameters["damping_ratio"],
                             ParameterRange(0.02, 0.08, "1"))
            self.assertEqual(split.parameters["t0_s"],
                             ParameterRange(180.0, 540.0, "s"))
        self.assertEqual(config.dataset.domains.train.parameters["t0_s"],
                         ParameterRange(240.0, 480.0, "s"))
        self.assertEqual(config.dataset.domains.validation.parameters["t0_s"],
                         ParameterRange(240.0, 480.0, "s"))

    def test_calibration_pilot_plan_is_reproducible_unique_and_has_no_test_splits(self):
        first = build_pilot_plan(12345)
        second = build_pilot_plan(12345)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 90)
        self.assertEqual(len({entry.session_id for entry in first}), 90)
        self.assertEqual(len({entry.seed for entry in first}), 90)
        self.assertTrue(all(entry.split in (DatasetSplit.TRAIN,
                                            DatasetSplit.VALIDATION)
                            for entry in first))
        self.assertEqual(sum(entry.split is DatasetSplit.TRAIN for entry in first), 60)
        self.assertEqual(sum(entry.split is DatasetSplit.VALIDATION for entry in first), 30)
        for scenario in ScenarioCode:
            self.assertEqual(sum(entry.scenario is scenario and
                                 entry.split is DatasetSplit.TRAIN for entry in first), 10)
            self.assertEqual(sum(entry.scenario is scenario and
                                 entry.split is DatasetSplit.VALIDATION for entry in first), 5)

    def test_validation_tool_uses_candidate_profile_and_blocks_uncalibrated_v2(self):
        profile_deg, is_default = parse_sea_state_profile(None)
        self.assertTrue(is_default)
        self.assertEqual(profile_deg, SimulationConfig().sea_state_profile.sigma_w_by_state_deg)
        with self.assertRaisesRegex(ValueError, "thresholds are not calibrated"):
            run_validation(sessions_per_scenario=1, labeling_version=LabelingVersion.V2,
                           make_plots=False)

    def test_unspecified_physical_parameters_are_not_assumed(self):
        config = SimulationConfig()
        self.assertIsNone(config.roll.natural_period_s)
        self.assertIsNone(config.roll.damping_ratio)
        self.assertIsNone(config.waves.g2_significant_height_m)
        self.assertIsNone(config.waves.g2_peak_period_s)
        self.assertIsNone(config.imu.roll_noise_std_rad)
        self.assertIsNone(config.imu.gyro_noise_std_rad_s)

    def test_rejects_invalid_timing_seed_and_parameter_ranges(self):
        with self.assertRaises(ValueError):
            SimulationTimeConfig(duration_s=0.0)
        with self.assertRaises(ValueError):
            SimulationTimeConfig(sample_rate_hz=1.0, output_rate_hz=2.0)
        with self.assertRaises(ValueError):
            SimulationTimeConfig(output_rate_hz=3.0)
        with self.assertRaises(ValueError):
            SimulationTimeConfig(dt_s=0.1)
        with self.assertRaises(ValueError):
            SimulationTimeConfig(duration_s=1200.01)
        with self.assertRaises(ValueError):
            SimulationConfig(random_seed=0)
        with self.assertRaises(ValueError):
            ParameterRange(minimum=2.0, maximum=1.0, unit="rad")
        with self.assertRaises(ValueError):
            RollDynamicsConfig(natural_period_s=0.0)
        with self.assertRaises(ValueError):
            IMUNoiseConfig(roll_noise_std_rad=-0.1)
        with self.assertRaises(ValueError):
            DatasetPlanConfig(session_counts={
                DatasetSplit.TRAIN: 280,
                DatasetSplit.VALIDATION: 85,
                DatasetSplit.TEST_G1: 119,
                DatasetSplit.TEST_G2: 120,
            })
        with self.assertRaises(TypeError):
            DatasetPlanConfig(session_counts={
                "Train": 280,
                DatasetSplit.VALIDATION: 85,
                DatasetSplit.TEST_G1: 120,
                DatasetSplit.TEST_G2: 120,
            })
        with self.assertRaises(TypeError):
            ScenarioDefinition(code="S0", description="calm", expected_label="NORMAL")
        with self.assertRaises(ValueError):
            SimulationConfig(time=SimulationTimeConfig(duration_s=500.0))

    def test_rejects_unknown_scenario_and_dataset_split_codes(self):
        config_data = SimulationConfig().to_dict()
        config_data["scenarios"][0]["code"] = "UNKNOWN"
        with self.assertRaises(ValueError):
            SimulationConfig.from_dict(config_data)

        config_data = SimulationConfig().to_dict()
        config_data["dataset"]["session_counts"]["Test-Unknown"] = 120
        with self.assertRaises(ValueError):
            SimulationConfig.from_dict(config_data)

        config_data = SimulationConfig().to_dict()
        config_data["dataset"]["scenario_counts"]["H1"]["Train"] += 1
        with self.assertRaises(ValueError):
            SimulationConfig.from_dict(config_data)

    def test_metadata_json_roundtrip_restores_configuration(self):
        config = SimulationConfig(
            roll=RollDynamicsConfig(heel_offset_rad=0.1,
                                    initial_roll_rate_rad_s=0.02),
        )
        metadata = config.to_dict()
        serialized = json.dumps(metadata, sort_keys=True)
        restored = SimulationConfig.from_dict(json.loads(serialized))
        self.assertEqual(restored, config)
        self.assertEqual(metadata["waves"]["generator"], "G1")
        self.assertEqual(metadata["scenarios"][1]["code"], "S0b")
        self.assertEqual(metadata["dataset"]["session_counts"], {
            "Train": 280,
            "Validation": 85,
            "Test-G1": 120,
            "Test-G2": 120,
        })
        self.assertEqual(restored.dataset.scenario_counts, config.dataset.scenario_counts)
        self.assertEqual(metadata["roll"]["heel_offset_rad"], 0.1)
        self.assertEqual(
            metadata["dataset"]["domains"]["train"]["parameters"]
            ["natural_period_s"]["unit"], "s")
        self.assertEqual(set(item.value for item in DatasetSplit),
                         {"Train", "Validation", "Test-G1", "Test-G2"})

    def test_labeling_thresholds_are_optional_until_validation_calibration(self):
        self.assertIsNone(SimulationConfig().labeling.high_roll_centered_threshold_deg)
        calibrated_fixture = MotionLabelConfig(
            high_roll_centered_threshold_deg=1.25,
            growth_criterion=GrowthCriterion.SLOPE_AND_RATIO,
            growth_slope_threshold_deg_per_min=0.2,
            growth_ratio_threshold=1.1,
            growth_ratio_floor_deg=0.01,
            growth_confirmation_s=10.0,
            threshold_calibration_status=ProfileCalibrationStatus.CALIBRATED,
        )
        self.assertTrue(calibrated_fixture.labeling_v2_ready)
        partial = MotionLabelConfig(growth_ratio_threshold=1.1)
        self.assertFalse(partial.labeling_v2_configured)
        self.assertIn("growth_criterion", partial.unresolved_v2_thresholds)

    def test_candidate_sea_state_profile_converts_degrees_once_and_validates(self):
        profile = SeaStateProfileConfig.from_degrees({
            "SS0": 0.5, "SS1": 0.9, "SS2": 1.5,
            "SS3": 2.2, "SS4": 3.0, "SS5": 4.5,
        })
        self.assertAlmostEqual(profile.sigma_w_by_state_rad["SS5"], math.radians(4.5))
        self.assertEqual(profile.sigma_w_by_state_deg["SS4"], 3.0)
        with self.assertRaises(ValueError):
            SeaStateProfileConfig.from_degrees({
                "SS0": 1.0, "SS1": 0.9, "SS2": 1.5,
                "SS3": 2.2, "SS4": 3.0, "SS5": 4.5,
            })

    def test_angular_units_are_explicit_and_reproducible_construction_matches(self):
        kwargs = {
            "random_seed": 123,
            "roll": RollDynamicsConfig(heel_offset_rad=0.25,
                                        initial_roll_rate_rad_s=0.03),
            "imu": IMUNoiseConfig(gyro_bias_rad_s=0.004),
        }
        first = SimulationConfig(**kwargs)
        second = SimulationConfig(**kwargs)
        self.assertEqual(first, second)
        roll_metadata = first.to_dict()["roll"]
        imu_metadata = first.to_dict()["imu"]
        self.assertIn("heel_offset_rad", roll_metadata)
        self.assertIn("initial_roll_rate_rad_s", roll_metadata)
        self.assertIn("gyro_bias_rad_s", imu_metadata)
        self.assertNotIn("heel_offset_deg", roll_metadata)


class XorShift32Tests(unittest.TestCase):
    def test_same_seed_and_call_sequence_is_reproducible(self):
        first = XorShift32(0x12345678)
        second = XorShift32(0x12345678)
        self.assertEqual([first.next_uint32() for _ in range(20)],
                         [second.next_uint32() for _ in range(20)])

    def test_different_seeds_produce_different_sequences(self):
        first = XorShift32(1)
        second = XorShift32(2)
        self.assertNotEqual([first.next_uint32() for _ in range(8)],
                            [second.next_uint32() for _ in range(8)])

    def test_state_and_outputs_remain_unsigned_32_bit(self):
        for seed in (0, 1, 0x12345678, UINT32_MASK):
            rng = XorShift32(seed)
            self.assertEqual(rng.state, seed)
            for _ in range(1000):
                value = rng.next_uint32()
                self.assertGreaterEqual(value, 0)
                self.assertLessEqual(value, UINT32_MASK)
                self.assertEqual(rng.state, value)

    def test_zero_seed_matches_c_zero_state_convention(self):
        rng = XorShift32(0)
        self.assertEqual(rng.seed, 0)
        self.assertEqual([rng.next_uint32() for _ in range(5)], [0] * 5)
        self.assertEqual(XorShift32(0).random(), 0.0)

    def test_random_values_are_uniform_mapping_in_half_open_unit_interval(self):
        rng = XorShift32(0xA5A5A5A5)
        for _ in range(10000):
            value = rng.random()
            self.assertGreaterEqual(value, 0.0)
            self.assertLess(value, 1.0)

        integer_rng = XorShift32(987654321)
        float_rng = XorShift32(987654321)
        expected = integer_rng.next_uint32() / float(1 << 32)
        self.assertEqual(float_rng.random(), expected)

    def test_seed_must_fit_unsigned_32_bit(self):
        for seed in (-1, UINT32_MASK + 1):
            with self.assertRaises(ValueError):
                XorShift32(seed)
        with self.assertRaises(TypeError):
            XorShift32(True)

    def test_box_muller_normal_values_are_finite_and_reproducible(self):
        first = XorShift32(0x1234ABCD)
        second = XorShift32(0x1234ABCD)
        values_a = [first.normal() for _ in range(100)]
        values_b = [second.normal() for _ in range(100)]
        self.assertEqual(values_a, values_b)
        self.assertTrue(all(math.isfinite(value) for value in values_a))
        self.assertTrue(math.isfinite(XorShift32(0).normal()))


class CorrelatedWaveGeneratorTests(unittest.TestCase):
    @staticmethod
    def make_generator(seed, sigma_w_rad=0.4, correlation_time_s=3.0, dt_s=0.05):
        config = WaveExcitationConfig(
            g1_forcing_std_rad=sigma_w_rad,
            g1_correlation_time_s=correlation_time_s,
        )
        return CorrelatedWaveGenerator(config, dt_s=dt_s, seed=seed)

    def test_same_seed_and_parameters_reproduce_wave_sequence(self):
        first = self.make_generator(123456)
        second = self.make_generator(123456)
        self.assertEqual([first.step() for _ in range(500)],
                         [second.step() for _ in range(500)])

    def test_private_prng_instance_matches_generator_seed_path(self):
        config = WaveExcitationConfig(g1_forcing_std_rad=0.2)
        via_seed = CorrelatedWaveGenerator(config, seed=4242)
        via_instance = CorrelatedWaveGenerator(config, rng=XorShift32(4242))
        self.assertEqual([via_seed.step() for _ in range(100)],
                         [via_instance.step() for _ in range(100)])

    def test_different_seeds_give_different_sequences(self):
        first = self.make_generator(11)
        second = self.make_generator(12)
        self.assertNotEqual([first.step() for _ in range(100)],
                            [second.step() for _ in range(100)])

    def test_zero_sigma_and_zero_initial_state_produce_zero_signal(self):
        generator = self.make_generator(77, sigma_w_rad=0.0)
        self.assertEqual(generator.current_value_rad, 0.0)
        self.assertEqual(generator.timestamp_s, 0.0)
        self.assertEqual([generator.step() for _ in range(100)], [0.0] * 100)

    def test_output_and_state_remain_finite(self):
        generator = self.make_generator(98765)
        for _ in range(5000):
            value = generator.step()
            self.assertTrue(math.isfinite(value))
            self.assertTrue(math.isfinite(generator.current_value_rad))
            self.assertTrue(math.isfinite(generator.timestamp_s))

    def test_rejects_invalid_sigma_correlation_time_dt_and_rng_setup(self):
        with self.assertRaises(ValueError):
            self.make_generator(1, sigma_w_rad=-0.1)
        with self.assertRaises(ValueError):
            self.make_generator(1, sigma_w_rad=float("nan"))
        with self.assertRaises(ValueError):
            self.make_generator(1, correlation_time_s=0.0)
        with self.assertRaises(ValueError):
            self.make_generator(1, dt_s=float("inf"))
        with self.assertRaises(ValueError):
            CorrelatedWaveGenerator(WaveExcitationConfig(g1_forcing_std_rad=0.1))
        with self.assertRaises(ValueError):
            self.make_generator(0)
        with self.assertRaises(ValueError):
            CorrelatedWaveGenerator(
                WaveExcitationConfig(g1_forcing_std_rad=0.1), seed=1, rng=XorShift32(1))
        with self.assertRaises(TypeError):
            CorrelatedWaveGenerator(
                WaveExcitationConfig(g1_forcing_std_rad=0.1), rng=object())

    def test_sigma_in_degrees_is_converted_once_at_construction(self):
        generator = CorrelatedWaveGenerator(
            WaveExcitationConfig(), sigma_w_deg=10.0, seed=9)
        self.assertAlmostEqual(generator.sigma_w_rad, math.radians(10.0))

    def test_ar1_lag_one_autocorrelation_matches_rho_within_tolerance(self):
        generator = self.make_generator(2026, sigma_w_rad=0.7)
        samples = [generator.step() for _ in range(60000)][1000:]
        mean = statistics.fmean(samples)
        denominator = sum((value - mean) ** 2 for value in samples[:-1])
        covariance = sum((left - mean) * (right - mean)
                         for left, right in zip(samples[:-1], samples[1:]))
        empirical_rho = covariance / denominator
        self.assertAlmostEqual(empirical_rho, generator.rho, delta=0.015)

    def test_sample_mean_and_standard_deviation_match_stationary_targets(self):
        sigma = 0.35
        generator = self.make_generator(314159, sigma_w_rad=sigma)
        samples = [generator.step() for _ in range(80000)][1000:]
        self.assertLess(abs(statistics.fmean(samples)), 0.06)
        self.assertAlmostEqual(statistics.pstdev(samples), sigma, delta=0.06)


class IMUSimulatorTests(unittest.TestCase):
    @staticmethod
    def make_simulator(noise_config=None, seed=2468, lever_arm=(0.0, 0.0, 0.0)):
        return IMUSimulator(
            noise_config=noise_config or IMUNoiseConfig(),
            time_config=SimulationTimeConfig(),
            seed=seed,
            lever_arm_body_m=lever_arm,
        )

    def test_level_static_specific_force_is_one_g_on_negative_z(self):
        simulator = self.make_simulator()
        sample = simulator.sample(RollState(0.0, 0.0, 0.0), 0.0)
        self.assertAlmostEqual(sample.ax, 0.0)
        self.assertAlmostEqual(sample.ay, 0.0)
        self.assertAlmostEqual(sample.az, -GRAVITY_M_S2, places=12)
        self.assertEqual((sample.gx, sample.gy, sample.gz), (0.0, 0.0, 0.0))
        self.assertEqual(sample.timestamp_s, 0.0)
        self.assertTrue(sample.valid)
        self.assertEqual(sample.source_mode, 1)
        self.assertFalse(sample.noise_applied)

    def test_roll_angle_rotates_gravity_projection_with_selected_sign(self):
        phi = math.radians(30.0)
        sample = self.make_simulator().sample(RollState(phi, 0.0, 1.0), 0.0)
        self.assertAlmostEqual(sample.ay, -GRAVITY_M_S2 * math.sin(phi), places=12)
        self.assertAlmostEqual(sample.az, -GRAVITY_M_S2 * math.cos(phi), places=12)

    def test_gyro_x_tracks_roll_rate_and_other_axes_are_ideal_zero(self):
        omega = 0.42
        sample = self.make_simulator().sample(RollState(0.1, omega, 2.0), 0.0)
        self.assertAlmostEqual(sample.gx, omega)
        self.assertEqual(sample.gy, 0.0)
        self.assertEqual(sample.gz, 0.0)

    def test_sensor_on_roll_axis_has_no_rotational_acceleration(self):
        phi, omega, alpha = 0.25, 1.7, -0.8
        sample = self.make_simulator().sample(RollState(phi, omega, 0.5), alpha)
        self.assertAlmostEqual(sample.ax, 0.0)
        self.assertAlmostEqual(sample.ay, -GRAVITY_M_S2 * math.sin(phi))
        self.assertAlmostEqual(sample.az, -GRAVITY_M_S2 * math.cos(phi))

    def test_lever_arm_includes_tangential_and_centripetal_acceleration(self):
        phi, omega, alpha = 0.3, 2.0, 1.5
        lever_y, lever_z = 0.2, -0.1
        sample = self.make_simulator(
            lever_arm=(0.0, lever_y, lever_z)
        ).sample(RollState(phi, omega, 0.5), alpha)
        expected_ay = (-GRAVITY_M_S2 * math.sin(phi)
                       - alpha * lever_z - omega ** 2 * lever_y)
        expected_az = (-GRAVITY_M_S2 * math.cos(phi)
                       + alpha * lever_y - omega ** 2 * lever_z)
        self.assertAlmostEqual(sample.ay, expected_ay, places=12)
        self.assertAlmostEqual(sample.az, expected_az, places=12)

    def test_same_seed_and_input_sequence_reproduce_noisy_imu(self):
        noise = IMUNoiseConfig(
            gyro_noise_std_rad_s=0.015,
            gyro_bias_rad_s=0.004,
        )
        first = self.make_simulator(noise_config=noise, seed=8080)
        second = self.make_simulator(noise_config=noise, seed=8080)
        states = [RollState(0.01 * i, 0.02 * i, 0.05 * i) for i in range(20)]
        outputs_a = [first.sample(state, 0.03) for state in states]
        outputs_b = [second.sample(state, 0.03) for state in states]
        self.assertEqual(outputs_a, outputs_b)
        self.assertTrue(all(sample.noise_applied for sample in outputs_a))

    def test_configured_gyro_bias_and_noise_are_applied(self):
        noise = IMUNoiseConfig(gyro_noise_std_rad_s=0.02,
                               gyro_bias_rad_s=0.01)
        sample = self.make_simulator(noise_config=noise).sample(
            RollState(0.0, 0.3, 0.0), 0.0)
        self.assertTrue(sample.noise_applied)
        self.assertTrue(math.isfinite(sample.gx))
        self.assertTrue(math.isfinite(sample.gy))
        self.assertTrue(math.isfinite(sample.gz))
        self.assertAlmostEqual(sample.ax, 0.0)
        self.assertAlmostEqual(sample.az, -GRAVITY_M_S2)

        bias_only = self.make_simulator(
            IMUNoiseConfig(gyro_bias_rad_s=0.01)
        ).sample(RollState(0.0, 0.3, 0.0), 0.0)
        self.assertAlmostEqual(bias_only.gx, 0.31)
        self.assertAlmostEqual(bias_only.gy, 0.01)
        self.assertAlmostEqual(bias_only.gz, 0.01)

    def test_samples_remain_finite_and_keep_si_field_units(self):
        simulator = self.make_simulator(
            IMUNoiseConfig(gyro_noise_std_rad_s=0.03),
            lever_arm=(0.0, 0.1, 0.05),
        )
        for index in range(1000):
            sample = simulator.sample(
                RollState(0.2, 0.4, index * 0.05), angular_acceleration_rad_s2=0.1)
            for value in (sample.ax, sample.ay, sample.az,
                          sample.gx, sample.gy, sample.gz, sample.t):
                self.assertTrue(math.isfinite(value))
        self.assertEqual(simulator.dt_s, 0.05)

    def test_invalid_seed_lever_arm_and_kinematic_inputs_are_rejected(self):
        with self.assertRaises(ValueError):
            IMUSimulator(IMUNoiseConfig(), seed=0)
        with self.assertRaises(ValueError):
            IMUSimulator(IMUNoiseConfig(), seed=1, lever_arm_body_m=(0.0, 1.0))
        with self.assertRaises(ValueError):
            self.make_simulator().sample(RollState(0.0, 0.0, 0.0), float("inf"))
        with self.assertRaises(TypeError):
            self.make_simulator().sample(object(), 0.0)


class ScenarioRunnerTests(unittest.TestCase):
    @classmethod
    def make_runner(cls):
        return ScenarioRunner(SimulationConfig())

    def test_label_priority_and_warmup_are_explicit(self):
        common = {
            "heel_offset_rad": math.radians(5.0),
            "heel_duration_s": 200.0,
        }
        self.assertIsNone(assign_motion_label(None, parametric_excitation_active=True,
                                              **common))
        self.assertEqual(assign_motion_label(
            math.radians(7.0), parametric_excitation_active=True, **common), "HIGH_ROLL")
        self.assertEqual(assign_motion_label(
            math.radians(5.0), parametric_excitation_active=True, **common),
            "AMPLITUDE_GROWTH")
        self.assertEqual(assign_motion_label(
            math.radians(5.0), parametric_excitation_active=False, **common),
            "PERSISTENT_OFFSET")
        self.assertEqual(assign_motion_label(
            math.radians(5.0), parametric_excitation_active=False,
            heel_offset_rad=math.radians(5.0), heel_duration_s=119.95), "NORMAL")

    def test_scenarios_generate_aligned_finite_sessions_with_metadata(self):
        runner = self.make_runner()
        expected_targets = {
            ScenarioCode.S0: "NORMAL",
            ScenarioCode.S0B: "NORMAL",
            ScenarioCode.S1: "HIGH_ROLL",
            ScenarioCode.S2: "PERSISTENT_OFFSET",
            ScenarioCode.S3: "AMPLITUDE_GROWTH",
            ScenarioCode.H1: None,
        }
        results = {}
        for scenario in ScenarioCode:
            result = runner.generate(scenario, seed=1000 + len(results))
            results[scenario] = result
            self.assertEqual(result.nominal_target_label, expected_targets[scenario])
            self.assertEqual(len(result.timestamps_s), 24000)
            self.assertEqual(len(result.imu_samples), 24000)
            self.assertEqual(result.timestamps_s[0], 0.0)
            self.assertAlmostEqual(result.timestamps_s[-1], 1199.95)
            self.assertTrue(all(
                right > left for left, right in
                zip(result.timestamps_s, result.timestamps_s[1:])))
            self.assertEqual(result.metadata["sampled_parameters"]["natural_period_s"] > 0,
                             True)
            for values in (result.true_roll_rad, result.true_roll_rate_rad_s,
                           result.true_roll_acceleration_rad_s2,
                           result.wave_excitation_rad, result.wave_sigma_rad):
                self.assertTrue(all(math.isfinite(value) for value in values))
            for sample in result.imu_samples:
                self.assertTrue(all(math.isfinite(value) for value in
                                    (sample.ax, sample.ay, sample.az,
                                     sample.gx, sample.gy, sample.gz, sample.t)))
            self.assertEqual(result.imu_samples[0].t, result.timestamps_s[0])
            self.assertEqual(result.imu_samples[-1].t, result.timestamps_s[-1])
            self.assertEqual(result.metadata["sample_count"], 24000)
            self.assertEqual(result.metadata["last_timestamp_s"], 1199.95)
            self.assertEqual(result.metadata["units"]["accelerometer"], "m/s^2")
            self.assertEqual(result.metadata["units"]["gyroscope"], "rad/s")

        self.assertEqual(results[ScenarioCode.S0].events, ())
        self.assertTrue(all(value == 0.0 for value in results[ScenarioCode.S0].heel_offset_rad))
        self.assertTrue(all(value == 0.0 for value in
                            results[ScenarioCode.S0].parametric_excitation_amplitude))

    def test_seed_reproduces_complete_scenario_result(self):
        runner = self.make_runner()
        first = runner.generate(ScenarioCode.S0B, seed=223344)
        second = runner.generate(ScenarioCode.S0B, seed=223344)
        self.assertEqual(first.timestamps_s, second.timestamps_s)
        self.assertEqual(first.true_roll_rad, second.true_roll_rad)
        self.assertEqual(first.true_roll_rate_rad_s, second.true_roll_rate_rad_s)
        self.assertEqual(first.wave_excitation_rad, second.wave_excitation_rad)
        self.assertEqual(first.imu_samples, second.imu_samples)
        self.assertEqual(first.labels, second.labels)
        self.assertEqual(first.metadata, second.metadata)

    def test_s0b_is_temporary_and_not_labeled_persistent_offset(self):
        result = self.make_runner().generate(ScenarioCode.S0B, seed=1122)
        event = result.events[0]
        duration = event["end_s"] - event["t0_s"]
        self.assertGreaterEqual(duration, 20.0)
        self.assertLessEqual(duration, 90.0)
        self.assertLess(duration, 120.0)
        self.assertNotIn("PERSISTENT_OFFSET", result.labels)
        self.assertTrue(any(result.transition_flags))

    def test_s1_switches_wave_sigma_at_event_and_records_real_outcome(self):
        result = self.make_runner().generate(ScenarioCode.S1, seed=5566)
        parameters = result.metadata["sampled_parameters"]
        event = result.events[0]
        t0 = event["t0_s"]
        index = int(round(t0 / 0.05))
        self.assertAlmostEqual(result.metadata["sampled_parameters"]["t0_s"], t0)
        self.assertEqual(result.sea_states[index], event["sea_state"])
        self.assertLess(result.wave_sigma_rad[index - 1], result.wave_sigma_rad[index])
        self.assertGreaterEqual(parameters["event_sigma_w_deg"], 3.0)
        self.assertLessEqual(parameters["event_sigma_w_deg"], 4.5)
        self.assertIn(event["sea_state"], ("SS4", "SS5"))
        self.assertEqual(
            parameters["event_sigma_w_deg"],
            SimulationConfig().sea_state_profile.sigma_w_by_state_deg[event["sea_state"]],
        )
        self.assertIn("high_roll_threshold_reached",
                      result.metadata["outcome_checks"])

    def test_s2_has_sustained_heel_and_separates_event_from_label_time(self):
        result = self.make_runner().generate(ScenarioCode.S2, seed=321)
        event = result.events[0]
        t0 = event["t0_s"]
        self.assertGreaterEqual(event["end_s"] - t0, 600.0)
        self.assertAlmostEqual(result.heel_offset_rad[int(t0 / 0.05)],
                               math.radians(event["heel_offset_deg"]))
        self.assertEqual(event["minimum_label_delay_s"], 120.0)
        self.assertGreaterEqual(t0, 240.0)
        earlier_persistent = [timestamp for timestamp, label in
                              zip(result.timestamps_s, result.labels)
                              if timestamp < t0 + 120.0 and label == "PERSISTENT_OFFSET"]
        self.assertEqual(earlier_persistent, [])

    def test_s3_activates_parametric_excitation_at_t0_and_records_kappa(self):
        result = self.make_runner().generate(ScenarioCode.S3, seed=7654)
        event = result.events[0]
        t0_index = int(event["t0_s"] / 0.05)
        self.assertEqual(result.parametric_excitation_amplitude[t0_index - 1], 0.0)
        self.assertGreaterEqual(result.parametric_excitation_amplitude[t0_index], 0.25)
        self.assertLessEqual(result.parametric_excitation_amplitude[t0_index], 0.5)
        params = result.metadata["sampled_parameters"]
        self.assertAlmostEqual(
            params["excitation_angular_frequency_rad_s"],
            2.0 * (2.0 * math.pi / params["natural_period_s"]),
        )
        self.assertGreater(params["kappa_used_rad_minus2"], 0.0)
        self.assertIn("amplitude_growth", result.metadata["outcome_checks"])

    def test_h1_combines_high_sea_and_heel_event(self):
        result = self.make_runner().generate(ScenarioCode.H1, seed=9988)
        event = result.events[0]
        index = int(event["t0_s"] / 0.05)
        self.assertIn(event["sea_state"], ("SS4", "SS5"))
        self.assertEqual(
            result.metadata["sampled_parameters"]["event_sigma_w_deg"],
            SimulationConfig().sea_state_profile.sigma_w_by_state_deg[event["sea_state"]],
        )
        self.assertGreaterEqual(event["heel_offset_deg"], 3.0)
        self.assertLessEqual(event["heel_offset_deg"], 6.0)
        self.assertAlmostEqual(result.heel_offset_rad[index],
                               math.radians(event["heel_offset_deg"]))
        self.assertEqual(result.metadata["outcome_checks"]["observed_labels"],
                         sorted(set(label for label in result.labels if label is not None)))

    def test_transition_ends_at_t0_plus_90_seconds(self):
        result = self.make_runner().generate(ScenarioCode.S1, seed=5678)
        t0 = result.events[0]["t0_s"]
        start = int(t0 / 0.05)
        end = int((t0 + 90.0) / 0.05)
        self.assertTrue(result.transition_flags[start])
        self.assertTrue(result.transition_flags[end - 1])
        self.assertFalse(result.transition_flags[end])

    def test_default_uses_approved_candidate_profile_and_rejects_partial_override(self):
        self.assertEqual(
            ScenarioRunner(SimulationConfig()).sea_state_sigma_deg,
            SimulationConfig().sea_state_profile.sigma_w_by_state_deg)
        with self.assertRaises(ValueError):
            ScenarioRunner(SimulationConfig(), sea_state_sigma_deg={"SS0": 0.1})
        with self.assertRaises(ValueError):
            self.make_runner().generate(ScenarioCode.S0, seed=0)

    @staticmethod
    def make_v2_labeler():
        config = SimulationConfig(labeling=MotionLabelConfig(
            high_roll_centered_threshold_deg=1.0,
            growth_criterion=GrowthCriterion.SLOPE,
            growth_slope_threshold_deg_per_min=0.05,
            growth_confirmation_s=1.0,
        ))
        return CausalMotionLabelerV2(config)

    def test_labeling_v1_remains_available_and_v2_default_is_not_dataset_ready(self):
        runner = self.make_runner()
        result_v1 = runner.generate(ScenarioCode.S0, seed=100, labeling_version="v1")
        result_v2 = runner.generate(ScenarioCode.S0, seed=100, labeling_version="v2")
        self.assertEqual(result_v1.labels, result_v1.labels_v1)
        self.assertEqual(result_v2.labels, result_v2.labels_v2)
        self.assertEqual(result_v1.labels_v1, result_v2.labels_v1)
        self.assertFalse(result_v2.metadata["labeling"]["v2_ready"])
        self.assertFalse(result_v2.metadata["labeling"]["official_dataset_ready"])
        self.assertTrue(all(label is None for label in result_v2.labels_v2))
        self.assertEqual(result_v1.labels_for(LabelingVersion.V1), result_v1.labels_v1)

    def test_centered_rms_matches_population_standard_deviation(self):
        labeler = self.make_v2_labeler()
        values = [0.0 if index % 2 == 0 else math.radians(2.0)
                  for index in range(1201)]
        step = None
        for index, value in enumerate(values):
            step = labeler.step(index * 0.05, value)
        expected = statistics.pstdev(values)
        self.assertAlmostEqual(step.metrics.rms_centered_60_rad, expected, places=12)

    def test_constant_offset_alone_does_not_set_high_roll(self):
        labeler = self.make_v2_labeler()
        step = None
        for index in range(7001):
            step = labeler.step(index * 0.05, math.radians(5.0))
        self.assertFalse(step.flags.high_roll_active)
        self.assertAlmostEqual(step.metrics.rms_centered_60_rad, 0.0, places=12)
        self.assertTrue(step.flags.persistent_offset_active)
        self.assertEqual(step.label, "PERSISTENT_OFFSET")

    def test_large_oscillation_around_offset_can_set_both_phenotypes(self):
        labeler = self.make_v2_labeler()
        step = None
        for index in range(7001):
            timestamp = index * 0.05
            roll = math.radians(5.0 + 2.0 * math.sin(2.0 * math.pi * timestamp / 8.0))
            step = labeler.step(timestamp, roll)
        self.assertTrue(step.flags.high_roll_active)
        self.assertTrue(step.flags.persistent_offset_active)
        self.assertEqual(step.label, "HIGH_ROLL")

    def test_temporary_offset_does_not_reach_persistent_duration(self):
        labeler = self.make_v2_labeler()
        for index in range(6001):
            timestamp = index * 0.05
            roll = math.radians(5.0) if timestamp < 90.0 else 0.0
            step = labeler.step(timestamp, roll)
        self.assertFalse(step.flags.persistent_offset_active)
        self.assertNotEqual(step.label, "PERSISTENT_OFFSET")

    def test_growth_requires_observed_trend_and_ignores_source_metadata(self):
        labeler = self.make_v2_labeler()
        final = None
        for index in range(7001):
            timestamp = index * 0.05
            # Constant zero roll is deliberately paired with no source input;
            # the labeler API has no h, scenario, seed, sea-state or t0 argument.
            final = labeler.step(timestamp, 0.0)
        self.assertFalse(final.flags.observed_amplitude_growth)
        self.assertEqual(final.label, "NORMAL")

    def test_future_samples_cannot_change_a_past_label(self):
        prefix_count = 7000
        prefix = [math.radians(1.5 * math.sin(2 * math.pi * index * 0.05 / 8.0))
                  for index in range(prefix_count)]
        future_a = [0.0] * 100
        future_b = [math.radians(20.0)] * 100
        outputs = []
        for future in (future_a, future_b):
            labeler = self.make_v2_labeler()
            labels = []
            for index, value in enumerate(prefix + future):
                labels.append(labeler.step(index * 0.05, value).label)
            outputs.append(labels)
        self.assertEqual(outputs[0][:prefix_count], outputs[1][:prefix_count])

    def test_transition_and_scenario_metadata_are_not_labeler_inputs(self):
        before = self.make_v2_labeler()
        after = self.make_v2_labeler()
        prefix = [math.radians(0.5 * math.sin(index * 0.02)) for index in range(4801)]
        decisions_a = [before.step(index * 0.05, value) for index, value in enumerate(prefix)]
        decisions_b = [after.step(index * 0.05, value) for index, value in enumerate(prefix)]
        self.assertEqual(decisions_a, decisions_b)

    def test_convenience_api_accepts_split_and_seed(self):
        result = generate_scenario(
            SimulationConfig(),
            ScenarioCode.S0,
            seed=123,
            dataset_split=DatasetSplit.VALIDATION,
        )
        self.assertEqual(result.scenario_id, ScenarioCode.S0)
        self.assertEqual(result.metadata["dataset_split"], "Validation")


class RollDynamicsTests(unittest.TestCase):
    @staticmethod
    def make_model(period_s=8.0, damping=0.0, kappa=0.0):
        config = RollDynamicsConfig(
            natural_period_s=period_s,
            damping_ratio=damping,
            nonlinear_coefficient=kappa,
        )
        return RollDynamics(config, SimulationTimeConfig())

    def test_zero_state_without_excitation_remains_zero(self):
        model = self.make_model(damping=0.05)
        state = RollState(0.0, 0.0, 0.0)
        for _ in range(200):
            state = model.step(state)
        self.assertEqual(state.phi_rad, 0.0)
        self.assertEqual(state.omega_rad_s, 0.0)
        self.assertAlmostEqual(state.timestamp_s, 10.0, places=12)

    def test_same_parameters_and_initial_state_reproduce_same_step(self):
        model_a = self.make_model(damping=0.03, kappa=0.2)
        model_b = self.make_model(damping=0.03, kappa=0.2)
        initial = RollState(0.12, -0.04, 2.5)
        kwargs = {
            "wave_excitation_rad": 0.01,
            "heel_offset_rad": 0.025,
            "parametric_excitation_amplitude": 0.1,
            "excitation_angular_frequency_rad_s": 1.7,
        }
        self.assertEqual(model_a.step(initial, **kwargs),
                         model_b.step(initial, **kwargs))

    def test_initial_state_uses_configured_roll_initial_conditions(self):
        config = RollDynamicsConfig(
            natural_period_s=8.0,
            damping_ratio=0.05,
            initial_roll_rad=0.12,
            initial_roll_rate_rad_s=-0.03,
        )
        state = RollDynamics(config).initial_state(timestamp_s=1.5)
        self.assertEqual(state, RollState(0.12, -0.03, 1.5))

    def test_damped_free_oscillation_decays_and_stays_finite(self):
        model = self.make_model(damping=0.12)
        state = RollState(0.2, 0.0, 0.0)
        initial_abs_angle = abs(state.phi_rad)
        for _ in range(20 * 20):
            state = model.step(state)
            self.assertTrue(math.isfinite(state.phi_rad))
            self.assertTrue(math.isfinite(state.omega_rad_s))
        self.assertLess(abs(state.phi_rad), initial_abs_angle)

    def test_undamped_free_period_is_close_to_natural_period(self):
        period_s = 8.0
        model = self.make_model(period_s=period_s, damping=0.0)
        state = RollState(0.0, 1.0, 0.0)
        previous = state
        upward_crossings = []
        for _ in range(int(4 * period_s / model.dt_s) + 10):
            state = model.step(state)
            if previous.phi_rad < 0.0 <= state.phi_rad:
                fraction = -previous.phi_rad / (state.phi_rad - previous.phi_rad)
                crossing_s = previous.timestamp_s + fraction * model.dt_s
                upward_crossings.append(crossing_s)
            previous = state
        measured_periods = [b - a for a, b in zip(upward_crossings, upward_crossings[1:])]
        self.assertGreaterEqual(len(measured_periods), 3)
        for measured in measured_periods:
            self.assertAlmostEqual(measured, period_s, delta=0.02)

    def test_constant_heel_offset_moves_toward_static_equilibrium(self):
        model = self.make_model(damping=0.3, kappa=0.0)
        heel_rad = 0.1
        state = RollState(0.0, 0.0, 0.0)
        for _ in range(int(80.0 / model.dt_s)):
            state = model.step(state, heel_offset_rad=heel_rad)
            self.assertTrue(math.isfinite(state.phi_rad))
            self.assertTrue(math.isfinite(state.omega_rad_s))
        self.assertAlmostEqual(state.phi_rad, heel_rad, delta=0.002)
        self.assertAlmostEqual(state.omega_rad_s, 0.0, delta=0.002)

    def test_step_uses_semi_implicit_euler_and_default_dt(self):
        model = self.make_model(period_s=10.0, damping=0.08, kappa=0.25)
        initial = RollState(0.3, -0.2, 0.7)
        acceleration = model.angular_acceleration(
            initial,
            wave_excitation_rad=0.02,
            heel_offset_rad=0.04,
            parametric_excitation_amplitude=0.15,
            excitation_angular_frequency_rad_s=2.0,
        )
        expected_omega = initial.omega_rad_s + acceleration * model.dt_s
        expected_phi = initial.phi_rad + expected_omega * model.dt_s
        actual = model.step(
            initial,
            wave_excitation_rad=0.02,
            heel_offset_rad=0.04,
            parametric_excitation_amplitude=0.15,
            excitation_angular_frequency_rad_s=2.0,
        )
        self.assertAlmostEqual(actual.omega_rad_s, expected_omega, places=14)
        self.assertAlmostEqual(actual.phi_rad, expected_phi, places=14)
        self.assertAlmostEqual(actual.timestamp_s, initial.timestamp_s + 0.05)

    def test_angular_acceleration_matches_rearranged_roll_equation(self):
        period_s = 8.0
        damping = 0.1
        kappa = 0.4
        model = self.make_model(period_s=period_s, damping=damping, kappa=kappa)
        state = RollState(phi_rad=0.2, omega_rad_s=0.3, timestamp_s=0.5)
        heel = 0.05
        wave = 0.01
        h = 0.2
        excitation_omega = 2.0
        omega0 = 2.0 * math.pi / period_s
        expected = (
            omega0 ** 2 * (heel + wave)
            - 2.0 * damping * omega0 * state.omega_rad_s
            - omega0 ** 2 * (1.0 + h * math.cos(excitation_omega * state.timestamp_s))
            * state.phi_rad
            - omega0 ** 2 * kappa * state.phi_rad ** 3
        )
        actual = model.angular_acceleration(
            state,
            wave_excitation_rad=wave,
            heel_offset_rad=heel,
            parametric_excitation_amplitude=h,
            excitation_angular_frequency_rad_s=excitation_omega,
        )
        self.assertAlmostEqual(actual, expected, places=14)

    def test_invalid_nonfinite_values_and_missing_frequency_are_rejected(self):
        with self.assertRaises(ValueError):
            RollState(float("nan"), 0.0, 0.0)
        with self.assertRaises(ValueError):
            self.make_model().step(RollState(0.0, 0.0, 0.0), dt_s=float("inf"))
        with self.assertRaises(ValueError):
            self.make_model().step(RollState(0.0, 0.0, 0.0), dt_s=0.0)
        with self.assertRaises(ValueError):
            self.make_model().step(
                RollState(0.1, 0.0, 0.0),
                parametric_excitation_amplitude=0.2,
            )
        with self.assertRaises(ValueError):
            RollDynamics(RollDynamicsConfig(damping_ratio=0.1))
        with self.assertRaises(ValueError):
            RollDynamics(RollDynamicsConfig(natural_period_s=8.0))

    def test_reference_kappa_uses_25_degrees_converted_to_radians_once(self):
        expected = 1.0 / (math.radians(25.0) ** 2)
        self.assertAlmostEqual(reference_nonlinear_coefficient_rad_minus2(), expected)


if __name__ == "__main__":
    unittest.main()
