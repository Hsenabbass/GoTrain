"""Meaningful safety/math/persistence checks; execute on SageMaker."""
import copy
from datetime import datetime, timedelta
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from gotrain.data import DevelopmentData, fit_normalization, joint_transform, prepare
from gotrain.metrics import Confusion
from gotrain.runtime import Budget, Guard, validate_recipe
from gotrain.training import checkpoint, run_with_watchdog, main


class FoundationChecks(unittest.TestCase):
    def setUp(self):
        self.caps = json.loads((ROOT / 'configs/m1.json').read_text())
        self.caps['submission_deadline_local'] = (datetime.now() + timedelta(days=2)).isoformat()
        self.contracts = json.loads((ROOT / 'configs/tasks.json').read_text())

    def test_test_split_rejected_before_metadata_import_or_io(self):
        with patch('pathlib.Path.read_bytes', side_effect=AssertionError('File access must not occur')):
            for split in ('test', 'all', None, 'validation'):
                with self.assertRaises(ValueError):
                    DevelopmentData('/not-present', 'm-eurosat', split, self.contracts, {})

    def test_other_checkout_cannot_create_an_independent_gpu_budget(self):
        with patch('gotrain.training.ROOT', Path('/not-the-execution-checkout')):
            with self.assertRaises(RuntimeError): main()

    def test_joint_spatial_transform_keeps_mask_alignment(self):
        x = torch.arange(9).reshape(1, 3, 3).float(); y = x[0].long()
        for turns in range(4):
            a, b = joint_transform(x, y, horizontal=True, turns=turns)
            self.assertTrue(torch.equal(a[0].long(), b))
        self.assertTrue(torch.equal(y, torch.arange(9).reshape(3, 3)))

    def test_fixed_scaling_and_target_validation(self):
        spec = self.contracts['tasks']['m-brick-kiln']
        x = np.zeros((13, 64, 64), dtype=np.float64); x[:10] = 20000; x[10:] = 255
        tensor, y = prepare(x, np.int64(1), spec)
        self.assertEqual(tensor.dtype, torch.float32)
        self.assertTrue(torch.all(tensor[:10] == 2))  # No reflectance clamp.
        self.assertTrue(torch.all(tensor[10:] == 1))
        for target in (np.float32(1), np.int64(2)):
            with self.assertRaises(ValueError): prepare(x, target, spec)
        x[0, 0, 0] = np.nan
        with self.assertRaises(ValueError): prepare(x, np.int64(1), spec)

    def test_fit_uses_train_only_and_known_channel_moments(self):
        class Fixture:
            split, normalization = 'train', None
            def __len__(self): return 2
            def __getitem__(self, i): return torch.tensor([[[1., 3.]]] if i == 0 else [[[5., 7.]]]), torch.tensor(0)
        data = Fixture(); result = fit_normalization(data)
        self.assertAlmostEqual(result['mean'][0], 4)
        self.assertAlmostEqual(result['std'][0], 5**0.5)
        data.split = 'valid'
        with self.assertRaises(ValueError): fit_normalization(data)

    def test_global_metrics_absent_classes_and_batch_invariance(self):
        p, y = torch.tensor([0, 1, 1, 1]), torch.tensor([0, 0, 1, 1])
        m = Confusion(3); m.update(p, y); result = m.compute()
        self.assertAlmostEqual(result['accuracy'], .75)
        self.assertAlmostEqual(result['macro_iou'], 7/12)
        self.assertEqual(result['union'][2], 0)
        split = Confusion(3); split.update(p[:1], y[:1]); split.update(p[1:], y[1:])
        self.assertEqual(split.compute(), result)
        bad = Confusion(3); bad.update(torch.tensor([0, 2, 1, 1]), y)
        self.assertAlmostEqual(bad.compute()['macro_iou'], .5)  # Hallucinated absent class is penalized.
        with self.assertRaises(ValueError): Confusion(3).compute()

    def test_ignored_target_diagnostic_still_penalizes_prediction_zero(self):
        m = Confusion(3, ignore_target=0, exclude_macro=(0,))
        m.update(torch.tensor([2, 0, 2, 1]), torch.tensor([0, 1, 2, 2]))
        result = m.compute()
        self.assertEqual(result['count'], 3)
        self.assertAlmostEqual(result['macro_iou'], .25)
        empty = Confusion(3, ignore_target=0); empty.update(torch.tensor([0]), torch.tensor([0]))
        self.assertIsNone(empty.compute(allow_empty=True)['macro_iou'])

    def test_recipe_caps_and_smoke_only_subsets(self):
        recipe = json.loads((ROOT / 'configs/smoke-classification.json').read_text())
        validate_recipe(recipe, self.contracts, self.caps)
        for change in ({'wall_seconds':601}, {'epochs':11}, {'steps':5001}, {'batch_size':33}, {'smoke':False}, {'lr':float('nan')}):
            with self.assertRaises(ValueError): validate_recipe({**recipe, **change}, self.contracts, self.caps)

    def test_lock_reservation_refund_shared_cap_and_retry_cap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); budget = Budget(root, self.caps, 13)
            with self.assertRaises(RuntimeError): Budget(root, self.caps, 13)
            budget.begin('fixture', 'foundation_smoke', 20, 'original')
            self.assertEqual(budget.ledger['charged_seconds'], 93)
            elapsed = budget.finish('completed')
            self.assertAlmostEqual(budget.ledger['charged_seconds'], 73 + elapsed)
            with self.assertRaises(RuntimeError): budget.begin('retry2', 'foundation_smoke', 20, 'original')
            budget.ledger['charged_seconds'] = 3595
            with self.assertRaises(RuntimeError): budget.begin('over', 'foundation_smoke', 20)
            budget.close()

    def test_wall_disk_storage_and_memory_guards(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); run = root / 'artifacts/runs/check'; run.mkdir(parents=True)
            guard = Guard(root, run, self.caps, 20, clock=lambda:10)
            with self.assertRaises(TimeoutError): guard.check(reserve=10)
            with patch('gotrain.runtime.shutil.disk_usage', return_value=type('Disk', (), {'free':0})()):
                with self.assertRaises(RuntimeError): guard.check()
            caps = copy.deepcopy(self.caps); caps['resources']['per_run_artifact_limit_gib'] = 0
            (run / 'blob').write_text('x')
            with self.assertRaises(RuntimeError): Guard(root, run, caps, 20, clock=lambda:10).check()
            fake = type('Torch', (), {'cuda':type('CUDA', (), {'memory_allocated':staticmethod(lambda:11*2**30), 'memory_reserved':staticmethod(lambda:11*2**30)})})()
            with self.assertRaises(RuntimeError): guard.check(torch_module=fake)

    def test_watchdog_terminates_real_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            start = time.monotonic()
            with self.assertRaises(TimeoutError):
                run_with_watchdog([sys.executable, '-c', 'import time;time.sleep(5)'], .05, Path(tmp) / 'log')
            self.assertLess(time.monotonic() - start, 2)

    def test_failed_atomic_checkpoint_keeps_previous_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'best.pt'; path.write_bytes(b'previous-best')
            model = torch.nn.Linear(1, 1); optimizer = torch.optim.SGD(model.parameters(), lr=.1)
            guard = type('Guard', (), {'check':lambda *a, **kw:None})()
            def fail(value, target):
                Path(target).write_bytes(b'incomplete'); raise OSError('simulated write failure')
            with patch('torch.save', side_effect=fail), self.assertRaises(OSError): checkpoint(path, model, optimizer, {}, guard)
            self.assertEqual(path.read_bytes(), b'previous-best')


if __name__ == '__main__':
    unittest.main(verbosity=2)
