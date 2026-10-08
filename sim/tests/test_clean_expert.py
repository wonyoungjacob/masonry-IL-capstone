"""Behavioral checks for first-grasp-only, single-release collection."""
import unittest

from brick_sim.expert import ScriptedExpert
from brick_sim.scene import BrickEnv, blueprint_config


class CleanExpertTests(unittest.TestCase):
    def setUp(self):
        self.env = BrickEnv(blueprint_config('mortarB', pos_rand=.03, supply_yaw_deg=60, valid_supply=True))
        self.env.reset(4)
        self.expert = ScriptedExpert(self.env, seed=4, max_retries=0, clean_single_pass=True)

    def test_missing_grasp_stops_before_transport(self):
        self.env.grasped = lambda _: False
        self.expert.run_episode()
        self.assertEqual(self.env.t, 50)
        self.assertEqual([e['stage'] for e in self.expert.log], ['grasp'])
        self.assertEqual(len(self.expert.unrecoverable), 1)

    def test_bad_placement_is_not_regrasped(self):
        def fail(_):
            self.expert.last_err = {}
            return False, 'test_offset'
        self.expert.placement_ok = fail
        self.expert.run_episode()
        self.assertEqual([e['stage'] for e in self.expert.log], ['grasp', 'release'])
        self.assertEqual(self.expert.recoveries, 0)
        self.assertEqual(self.env.t, 122)

    def test_lost_grasp_aborts_carry(self):
        self.env.grasped = lambda _: self.env.t <= 50
        self.expert.run_episode()
        self.assertEqual(self.env.t, 51)
        self.assertEqual([e['stage'] for e in self.expert.log], ['grasp', 'carry'])
        self.assertFalse(self.expert.log[-1]['ok'])

    def test_success_has_exactly_one_grasp_and_release_per_brick(self):
        self.expert.run_episode()
        self.assertEqual(len(self.expert.log), 6)
        self.assertTrue(all(e['ok'] for e in self.expert.log))
        for brick in range(3):
            self.assertEqual([e['stage'] for e in self.expert.log if e['brick'] == brick], ['grasp', 'release'])
        self.assertFalse(self.expert.unrecoverable)
        self.assertEqual(self.expert.recoveries, 0)


if __name__ == '__main__':
    unittest.main()
