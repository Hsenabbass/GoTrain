"""Focused M2 boundaries; run on SageMaker, no training or Bedrock calls."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from gotrain import agent
from gotrain.runtime import Budget, write_json
from gotrain.training import read, digest


class AgentChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'configs').mkdir()
        (self.root / 'docs').mkdir()
        (self.root / 'artifacts/runs').mkdir(parents=True)
        for file in ('configs/m2.json', 'configs/tasks.json', 'configs/reference-m-eurosat.json', 'docs/m1-evidence.json'):
            (self.root / file).write_bytes((agent.ROOT / file).read_bytes())
        self.mock = patch.object(agent, 'ROOT', self.root); self.mock.start()
        self.c = agent.Controller(self.root / 'session')
        self.reference = read(self.root / 'docs/m1-evidence.json')['classification']['results'][0]['record']
        self.add_run(self.c.state['best'], .87)

    def tearDown(self):
        self.mock.stop(); self.tmp.cleanup()

    def add_run(self, name, score):
        r = copy.deepcopy(self.reference)
        r.update(run_id=name, status='completed', checkpoint='best.pt')
        r['best_validation']['primary'] = score
        folder = self.root / 'artifacts/runs' / name; folder.mkdir()
        (folder / 'best.pt').write_bytes(b'checkpoint')
        r['checkpoint_sha256'] = digest(folder / 'best.pt')
        write_json(folder / 'record.json', r)
        return r

    def test_field_and_id_rejection(self):
        for field in ('split', 'task', 'data_root', 'model', 'smoke', 'valid_limit'):
            with self.assertRaises(ValueError):
                self.c.train_candidate({field: 'test'}, 'bad', self.c.state['best'])
        for value in ('../../configs/tasks', '/etc/passwd', 'test'):
            with self.assertRaises(ValueError): self.c.record(value)

    def test_best_selection_and_integrity(self):
        original = self.c.state['best']
        for name, score in [('worse', .8), ('tie', .87), ('better', .9)]:
            self.add_run(name, score); self.c.state['runs'].append(name)
            self.c.select_candidate(name, 'evidence')
            self.assertEqual(self.c.state['best'], 'better' if name == 'better' else original)
        (self.root / 'artifacts/runs/better/best.pt').write_bytes(b'corrupt')
        with self.assertRaises(ValueError): self.c.select_candidate('better', 'bad')

    def test_failed_and_partial_never_selected(self):
        r = self.add_run('failed', .99); self.c.state['runs'].append('failed')
        for key, value in [('status', 'failed'), ('eligible_reference', False)]:
            changed = {**r, key: value};write_json(self.root / 'artifacts/runs/failed/record.json', changed)
            with self.assertRaises(ValueError): self.c.select_candidate('failed', 'bad')
        self.assertEqual(self.c.state['best'], self.reference['run_id'])

    def test_call_and_wall_bounds(self):
        self.c.state['tool_calls'] = 20
        with self.assertRaises(RuntimeError): self.c.invoke('inspect_task')
        self.c.state['model_requests'] = 12
        with self.assertRaises(RuntimeError): self.c.bound('model_requests')
        self.c.started = time.monotonic() - 1801
        with self.assertRaises(RuntimeError): self.c.verify_prediction(self.c.state['best'])

    def test_separate_budget_and_shared_lock(self):
        old = {'active': None, 'charged_seconds': 2044.41}
        write_json(self.root / 'artifacts/m1-budget.json', old)
        caps = self.c.caps
        b = Budget(self.root, caps, 0, 'm2')
        try:
            self.assertEqual(b.ledger['charged_seconds'], 0)
            with self.assertRaises(RuntimeError): Budget(self.root, caps, 0, 'm1')
            b.begin('check', 'four_reference_runs', 600);b.finish('failed')
            b.ledger['runs'].append({'category': 'four_reference_runs'})
            with self.assertRaises(RuntimeError):b.begin('third', 'four_reference_runs', 600)
        finally:b.close()
        self.assertEqual(read(self.root / 'artifacts/m1-budget.json'), old)

    def test_retry_and_recipe_caps(self):
        with self.assertRaises(ValueError):self.c.train_candidate({'epochs': 11}, 'bad', self.c.state['best'])
        self.c.state['attempts'] = 2
        with self.assertRaises(ValueError):self.c.train_candidate({}, 'third', self.c.state['best'])
        with self.assertRaises(ValueError):self.c.train_candidate({}, 'retry', self.c.state['best'], self.c.state['best'])

    def test_strands_schema(self):
        from strands import tool
        for name in ('inspect_task', 'train_candidate', 'read_result', 'verify_prediction', 'select_candidate'):
            wrapped = tool(getattr(self.c, name))
            self.assertTrue(wrapped.tool_spec['inputSchema'])
