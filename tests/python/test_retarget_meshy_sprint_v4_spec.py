from __future__ import annotations

import math
import unittest

from blender.scripts import retarget_meshy_sprint_v4_spec as spec


class RetargetMeshySprintV4SpecTests(unittest.TestCase):
    def test_raw_cycle_is_resampled_to_sixteen_unique_poses_and_exact_seam(self) -> None:
        samples = spec.resample_cycle_frames(0.8, 15.2)

        self.assertEqual(spec.SOURCE_FPS, 30)
        self.assertEqual(spec.SOURCE_LOOP_SECONDS, 0.6)
        self.assertEqual(spec.TARGET_FPS, 24)
        self.assertEqual(spec.TARGET_FRAMES, tuple(range(1, 18)))
        self.assertEqual(len(samples), 17)
        self.assertAlmostEqual(samples[0], 0.8)
        self.assertAlmostEqual(samples[-1], samples[0])
        self.assertEqual(len({round(value, 8) for value in samples[:-1]}), 16)
        self.assertTrue(
            all(first < second for first, second in zip(samples[:-2], samples[1:-1]))
        )
        self.assertAlmostEqual((15.2 - 0.8) / spec.TARGET_FPS, 0.6)

    def test_meshy_positive_x_left_maps_to_target_dot_r(self) -> None:
        mapping = spec.SOURCE_TO_TARGET_BONES

        self.assertEqual(mapping["LeftShoulder"], "shoulder.R")
        self.assertEqual(mapping["LeftArm"], "upper_arm.R")
        self.assertEqual(mapping["LeftForeArm"], "lower_arm.R")
        self.assertEqual(mapping["LeftHand"], "hand.R")
        self.assertEqual(mapping["LeftUpLeg"], "upper_leg.R")
        self.assertEqual(mapping["LeftLeg"], "lower_leg.R")
        self.assertEqual(mapping["LeftFoot"], "foot.R")
        self.assertEqual(mapping["LeftToeBase"], "toe.R")

        self.assertEqual(mapping["RightShoulder"], "shoulder.L")
        self.assertEqual(mapping["RightArm"], "upper_arm.L")
        self.assertEqual(mapping["RightForeArm"], "lower_arm.L")
        self.assertEqual(mapping["RightHand"], "hand.L")
        self.assertEqual(mapping["RightUpLeg"], "upper_leg.L")
        self.assertEqual(mapping["RightLeg"], "lower_leg.L")
        self.assertEqual(mapping["RightFoot"], "foot.L")
        self.assertEqual(mapping["RightToeBase"], "toe.L")

    def test_torso_lean_is_damped_into_sanic_sprint_band(self) -> None:
        self.assertAlmostEqual(spec.target_torso_lean_degrees(22.0), 12.1)
        self.assertAlmostEqual(spec.target_torso_lean_degrees(24.0), 13.2)
        self.assertEqual(spec.target_torso_lean_degrees(1.0), 11.0)
        self.assertEqual(spec.target_torso_lean_degrees(90.0), 14.0)

    def test_joint_angle_guards_match_animation_contract(self) -> None:
        self.assertEqual(spec.clamp_elbow_angle_degrees(40.0), 75.0)
        self.assertEqual(spec.clamp_elbow_angle_degrees(90.0), 90.0)
        self.assertEqual(spec.clamp_elbow_angle_degrees(150.0), 105.0)
        self.assertEqual(spec.ensure_knee_flex_degrees(2.0), 15.0)
        self.assertEqual(spec.ensure_knee_flex_degrees(85.0), 85.0)

    def test_lateral_damping_preserves_normalized_sagittal_motion(self) -> None:
        damped = spec.damp_lateral_direction((0.8, -0.4, -0.4))

        self.assertAlmostEqual(math.sqrt(sum(value * value for value in damped)), 1.0)
        self.assertLess(abs(damped[0]), 0.8)
        self.assertLess(damped[1], 0.0)
        self.assertLess(damped[2], 0.0)

    def test_root_translation_contract_discards_horizontal_channels(self) -> None:
        self.assertEqual(spec.vertical_root_offset((2.5, -7.0, 0.035)), (0.0, 0.0, 0.035))

    def test_shoulders_are_active_first_stage_of_arm_retarget(self) -> None:
        self.assertEqual(
            spec.ARM_RETARGET_ORDER,
            ("shoulder", "upper_arm", "lower_arm", "hand"),
        )
        self.assertEqual(
            spec.SHOULDER_DELTA_JOINTS,
            {
                "R": ("LeftShoulder", "LeftArm"),
                "L": ("RightShoulder", "RightArm"),
            },
        )
        self.assertGreater(spec.SHOULDER_RETARGET_DAMPING, 0.0)
        self.assertLess(spec.SHOULDER_RETARGET_DAMPING, 0.5)

    def test_only_run_is_shifted_to_zero_for_glb_export(self) -> None:
        self.assertEqual(spec.RUN_EXPORT_FRAME_OFFSET, -1.0)
        self.assertEqual(
            spec.EXPECTED_EXPORTED_ACTION_RANGES,
            {
                "Crash": (1, 36),
                "Idle": (1, 60),
                "Jump": (1, 30),
                "Run": (0, 16),
            },
        )

    def test_foot_guard_keeps_shoe_forward_and_in_natural_pitch_band(self) -> None:
        guarded = spec.guard_foot_direction((0.25, 0.55, -0.80))
        pitch = math.degrees(math.atan2(guarded[2], -guarded[1]))

        self.assertAlmostEqual(
            math.sqrt(sum(value * value for value in guarded)),
            1.0,
        )
        self.assertLess(guarded[1], 0.0)
        self.assertGreaterEqual(pitch, spec.MIN_FOOT_PITCH_DEGREES)
        self.assertLessEqual(pitch, spec.MAX_FOOT_PITCH_DEGREES)
        self.assertLessEqual(abs(guarded[0]), spec.MAX_FOOT_LATERAL_COMPONENT)


if __name__ == "__main__":
    unittest.main()
