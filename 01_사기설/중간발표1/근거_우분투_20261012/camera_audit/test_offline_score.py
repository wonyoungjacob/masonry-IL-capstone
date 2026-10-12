"""Known-error fixtures: mm units, missing tracks, and identity changes."""
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
import score_camera_audit as scorer


class OfflineScoreTests(unittest.TestCase):
    def fixture(self, root, switched=False):
        cfg=scorer.cfg_paper()
        xyz=np.array([s[:3] for s in scorer.design_poses(cfg,cfg.brick)])
        poses=np.column_stack([xyz,np.tile([1.,0.,0.,0.],(3,1))]).tolist()
        dets=[dict(pos=(x+np.array([.001,0.,0.])).tolist(),quat=[1,0,0,0],yaw=0.,tilt_deg=0.,full=True,ambiguous=False) for x in xyz]
        predictions=[]; refs=[]
        for step in [0,5]:
            tracks={str(i):d for i,d in enumerate(dets)}
            if step==5:
                if switched:tracks['0'],tracks['1']=tracks['1'],tracks['0']
                else:tracks.pop('1')
            key=f'50000:{step}'
            predictions.append(dict(key=key,step=step,seed=50000,detections=dets,tracks=tracks))
            refs.append(dict(key=key,poses=poses))
        for suffix,rows in [('predictions',predictions),('references',refs),('queries',[])]:
            (root/f'fixture_s50000_{suffix}.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
        return dict(config=dict(name='fixture'),episodes=[dict(seed=50000,audit_reference_frames=2,
                    controller_forbidden_truth_reads=[],status='completed',steps=5)])

    def test_known_one_mm_error_and_missing_track(self):
        with tempfile.TemporaryDirectory(dir=scorer.P) as temp:
            original=scorer.P; scorer.P=Path(temp)
            try:
                r=scorer.score(self.fixture(scorer.P))
                self.assertAlmostEqual(r['detection_xy_mm']['mean'],1.,places=10)
                self.assertEqual(r['assigned_detections'],6)
                self.assertEqual(r['missing_detection_slots'],0)
                self.assertEqual(r['tracked_observations'],5)
                self.assertEqual(r['track_coverage'],5/6)
            finally:scorer.P=original

    def test_identity_swap_is_not_hidden_by_framewise_matching(self):
        with tempfile.TemporaryDirectory(dir=scorer.P) as temp:
            original=scorer.P; scorer.P=Path(temp)
            try:
                r=scorer.score(self.fixture(scorer.P,switched=True))
                self.assertAlmostEqual(r['detection_xy_mm']['mean'],1.,places=10)
                self.assertEqual(r['wrong_identity_observations'],2)
                self.assertGreater(r['track_xy_fixed_identity_mm']['max'],80.)
            finally:scorer.P=original


if __name__=='__main__':unittest.main(verbosity=2)
