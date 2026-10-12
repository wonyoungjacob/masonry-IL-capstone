"""Tests for the new observation boundary and failure behavior, no GL needed."""
import unittest
from types import SimpleNamespace
import numpy as np
from strict_camera_only import (
    CameraTracks, CameraWorld, CameraGate, ObservationUnavailable,
    ForbiddenTruthRead, SensorBackend, cfg_paper, without_audit,
)


def detection(x, y=0., ambiguous=False):
    return {"pos": np.array([x, y, .0135]), "quat": np.array([1., 0., 0., 0.]),
            "yaw": 0., "full": True, "ambiguous": ambiguous}


class FakeEstimator:
    def __init__(self):
        self.env = SimpleNamespace(t=0)
        self.ds = [detection(.2), detection(.0), detection(.1)]

    def detect(self):
        return self.ds


class CameraBoundaryTests(unittest.TestCase):
    def test_camera_identity_survives_detection_order_permutation(self):
        est = FakeEstimator()
        tracks = CameraTracks(est)
        tracks.update()
        np.testing.assert_allclose(tracks.pose(0)[0], [0, 0, .0135])
        est.env.t += 1
        est.ds = [detection(.103), detection(.201), detection(.002)]
        np.testing.assert_allclose(tracks.pose(0)[0], [.002, 0, .0135])
        np.testing.assert_allclose(tracks.pose(2)[0], [.201, 0, .0135])

    def test_missing_detection_never_returns_cached_position(self):
        est = FakeEstimator()
        tracks = CameraTracks(est)
        tracks.update()
        est.env.t += 1
        est.ds = [detection(.1), detection(.2)]
        with self.assertRaises(ObservationUnavailable):
            tracks.pose(0)
        self.assertIn(0, tracks.last)     # association history exists but is not returned

    def test_distant_detection_is_not_silently_relabelled(self):
        est = FakeEstimator()
        tracks = CameraTracks(est)
        tracks.update()
        est.env.t += 1
        est.ds = [detection(.04), detection(.1), detection(.2)]
        with self.assertRaises(ObservationUnavailable):
            tracks.pose(0)

    def test_ambiguous_initial_image_stops(self):
        est = FakeEstimator()
        est.ds[0]["ambiguous"] = True
        with self.assertRaises(ObservationUnavailable):
            CameraTracks(est).update()

    def test_raw_truth_guard_and_sanitized_robot_state(self):
        b = SensorBackend(50000)
        try:
            w = CameraWorld(b)
            with self.assertRaises(ForbiddenTruthRead):
                b.raw.brick_pose(0)
            with self.assertRaises(ForbiddenTruthRead):
                w.env_state()
            with self.assertRaises(ForbiddenTruthRead):
                w.grasped(0)
            with self.assertRaises(AttributeError):
                _ = w.data.mocap_pos
            for adr in b.raw.brick_qadr:
                np.testing.assert_equal(w.data.qpos[adr:adr+7], [0, 0, 0, 1, 0, 0, 0])
            np.testing.assert_equal(w.data.qpos[w.arm_qidx], b.raw.data.qpos[w.arm_qidx])
            b.forbidden.clear()
            b.step(b.raw.data.ctrl[b.raw.act_ids].copy())
            self.assertEqual(b.forbidden, [])
            self.assertNotIn("env_state", b.physics_calls)
        finally:
            b.close()

    def test_slot_bookkeeping_uses_camera_not_sim_identity(self):
        b = SensorBackend(50000)
        try:
            w = CameraWorld(b)
            target = w.design[1][:3]
            w.tracks = SimpleNamespace(pose=lambda i: (np.array(target), np.array([1, 0, 0, 0])))
            self.assertEqual(w.brick_in_slot(0), 1)
            g = CameraGate(w, None, True)
            self.assertEqual(g._score(0, 1)["exy_mm"], 0.)
            self.assertEqual(g._sim_grasped(), None)
            self.assertEqual(b.forbidden, [])
        finally:
            b.close()

    def test_truth_audit_keys_removed_recursively(self):
        self.assertEqual(without_audit({"x": [{"sim_grasped": None, "held": True}]}), {"x": [{"held": True}]})


if __name__ == "__main__":
    unittest.main(verbosity=2)
