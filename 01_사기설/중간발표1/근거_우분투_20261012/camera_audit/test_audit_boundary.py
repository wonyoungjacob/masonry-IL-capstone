"""Check that reference recording cannot change camera outputs or return labels."""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
import numpy as np
from run_camera_audit import OfflineRecorder, AuditedTracks, ROOT


def det(x):
    return dict(pos=np.array([x,0.,.02]),quat=np.array([1.,0.,0.,0.]),yaw=0.,tilt_deg=0.,full=True,ambiguous=False)


class AuditTests(unittest.TestCase):
    def test_prediction_precedes_reference_and_is_invariant(self):
        ds=[det(0.),det(.1),det(.2)]
        estimates=[]
        outputs=[]
        for k,offset in enumerate([0.,1000.]):
            prefix=ROOT/f'boundary_test_{k}'
            class Data:
                @property
                def qpos(self):
                    assert Path(str(prefix)+'_predictions.jsonl').read_text(), 'reference read before prediction'
                    return np.tile(np.r_[offset,0.,0.,1.,0.,0.,0.],3)
            est=SimpleNamespace(env=SimpleNamespace(t=0),detect=lambda:ds)
            b=SimpleNamespace(raw=SimpleNamespace(t=0,data=Data(),brick_qadr=[0,7,14]),estimator=est)
            tracks=AuditedTracks(est); tracks.update()
            rec=OfflineRecorder(b,prefix,50000); tracks.recorder=rec
            try:
                estimates.append(tracks.pose(1))
                self.assertIsNone(rec.record(tracks))
            finally:
                rec.close()
            outputs.append(Path(str(prefix)+'_predictions.jsonl').read_text())
        self.assertEqual(outputs[0],outputs[1])
        for a,b in zip(estimates[0],estimates[1]):np.testing.assert_equal(a,b)
        refs=[json.loads((ROOT/f'boundary_test_{k}_references.jsonl').read_text()) for k in range(2)]
        self.assertNotEqual(refs[0]['poses'],refs[1]['poses'])


if __name__=='__main__':unittest.main(verbosity=2)
