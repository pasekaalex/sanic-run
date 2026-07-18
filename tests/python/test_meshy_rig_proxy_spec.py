from __future__ import annotations

import importlib
import unittest


class MeshyRigProxySpecTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.proxy = importlib.import_module(
                "blender.scripts.meshy_rig_proxy_spec"
            )
        except ModuleNotFoundError:
            cls.proxy = None

    def require_proxy(self):
        self.assertIsNotNone(
            self.proxy,
            "clean Meshy A-pose proxy specification is not implemented",
        )
        return self.proxy

    def test_proxy_uses_human_scale_and_gltf_forward_contract(self) -> None:
        proxy = self.require_proxy()

        self.assertEqual(proxy.HEIGHT_METERS, 1.7)
        self.assertEqual(proxy.BOUNDS_MINIMUM_Z, 0.0)
        self.assertEqual(proxy.BLENDER_FORWARD, (0.0, -1.0, 0.0))

    def test_a_pose_is_mirrored_with_clear_arm_separation(self) -> None:
        proxy = self.require_proxy()
        landmarks = proxy.LANDMARKS

        for left_name, right_name in (
            ("shoulder.L", "shoulder.R"),
            ("elbow.L", "elbow.R"),
            ("wrist.L", "wrist.R"),
            ("hand.L", "hand.R"),
            ("hip.L", "hip.R"),
            ("knee.L", "knee.R"),
            ("ankle.L", "ankle.R"),
        ):
            left = landmarks[left_name]
            right = landmarks[right_name]
            self.assertAlmostEqual(left[0], -right[0])
            self.assertAlmostEqual(left[1], right[1])
            self.assertAlmostEqual(left[2], right[2])

        shoulder = landmarks["shoulder.R"]
        elbow = landmarks["elbow.R"]
        wrist = landmarks["wrist.R"]
        hand = landmarks["hand.R"]
        self.assertGreater(hand[0], 0.72)
        self.assertGreater(shoulder[2], elbow[2])
        self.assertGreater(elbow[2], wrist[2])
        self.assertGreaterEqual(wrist[2], hand[2])
        self.assertGreater(hand[0] - shoulder[0], 0.50)

    def test_proxy_has_unambiguous_face_and_forward_feet(self) -> None:
        proxy = self.require_proxy()
        landmarks = proxy.LANDMARKS

        self.assertLess(landmarks["nose"][1], landmarks["head"][1])
        self.assertLess(landmarks["toe.L"][1], landmarks["ankle.L"][1])
        self.assertLess(landmarks["toe.R"][1], landmarks["ankle.R"][1])
        self.assertAlmostEqual(
            landmarks["nose"][0],
            0.0,
        )

    def test_geometry_is_named_textured_and_detector_friendly(self) -> None:
        proxy = self.require_proxy()
        parts = proxy.proxy_parts()
        names = [part.name for part in parts]

        self.assertEqual(len(names), len(set(names)))
        self.assertGreaterEqual(len(parts), 18)
        for required in (
            "Proxy_Head",
            "Proxy_Torso",
            "Proxy_Pelvis",
            "Proxy_UpperArm.L",
            "Proxy_UpperArm.R",
            "Proxy_LowerLeg.L",
            "Proxy_LowerLeg.R",
            "Proxy_Hand.L",
            "Proxy_Hand.R",
            "Proxy_Foot.L",
            "Proxy_Foot.R",
            "Proxy_Nose",
        ):
            self.assertIn(required, names)

        allowed_materials = set(proxy.MATERIAL_COLORS)
        self.assertTrue(allowed_materials)
        self.assertTrue(
            all(part.material in allowed_materials for part in parts)
        )


if __name__ == "__main__":
    unittest.main()
