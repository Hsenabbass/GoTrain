"""Linux CPU admission/accounting checks. No workers, model calls or GPU work."""
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from gotrain.admission import Admission
from gotrain.requests import Requests, RequestError, atomic_json, read_json


@unittest.skipUnless(sys.platform == 'linux', 'Shared GPU lock is verified on SageMaker Linux')
class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.caps = read_json(ROOT / 'configs/service.json')
        self.caps['training_enabled'] = True  # Isolated fixture only, never live config.
        self.policy = read_json(ROOT / 'configs/m4.json')
        self.clock = 100.
        self.now = datetime(2026, 11, 1, 0, 0, tzinfo=timezone.utc)
        self.disk = patch('gotrain.admission.shutil.disk_usage', return_value=type('Disk', (), {'free': 100*2**30})())
        self.disk.start()
        self.addCleanup(self.disk.stop)
        data = {'id': 'dataset_'+'a'*32, 'status': 'validated', 'sha256': 'fixture-version',
                'task': {'kind': 'classification'}, 'counts': {'train': 4, 'valid': 2}}
        self.store = Requests(self.root/'artifacts/service', self.caps, {data['id']: data})
        limits = self.store.validate_limits({})
        self.record = {'id': 'conversation_'+'b'*32, 'status': 'ready_for_review', 'questions': [],
                       'dataset_id': data['id'], 'goal': 'Classify fixture labels', 'messages': [{'role': 'user', 'content': 'Classify fixture labels'}],
                       'limits': limits, 'proposed_limits': limits.copy(), 'preflight_requests': 2, 'model_requests': 2,
                       'summary': {'dataset_id': data['id'], 'dataset_version': data['sha256'], 'task': data['task'], 'counts': data['counts'],
                                   'goal': 'Classify fixture labels', 'limits': limits.copy(), 'validation_only': True}}
        self.store.save(self.record)
        self.key = 'request_'+'c'*32

    def admission(self, policy=None):
        return Admission(self.root, policy or self.policy, clock=lambda: self.clock, now=lambda: self.now)

    def admit(self, lease):
        return lease.admit(self.store, self.record['id'], self.key)

    def test_freezes_request_and_preserves_preflight_charges(self):
        with self.admission() as lease:
            job = self.admit(lease)
            self.record['messages'][0]['content'] = 'changed'
            self.store.save(self.record)
            self.assertEqual(job['model_requests'], 2)
            self.assertEqual(job['frozen']['messages'][0]['content'], 'Classify fixture labels')
            lease.charge_model_request()
            self.assertEqual(read_json(lease.path)['jobs'][job['id']]['model_requests'], 3)
            lease.finish('failed')

    def test_duplicate_after_settlement_never_readmits(self):
        with self.admission() as lease:
            original = self.admit(lease)
            lease.finish('stopped')
        with self.admission() as lease:
            with self.assertRaisesRegex(RequestError, original['id']):
                self.admit(lease)
        self.assertEqual(len(read_json(lease.path)['jobs']), 1)

    def test_shared_lock_excludes_another_process(self):
        with self.admission() as lease:
            self.admit(lease)
            code = "import fcntl,sys; f=open(sys.argv[1],'a'); fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)"
            result = subprocess.run([sys.executable, '-c', code, str(self.root/'artifacts/m1.lock')], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            lease.finish('stopped')

    def test_interruption_keeps_trial_reservation_and_blocks_legacy(self):
        with self.admission() as lease:
            self.admit(lease)
            lease.reserve_trial('screen', 150)
        ledger = read_json(lease.path)
        self.assertEqual(ledger['charged_seconds'], 150)
        from gotrain.runtime import Budget
        with self.assertRaisesRegex(RuntimeError, 'Unsettled'):
            Budget(self.root, {}, 0)
        with self.admission() as lease:
            self.record['id'] = 'conversation_'+'d'*32
            self.store.save(self.record)
            with self.assertRaisesRegex(RequestError, 'interrupted'):
                lease.admit(self.store, self.record['id'], 'request_'+'e'*32)
        self.assertEqual(read_json(lease.path)['charged_seconds'], 150)

    def test_legacy_lock_blocks_m4(self):
        from gotrain.runtime import Budget
        legacy = Budget(self.root, {}, 0)
        try:
            with self.assertRaisesRegex(RequestError, 'shared GPU lock'):
                with self.admission(): pass
        finally:
            legacy.close()

    def test_historical_reservation_blocks_m4_and_is_unchanged(self):
        for allocation in ('m1', 'm2', 'm3'):
            path = self.root/('artifacts/'+allocation+'-budget.json')
            atomic_json(path, {'active': {'run_id': 'old'}, 'charged_seconds': 17})
            before = path.read_bytes()
            with self.admission() as lease:
                with self.assertRaisesRegex(RequestError, allocation):
                    self.admit(lease)
            self.assertEqual(path.read_bytes(), before)
            atomic_json(path, {'active': None, 'charged_seconds': 17})

    def test_disabled_unresolved_changed_and_infeasible_launch_nothing(self):
        variants = []
        changed = copy.deepcopy(self.record); changed['status'] = 'needs_input'; variants.append(changed)
        changed = copy.deepcopy(self.record); changed['summary']['dataset_version'] = 'changed'; variants.append(changed)
        changed = copy.deepcopy(self.record); changed['model_requests'] = 23; variants.append(changed)
        changed = copy.deepcopy(self.record)
        changed['proposed_limits']['gpu_seconds'] = changed['summary']['limits']['gpu_seconds'] = 600
        variants.append(changed)
        for changed in variants:
            self.store.save(changed)
            with self.admission() as lease:
                with self.assertRaises(RequestError): self.admit(lease)
            self.assertFalse(lease.path.exists())
        self.store.save(self.record)
        self.store.caps['training_enabled'] = False
        with self.admission() as lease:
            with self.assertRaisesRegex(RequestError, 'disabled'): self.admit(lease)
        self.assertFalse(lease.path.exists())

    def test_global_budget_reduces_ceiling_or_rejects(self):
        with self.admission() as lease:
            ledger = lease.ledger(); ledger['charged_seconds'] = 2900; atomic_json(lease.path, ledger)
            job = self.admit(lease)
            self.assertEqual(job['gpu_seconds'], 700)
            with self.assertRaisesRegex(RequestError, 'reserve'): lease.reserve_trial('screen', 150)
            lease.finish('failed')
        with self.admission() as lease:
            ledger = lease.ledger(); ledger['jobs'] = {}; ledger['charged_seconds'] = 3000; atomic_json(lease.path, ledger)
            with self.assertRaisesRegex(RequestError, 'Insufficient'): self.admit(lease)

    def test_trial_reserves_finalization_attempt_and_model_caps(self):
        with self.admission() as lease:
            job = self.admit(lease)
            with self.assertRaisesRegex(RequestError, 'reserve'): lease.reserve_trial('tune', 300)
            trial = lease.reserve_trial('screen', 150)
            with self.assertRaises(RequestError): lease.reserve_trial('screen', 150)
            self.clock += 100
            lease.settle_trial(trial['id'], 'completed')
            self.assertEqual(read_json(lease.path)['charged_seconds'], 100)
            with self.assertRaises(RequestError): lease.settle_trial(trial['id'], 'completed')
            for _ in range(22): lease.charge_model_request()
            with self.assertRaisesRegex(RequestError, 'request allowance'): lease.charge_model_request()
            # Remaining runtime must preserve current trial, verification and packaging.
            self.clock += 500
            with self.assertRaisesRegex(RequestError, 'runtime/reserve'): lease.reserve_trial('final', 600)
            lease.finish('failed')

    def test_attempt_reserve_and_overrun_fail_closed(self):
        self.record['limits']['attempts'] = 1
        self.record['proposed_limits']['attempts'] = self.record['summary']['limits']['attempts'] = 1
        self.store.save(self.record)
        with self.admission() as lease:
            self.admit(lease)
            with self.assertRaisesRegex(RequestError, 'Attempt'): lease.reserve_trial('probe', 30)
            trial = lease.reserve_trial('final', 600)
            self.clock += 601
            lease.settle_trial(trial['id'], 'failed')
            self.assertEqual(read_json(lease.path)['charged_seconds'], 601)
            with self.assertRaises(RequestError): lease.reserve_trial('verify', 60)
            with self.assertRaises(RequestError): lease.finish('completed')
            lease.finish('failed')

    def test_deadline_disk_and_changed_policy_block(self):
        self.now = datetime(2026, 11, 1, 10, 50, tzinfo=timezone.utc)
        with self.admission() as lease:
            with self.assertRaisesRegex(RequestError, 'Submission'): self.admit(lease)
        self.now = datetime(2026, 11, 1, 0, 0, tzinfo=timezone.utc)
        with patch('gotrain.admission.shutil.disk_usage', return_value=type('Disk', (), {'free': 0})()):
            with self.admission() as lease:
                with self.assertRaisesRegex(RequestError, 'Disk'): self.admit(lease)
        with self.admission() as lease:
            self.admit(lease); lease.finish('failed')
        policy = copy.deepcopy(self.policy); policy['gpu_job_seconds'] = 9999
        with self.admission(policy) as lease:
            with self.assertRaisesRegex(RequestError, 'policy changed'): lease.ledger()


if __name__ == '__main__':
    unittest.main()
