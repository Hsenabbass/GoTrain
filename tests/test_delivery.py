"""CPU package-contract fixtures; untrained weights are never published as real results."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import test_m4 as task_fixture


@unittest.skipUnless(sys.platform=='linux' and Path('/home/sagemaker-user/GoTrain').is_dir(),'Run ML contract checks on SageMaker')
class DeliveryTests(unittest.TestCase):
    def setUp(self):
        import torch
        from gotrain.models import build_model
        from gotrain.requests import atomic_json
        from gotrain.prediction import digest
        self.fixture=task_fixture.M4RunnerTests(); self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.root,self.runner=self.fixture.root,self.fixture.runner
        record=self.fixture.saved_run('untrained_cpu_fixture')
        record['recipe']=self.runner.recipe('resnet18','final',{'epochs':1,'steps':1})
        record['source_commit']='EXPLICIT_UNTRAINED_CPU_CONTRACT_FIXTURE'
        model=build_model('resnet18',self.runner.spec)
        meta={'recipe':record['recipe'],'seed':2026,'task_spec':self.runner.spec,
              'normalization':{'fitted_on':'train','samples':4,'mean':[.2]*3,'std':[.1]*3},
              'validation':record['best_validation'],'contract_sha256':self.runner.contract_hash}
        path=self.root/'artifacts/runs/untrained_cpu_fixture/best.pt'
        torch.save({'model':model.state_dict(),'optimizer':{},'meta':meta},path)
        record['checkpoint_sha256']=digest(path)
        atomic_json(path.parent/'record.json',record)
        self.runner.select(record['run_id'])
        self.fixture.lease.check_time=lambda *_:None
        import time
        self.fixture.lease.clock=time.monotonic
        self.controller=SimpleNamespace(runner=self.runner,lease=self.fixture.lease,state={'decisions':[{'reason':'Untrained CPU contract fixture only'}]})

    def test_export_matches_origin_offline_and_repeat_reuses_version(self):
        from gotrain.delivery import finalize,model_record,package_path
        first=finalize(self.root,self.controller)
        self.assertTrue(first['verification']['passed'])
        self.assertTrue(first['verification']['class_ids_exact'])
        self.assertTrue(first['verification']['network_checkout_cache_denied'])
        second=finalize(self.root,self.controller)
        self.assertEqual((first['version'],first['sha256']),(second['version'],second['sha256']))
        self.assertEqual(len(list((self.root/'artifacts/models').glob('*.zip'))),1)
        self.assertEqual(model_record(self.root,first['version'])['run_id'],'untrained_cpu_fixture')
        self.assertTrue(package_path(self.root,first['version']).is_file())

    def test_prediction_requires_compatible_input_and_returns_probabilities(self):
        from gotrain.delivery import finalize,predict
        from gotrain.requests import read_json
        receipt=finalize(self.root,self.controller)
        output=self.root/'result'
        predict(self.root,receipt['version'],output,example=True)
        result=read_json(output/'result.json')
        self.assertEqual(len(result['probabilities']),2)
        self.assertAlmostEqual(sum(result['probabilities']),1.,places=5)
        self.assertFalse(result['probabilities_calibrated'])
        with self.assertRaises(ValueError):
            predict(self.root,receipt['version'],self.root/'bad-result',image=self.fixture.folder/'valid0.png',declaration={'band_names':['B','G','R'],'input_divisors':[255]*3})
        self.assertFalse((self.root/'bad-result').exists())

    def test_failed_verification_preserves_selection_and_publishes_nothing(self):
        from gotrain.delivery import finalize,registry
        with patch('gotrain.delivery.subprocess.run',return_value=SimpleNamespace(returncode=1,stderr='Explicit failed verification fixture',stdout='')):
            with self.assertRaisesRegex(RuntimeError,'verification failed'): finalize(self.root,self.controller)
        self.assertEqual(registry(self.root),{})
        self.assertEqual(self.runner.best,'untrained_cpu_fixture')

    def test_download_history_are_read_only_and_versions_are_allowlisted(self):
        from fastapi.testclient import TestClient
        from gotrain.delivery import finalize
        from gotrain.requests import Requests,read_json
        from gotrain.service import create_app
        from gotrain.jobs import Jobs
        receipt=finalize(self.root,self.controller)
        store=Requests(self.root/'artifacts/service',read_json(self.root/'configs/service.json'),{})
        app=create_app(store,jobs=Jobs(self.root,store))
        before=(self.root/'artifacts/models/registry.json').read_bytes()
        with patch('gotrain.service.ROOT',self.root),TestClient(app) as client:
            self.assertEqual(len(client.get('/api/models').json()),1)
            self.assertEqual(client.get('/api/models/'+receipt['version']+'/download').status_code,200)
            self.assertEqual(len(client.get('/api/models/'+receipt['version']+'/history').json()['experiments']),1)
            self.assertEqual(client.get('/api/models/not-a-version/download').status_code,404)
        self.assertEqual((self.root/'artifacts/models/registry.json').read_bytes(),before)


if __name__=='__main__': unittest.main()
