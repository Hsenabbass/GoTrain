"""M4 runner contract/real-image CPU checks on SageMaker; no GPU training."""
import copy
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))


@unittest.skipUnless(Path('/home/sagemaker-user/GoTrain').is_dir() and sys.platform=='linux', 'M4 ML adapter checks run only on SageMaker')
class M4RunnerTests(unittest.TestCase):
    def setUp(self):
        from gotrain.admission import fingerprint
        from gotrain.m4 import M4Runner
        from gotrain.requests import atomic_json
        from PIL import Image
        import numpy as np
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'configs').mkdir()
        (self.root/'docs').mkdir()
        for name in ('tasks.json','m3.json','m4.json','service.json'):
            shutil.copyfile(ROOT/'configs'/name,self.root/'configs'/name)
        for name in ('data-inspection.json','m3-evidence.json'):
            shutil.copyfile(ROOT/'docs'/name,self.root/'docs'/name)
        self.spec = {'kind':'classification','channels':3,'height':32,'width':32,'classes':2,
                     'class_names':['absent','present'],'band_names':['R','G','B'],'rgb_indices':[0,1,2],
                     'input_divisors':[255,255,255],'primary_metric':'accuracy','ignore_index':None}
        self.data = {'id':'dataset_'+'a'*32,'source':'manifest_zip','sha256':'accepted-archive-hash',
                     'status':'validated','task':self.spec,'counts':{'train':4,'valid':2}}
        self.folder = self.root/'artifacts/service/datasets'/self.data['id']; self.folder.mkdir(parents=True)
        rows = {'train':[],'valid':[]}
        for split,values in (('train',[16,32,48,64]),('valid',[255,255])):
            for index,value in enumerate(values):
                name = split+str(index)+'.png'
                Image.fromarray(np.full((32,32,3),value,dtype='uint8')).save(self.folder/name)
                rows[split].append({'image':name,'label':int(index>0) if split=='train' else 0})
        self.manifest = {'task':self.spec,'splits':rows}
        atomic_json(self.folder/'manifest.json',self.manifest); atomic_json(self.folder/'record.json',self.data)
        self.frozen = {'dataset':self.data,'summary':{'goal':'Classify the provided labels'},
                       'limits':{'gpu_seconds':900,'runtime_seconds':1200,'attempts':5,'model_requests':24}}
        self.job = {'id':'job_'+'b'*32,'owner_pid':os.getpid(),'status':'admitted',
                    'frozen':self.frozen,'frozen_sha256':fingerprint(self.frozen),
                    'model_requests':2,'started_monotonic':time.monotonic(),'runtime_seconds':1200}
        self.lease = SimpleNamespace(root=self.root,job_id=self.job['id'],policy=json.loads((self.root/'configs/m4.json').read_text()),owned=lambda:({},self.job))
        self.runner = M4Runner(self.lease)

    def test_custom_adapter_train_only_scaling_stats_and_counts(self):
        from gotrain.m4 import open_frozen
        from gotrain.data import fit_normalization,training_label_counts
        train = open_frozen(self.root,self.frozen,'train')
        valid = open_frozen(self.root,self.frozen,'valid')
        self.assertEqual(training_label_counts(train,2),{'0':1,'1':3})
        norm = fit_normalization(train)
        self.assertAlmostEqual(norm['mean'][0],40/255,places=6)
        self.assertEqual(norm['samples'],4)
        self.assertAlmostEqual(float(valid[0][0].mean()),1.)
        with self.assertRaises(ValueError): fit_normalization(valid)
        with self.assertRaises(ValueError): training_label_counts(valid,2)
        with self.assertRaises(ValueError): open_frozen(self.root,self.frozen,'test')
        self.assertEqual(self.runner.context()['goal'],'Classify the provided labels')
        self.assertTrue(self.runner.context()['baseline_needed'])

    def test_segmentation_masks_use_the_same_adapter(self):
        from gotrain.m4 import open_frozen
        from gotrain.data import training_label_counts
        from gotrain.requests import atomic_json
        import numpy as np
        from PIL import Image
        self.spec.update(kind='segmentation',primary_metric='macro_iou')
        for split,rows in self.manifest['splits'].items():
            for index,row in enumerate(rows):
                label = row.pop('label'); row['mask']=split+str(index)+'-mask.png'
                Image.fromarray(np.full((32,32),label,dtype='uint8')).save(self.folder/row['mask'])
        atomic_json(self.folder/'manifest.json',self.manifest); atomic_json(self.folder/'record.json',self.data)
        train = open_frozen(self.root,self.frozen,'train')
        self.assertEqual(tuple(train[0][1].shape),(32,32))
        self.assertEqual(training_label_counts(train,2),{'0':1024,'1':3072})

    def test_manifest_metadata_change_or_symlink_rejected(self):
        from gotrain.m4 import dataset_contract
        from gotrain.requests import atomic_json
        changed=copy.deepcopy(self.manifest); changed['task']['input_divisors']=[1,1,1]
        atomic_json(self.folder/'manifest.json',changed)
        with self.assertRaisesRegex(ValueError,'metadata'): dataset_contract(self.root,self.frozen)

    def test_recipes_lock_task_seed_time_and_model_compatibility(self):
        recipe = self.runner.recipe('resnet18_imagenet','final',{})
        self.assertEqual((recipe['task'],recipe['seed'],recipe['wall_seconds'],recipe['batch_size']), (self.data['id'],2026,600,4))
        for settings in ({'task':'m-eurosat'},{'seed':2027},{'wall_seconds':10000},{'lr':100},{'loss':'ce_dice'}):
            with self.assertRaises(ValueError): self.runner.recipe('resnet18_imagenet','final',settings)
        with self.assertRaises(ValueError): self.runner.recipe('fcn_imagenet','final',{})
        with self.assertRaises(ValueError): self.runner.recipe('resnet18_imagenet','confirm',{})

    def saved_run(self,run_id,score=.5,phase='final'):
        from gotrain.requests import atomic_json
        from gotrain.training import digest
        folder=self.root/'artifacts/runs'/run_id; folder.mkdir(parents=True)
        (folder/'best.pt').write_bytes(b'opaque fixture; never loaded as a model')
        record={'run_id':run_id,'recipe':self.runner.recipe('resnet18_imagenet',phase,{}),
                'seed':2026,'status':'completed','eligible_reference':True,
                'task_contract_sha256':self.runner.contract_hash,'data_revision':self.data['sha256'],
                'dataset_version':self.data['sha256'],'checkpoint':'best.pt','checkpoint_sha256':digest(folder/'best.pt'),
                'best_validation':{'split':'valid','full_split':True,'primary_name':'accuracy','primary':score}}
        atomic_json(folder/'record.json',record); self.runner.runs.append(run_id)
        return record

    def test_custom_baseline_selection_ties_and_ineligible_screen(self):
        self.saved_run('first'); self.assertEqual(self.runner.select('first'),'first')
        self.saved_run('tie'); self.assertEqual(self.runner.select('tie'),'first')
        self.saved_run('screen',score=.9,phase='screen')
        with self.assertRaises(ValueError): self.runner.select('screen')
        self.saved_run('better',score=.7); self.assertEqual(self.runner.select('better'),'better')

    def test_selection_rejects_cross_dataset_wrong_metric_and_changed_weights(self):
        from gotrain.requests import atomic_json
        record=self.saved_run('candidate')
        for field,value in (('dataset_version','different'),('task_contract_sha256','different')):
            bad=copy.deepcopy(record); bad[field]=value
            atomic_json(self.root/'artifacts/runs/candidate/record.json',bad)
            with self.assertRaises(ValueError): self.runner.select('candidate')
        bad=copy.deepcopy(record); bad['best_validation']['primary_name']='macro_iou'
        atomic_json(self.root/'artifacts/runs/candidate/record.json',bad)
        with self.assertRaises(ValueError): self.runner.select('candidate')
        atomic_json(self.root/'artifacts/runs/candidate/record.json',record)
        (self.root/'artifacts/runs/candidate/best.pt').write_bytes(b'changed')
        with self.assertRaises(ValueError): self.runner.select('candidate')

    def test_benchmarks_retain_m3_selected_run_without_reopening_sessions(self):
        from gotrain.m4 import M4Runner
        from gotrain.requests import benchmark_registry,atomic_json
        task=read_json(ROOT/'docs/m3-evidence.json')['searches']['results'][0]
        run=task['selected_run']
        record=read_json(ROOT/'artifacts/runs'/run/'record.json')
        folder=self.root/'artifacts/runs'/run; folder.mkdir(parents=True)
        atomic_json(folder/'record.json',record)
        frozen=copy.deepcopy(self.frozen); frozen['dataset']=benchmark_registry(ROOT)[task['task']]
        lease=SimpleNamespace(root=self.root,owned=lambda:({},dict(self.job,frozen=frozen)))
        runner=M4Runner(lease)
        self.assertEqual(runner.best,run); self.assertFalse(runner.context()['baseline_needed'])

    def test_worker_requires_matching_live_parent_trial_before_gpu_use(self):
        from gotrain.admission import fingerprint
        from gotrain.m4 import worker_setup
        from gotrain.requests import atomic_json
        record=self.saved_run('worker'); record.update(m4_job_id=self.job['id'],m4_trial_id='trial_fixture',frozen_sha256=self.job['frozen_sha256'])
        self.job['active_trial']={'id':'trial_fixture','phase':'final','reserved_seconds':600,'started_monotonic':time.monotonic()}
        ledger={'active':self.job['id'],'jobs':{self.job['id']:self.job},'policy_sha256':fingerprint(self.lease.policy)}
        atomic_json(self.root/'artifacts/m4-budget.json',ledger)
        caps=read_json(self.root/'configs/service.json'); caps['training_enabled']=True; atomic_json(self.root/'configs/service.json',caps)
        with patch('gotrain.m4.ROOT',self.root), patch('gotrain.m4.protect_parent'), patch('gotrain.m4.os.getppid',return_value=os.getpid()), patch.dict(os.environ,{'GOTRAIN_JOB_ID':self.job['id'],'GOTRAIN_TRIAL_ID':'trial_fixture'}):
            self.assertEqual(worker_setup(self.root/'artifacts/runs/worker',record)[4]['kind'],'classification')
            with patch('gotrain.m4.os.getppid',return_value=-1):
                with self.assertRaisesRegex(RuntimeError,'live M4'): worker_setup(self.root/'artifacts/runs/worker',record)
            record['m4_trial_id']='wrong'
            with self.assertRaises(RuntimeError): worker_setup(self.root/'artifacts/runs/worker',record)


def read_json(path):
    return json.loads(Path(path).read_text())


if __name__=='__main__': unittest.main()
