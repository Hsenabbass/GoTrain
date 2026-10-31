"""Trusted M4 dataset/recipe routing into the existing guarded training worker."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from .admission import fingerprint
from .requests import read_json, opaque
from .training import ROOT, digest


def protect_parent(expected_pid):
    """Set in the child (never preexec): an orphan cannot keep doing GPU work."""
    import ctypes
    import signal
    if ctypes.CDLL(None,use_errno=True).prctl(1,signal.SIGKILL,0,0,0)!=0:
        raise OSError(ctypes.get_errno(),'Could not set parent-death protection')
    if os.getppid()!=expected_pid:
        raise RuntimeError('Supervisor died before worker protection was installed')


def dataset_contract(root, frozen):
    """Resolve registered IDs only; no paths or download URLs from task text."""
    from .data import task_spec, validate_task
    root = Path(root)
    data = frozen['dataset']
    contracts = read_json(root/'configs/tasks.json')
    inspection = read_json(root/'docs/data-inspection.json')
    if data['source'] == 'benchmark':
        spec = task_spec(data['id'], contracts, inspection)
        expected = contracts['dataset_revision'] + ':' + digest(root/'configs/tasks.json')
        if data['sha256'] != expected or contracts['tasks'][data['id']] != data['task']:
            raise ValueError('Frozen benchmark contract changed')
        return spec, digest(root/'configs/tasks.json'), contracts, inspection
    if data['source'] != 'manifest_zip':
        raise ValueError('Unsupported registered data source')
    opaque(data['id'], 'dataset')
    folder = root/'artifacts/service/datasets'/data['id']
    if folder.resolve().parent != (root/'artifacts/service/datasets').resolve() or folder.is_symlink():
        raise ValueError('Invalid registered dataset directory')
    if read_json(folder/'record.json') != data:
        raise ValueError('Registered import differs from frozen dataset')
    manifest = read_json(folder/'manifest.json')
    if manifest['task'] != data['task'] or {s: len(v) for s,v in manifest['splits'].items()} != data['counts']:
        raise ValueError('Manifest metadata differs from validated import')
    spec = {**validate_task(data['task']), 'batch_size_ceiling': 4 if data['task']['kind']=='segmentation' else 32}
    return spec, digest(folder/'manifest.json'), {'tasks': {data['id']: spec}, 'dataset_revision': data['sha256']}, None


def open_frozen(root, frozen, split, limit=None, augment=False):
    from .data import open_task, require_split
    require_split(split)  # Before resolving a dataset or opening any samples.
    spec, _, contracts, inspection = dataset_contract(root, frozen)
    data = frozen['dataset']
    manifest = Path(root)/'artifacts/service/datasets'/data['id']/'manifest.json' if data['source']=='manifest_zip' else None
    dataset = open_task(Path(root)/'data/geo-bench/datasets', None if manifest else data['id'], split,
                        contracts, inspection, manifest, augment)
    dataset.spec = spec
    if limit is not None:
        dataset.count = min(limit, dataset.official_count)
    return dataset


def worker_setup(run, record):
    """Worker verifies its live parent-owned reservation before any data/GPU use."""
    from .runtime import Guard
    if read_json(ROOT/'configs/service.json')['training_enabled'] is not True:
        raise RuntimeError('M4 execution remains disabled')
    ledger = read_json(ROOT/'artifacts/m4-budget.json')
    if ledger['policy_sha256'] != fingerprint(read_json(ROOT/'configs/m4.json')):
        raise RuntimeError('M4 policy changed after reservation')
    job = ledger['jobs'][os.environ['GOTRAIN_JOB_ID']]
    trial = job['active_trial']
    if (ledger['active'] != job['id'] or job['owner_pid'] != os.getppid()
            or job['status'] != 'admitted' or not trial
            or trial['id'] != os.environ.get('GOTRAIN_TRIAL_ID')
            or record['m4_trial_id'] != trial['id'] or record['m4_job_id'] != job['id']
            or fingerprint(job['frozen']) != job['frozen_sha256']
            or record['frozen_sha256'] != job['frozen_sha256']):
        raise RuntimeError('Worker requires its live M4 supervisor reservation')
    protect_parent(job['owner_pid'])
    if Path(run).resolve().parent != (ROOT/'artifacts/runs').resolve():
        raise RuntimeError('M4 worker run must belong to the canonical run registry')
    spec, contract_hash, contracts, inspection = dataset_contract(ROOT, job['frozen'])
    if record['task_contract_sha256'] != contract_hash:
        raise ValueError('Task contract changed after preparation')
    caps = read_json(ROOT/'configs/m3.json')  # Reuse frozen numerical/resource guards.
    from .runtime import validate_search_recipe
    validate_search_recipe(record['recipe'], contracts, caps)
    if record['recipe']['task'] != job['frozen']['dataset']['id'] or record['recipe']['seed'] != 2026:
        raise ValueError('M4 recipe changed task or primary seed')
    phase = 'verify' if record.get('m4_verifying') else record['recipe']['phase']
    if trial['phase'] != phase or (phase != 'verify' and trial['reserved_seconds'] != record['recipe']['wall_seconds']):
        raise ValueError('Recipe does not match reserved work')
    deadline = min(trial['started_monotonic']+trial['reserved_seconds'], job['started_monotonic']+job['runtime_seconds'])
    guard = Guard(ROOT, run, caps, deadline)
    guard.check()
    return caps, contracts, inspection, guard, spec, job['frozen'], contract_hash


class M4Runner:
    """Operator tools for the later agent/supervisor; never acquires another GPU lock."""
    def __init__(self, lease):
        self.lease = lease
        self.root = lease.root
        _, job = lease.owned()
        self.frozen = job['frozen']
        self.spec, self.contract_hash, self.contracts, self.inspection = dataset_contract(self.root, self.frozen)
        self.task = self.frozen['dataset']['id']
        self.best = None
        self.runs = []
        self.on_change = lambda: None
        self.on_worker = lambda _pid: None
        if self.frozen['dataset']['source'] == 'benchmark':
            selected = next(t for t in read_json(self.root/'docs/m3-evidence.json')['searches']['results'] if t['task']==self.task)
            self.best = selected['selected_run']
            self.result(self.best)

    def context(self):
        _, job = self.lease.owned()
        return {'goal': self.frozen['summary']['goal'], 'task': self.spec,
                'counts': {s: self.frozen['dataset']['counts'][s] for s in ('train','valid')},
                'dataset_version': self.frozen['dataset']['sha256'], 'limits': self.frozen['limits'],
                'model_requests': job['model_requests'], 'best': self.best,
                'baseline_needed': self.best is None, 'validation_only': True}

    def recipe(self, candidate, phase, settings):
        from .runtime import validate_search_recipe
        if phase not in ('probe','screen','tune','final'):
            raise ValueError('Unsupported M4 training phase')
        batch = min(4 if self.spec['kind']=='segmentation' else 32, self.spec.get('batch_size_ceiling',32))
        legacy = 'resnet18' if self.spec['kind']=='classification' else 'fcn_resnet50'
        recipe = {'task': self.task, 'description': 'M4 bounded experiment', 'model': candidate,
                  'phase': phase, 'seed': 2026, 'smoke': phase=='probe', 'augment': False,
                  'normalization': 'train_standardize' if candidate==legacy else 'pretrained',
                  'optimizer': 'adamw', 'lr': .001, 'weight_decay': .0001, 'schedule': 'cosine',
                  'loss': 'ce', 'head_only': False, 'backbone_lr_ratio': .1,
                  'epochs': 50, 'steps': 10000, 'batch_size': batch,
                  'wall_seconds': self.lease.policy['phase_seconds'][phase]}
        allowed = {'optimizer','lr','weight_decay','augment','loss','head_only','batch_size','epochs','steps','backbone_lr_ratio'}
        if not isinstance(settings, dict) or set(settings)-allowed:
            raise ValueError('Only reviewed numerical settings may change')
        recipe.update(settings)
        if phase=='probe':
            recipe.update(steps=2,train_limit=64,valid_limit=64)
        if candidate != legacy:
            from .models import candidate_info
            candidate_info(candidate, self.spec)
        spec = {**self.spec, 'batch_size_ceiling': batch}
        validate_search_recipe(recipe, {'tasks': {self.task: spec}}, read_json(self.root/'configs/m3.json'))
        if self.frozen['dataset']['counts']['train'] < recipe['batch_size']:
            recipe['batch_size'] = min(recipe['batch_size'], self.frozen['dataset']['counts']['train'])
            validate_search_recipe(recipe, {'tasks': {self.task: spec}}, read_json(self.root/'configs/m3.json'))
        return recipe

    def result(self, run_id):
        if run_id != self.best and run_id not in self.runs:
            raise ValueError('Run is not registered to this task')
        record = read_json(self.root/'artifacts/runs'/run_id/'record.json')
        benchmark = self.frozen['dataset']['source']=='benchmark'
        if (record['recipe']['task'] != self.task or record['task_contract_sha256'] != self.contract_hash
                or record['data_revision'] != self.contracts['dataset_revision']
                or not benchmark and record.get('dataset_version') != self.frozen['dataset']['sha256']):
            raise ValueError('Cannot compare across dataset/contract versions')
        return record

    def select(self, run_id):
        record = self.result(run_id)
        metrics = record.get('best_validation', {})
        if (record['status'] not in ('completed','budget_exhausted') or not record.get('eligible_reference')
                or record['recipe'].get('phase')!='final' or record['seed']!=2026
                or not metrics.get('full_split') or metrics.get('split')!='valid'
                or metrics.get('primary_name')!=self.spec['primary_metric']
                or not isinstance(metrics.get('primary'),(int,float)) or not 0 <= metrics['primary'] <= 1
                or digest(self.root/'artifacts/runs'/run_id/record['checkpoint'])!=record['checkpoint_sha256']):
            raise ValueError('Select only intact primary-seed full-validation final checkpoints')
        if self.best is None or metrics['primary'] > self.result(self.best)['best_validation']['primary']:
            self.best = run_id
        self.on_change()
        return self.best

    def run_trial(self, candidate, phase, settings, hypothesis):
        if ROOT != Path('/home/sagemaker-user/GoTrain') or self.root.resolve()!=ROOT or read_json(ROOT/'configs/service.json')['training_enabled'] is not True:
            raise RuntimeError('M4 worker execution remains disabled until integration verification')
        if not isinstance(hypothesis,str) or not 1 <= len(hypothesis.strip()) <= 2000:
            raise ValueError('A bounded evidence-based hypothesis is required')
        recipe = self.recipe(candidate, phase, settings)
        receipt = None
        from .models import CANDIDATES
        if candidate in CANDIDATES:
            receipt = read_json(self.root/'docs/m3-evidence.json')['preparation']['weights'][candidate]
            weights = self.root/'artifacts/weights/m3'/receipt['filename']
            if digest(weights)!=receipt['sha256']:
                raise ValueError('Reviewed initialization weights changed; no download fallback')
        trial = self.lease.reserve_trial(phase, recipe['wall_seconds'])
        run_id = self.lease.job_id+'-'+trial['id']
        run = self.root/'artifacts/runs'/run_id
        run.mkdir()
        _, job = self.lease.owned()
        from .requests import atomic_json
        record = {'run_id':run_id,'status':'created','recipe':recipe,'seed':2026,
                  'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=self.root,text=True).strip(),
                  'task_contract_sha256':self.contract_hash,'data_revision':self.contracts['dataset_revision'],
                  'dataset_version':self.frozen['dataset']['sha256'],'m4_job_id':job['id'],
                  'm4_trial_id':trial['id'],'frozen_sha256':job['frozen_sha256'],
                  'parent_run':self.best,'hypothesis':hypothesis,'weight_receipt':receipt}
        atomic_json(run/'record.json',record)
        self.runs.append(run_id)
        self.on_change()
        from .training import run_with_watchdog
        remaining = trial['reserved_seconds']-(time.monotonic()-trial['started_monotonic'])
        status = 'failed'
        try:
            if remaining <= 0:
                raise TimeoutError('No trial allowance remains; no worker launched')
            run_with_watchdog([sys.executable,str(self.root/'scripts/train.py'),'_worker','--run',str(run),
                               '--data-root',str(self.root/'data/geo-bench/datasets')],remaining,run/'worker.log',
                              {**os.environ,'GOTRAIN_ALLOCATION':'m4','GOTRAIN_JOB_ID':job['id'],'GOTRAIN_TRIAL_ID':trial['id']},self.on_worker)
            status = 'completed'
        except Exception as exc:
            failed = read_json(run/'record.json')
            failed.update(status='failed',error_type=type(exc).__name__,error=str(exc)[:500])
            atomic_json(run/'record.json',failed)
            raise
        finally:
            # Watchdog waits for child termination before returning/raising.
            self.lease.settle_trial(trial['id'],status)
            self.on_worker(None)
        return self.result(run_id)
