"""Manual-run admission, single-job lock and durable shared budget accounting."""
from datetime import datetime, timedelta
import fcntl
import json
import math
import os
from pathlib import Path
import shutil
import time
from zoneinfo import ZoneInfo


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.partial')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def tree_bytes(directory):
    return sum(p.stat().st_size for p in directory.rglob('*') if p.is_file())


def validate_recipe(recipe, contracts, caps):
    if caps.get('allocation') == 'm3':
        return validate_search_recipe(recipe, contracts, caps)
    allowed = {'task', 'description', 'model', 'smoke', 'epochs', 'steps', 'wall_seconds', 'batch_size', 'lr', 'weight_decay', 'train_limit', 'valid_limit', 'augment', 'normalization'}
    if set(recipe) - allowed:
        raise ValueError('Unknown recipe fields')
    for flag in ('smoke', 'augment'):
        if flag in recipe and type(recipe[flag]) is not bool:
            raise ValueError('Recipe flags must be booleans')
    spec = contracts['tasks'][recipe['task']]
    if recipe['model'] != ('resnet18' if spec['kind'] == 'classification' else 'fcn_resnet50'):
        raise ValueError('Unsupported model/task pairing')
    for key, ceiling in [('epochs', caps['reference_run']['max_epochs']), ('steps', caps['reference_run']['max_train_steps']), ('wall_seconds', caps['reference_run']['max_wall_seconds']), ('batch_size', spec['batch_size_ceiling'])]:
        if type(recipe.get(key)) is not int or not 0 < recipe[key] <= ceiling:
            raise ValueError('Recipe exceeds ' + key + ' contract')
    if recipe['batch_size'] < 2:
        raise ValueError('Current batch-normalized models require batch size >= 2')
    for key in ('lr', 'weight_decay'):
        if not isinstance(recipe.get(key), (int, float)) or not math.isfinite(recipe[key]) or recipe[key] < 0:
            raise ValueError('Invalid optimizer setting')
    if recipe['lr'] == 0 or recipe.get('normalization', 'fixed') not in ('fixed', 'train_standardize'):
        raise ValueError('Invalid learning rate/normalization')
    if recipe.get('smoke', False):
        for key in ('train_limit', 'valid_limit'):
            if type(recipe.get(key)) is not int or recipe[key] < recipe['batch_size']:
                raise ValueError('Smoke limits must include a complete batch')
    elif recipe.get('train_limit') is not None or recipe.get('valid_limit') is not None:
        raise ValueError('Subsets are smoke-only, never reference runs')
    return spec


class Budget:
    def __init__(self, root, caps, calibration_seconds, allocation="m1"):
        self.root, self.caps = Path(root), caps
        (self.root / 'artifacts').mkdir(exist_ok=True)
        self.lock = (self.root / 'artifacts/m1.lock').open('a')
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.lock.close()
            raise RuntimeError('Another M1 job holds the GPU budget lock')
        if allocation not in ('m1', 'm2', 'm3'):
            self.close()
            raise ValueError('Unknown allocation')
        for other in ('m1', 'm2', 'm3', 'm4'):
            path = self.root / ('artifacts/' + other + '-budget.json')
            if path.exists() and json.loads(path.read_text()).get('active'):
                self.close()
                raise RuntimeError('Unsettled shared GPU reservation')
        self.allocation = allocation
        self.path = self.root / ('artifacts/' + allocation + '-budget.json')
        self.ledger = json.loads(self.path.read_text()) if self.path.exists() else {
            'charged_seconds': 60 + calibration_seconds if allocation == 'm1' else 0,
            'categories': {'earlier_access_accounting_reserve': 60, 'calibration': calibration_seconds} if allocation == 'm1' else {},
            'active': None, 'runs': []}
        if self.ledger['active']:
            self.close()
            raise RuntimeError('Unsettled reservation: inspect previous job before resuming')

    def begin(self, run_id, category, seconds, retry_of=None, task_id=None, job_type=None):
        deadline = datetime.fromisoformat(self.caps['submission_deadline_local']).replace(tzinfo=ZoneInfo(self.caps['timezone']))
        if datetime.now(ZoneInfo(self.caps['timezone'])) + timedelta(seconds=seconds + self.caps['final_submission_reserve_seconds']) >= deadline:
            raise RuntimeError('Submission reserve prevents this job')
        if self.ledger['charged_seconds'] + seconds > self.caps['m1_total_gpu_job_wall_seconds']:
            raise RuntimeError('Shared M1 budget exhausted')
        if self.ledger['categories'].get(category, 0) + seconds > self.caps['allocation_caps_seconds'][category]:
            raise RuntimeError('M1 category allocation exhausted')
        if retry_of and sum(row.get('retry_of') == retry_of for row in self.ledger['runs']) >= self.caps['retries']['max_retries_per_failed_run']:
            raise RuntimeError('Retry allowance exhausted')
        if self.allocation == 'm2':
            attempts = sum(r['category'] == category for r in self.ledger['runs'])
            limit = 2 if category == 'four_reference_runs' else 1 if category == 'failure_reserve' else None
            if limit is not None and attempts >= limit:
                raise RuntimeError('M2 attempt allowance exhausted')
        if self.allocation == 'm3':
            if job_type == 'train' and sum(r.get('task_id') == task_id and r.get('job_type') == 'train' for r in self.ledger['runs']) >= self.caps['agent']['max_training_runs']:
                raise RuntimeError('M3 task attempt limit reached')
            if retry_of and any(r.get('retry_of') for r in self.ledger['runs']):
                raise RuntimeError('M3 shared retry exhausted')
        self.started = time.monotonic()
        reservation = {'task_id': task_id, 'job_type': job_type, 'allocation': self.allocation, 'run_id': run_id, 'category': category, 'seconds': seconds, 'retry_of': retry_of, 'started_monotonic': self.started, 'owner_pid': os.getpid()}
        self.ledger['active'] = reservation
        self.ledger['charged_seconds'] += seconds
        self.ledger['categories'][category] = self.ledger['categories'].get(category, 0) + seconds
        write_json(self.path, self.ledger)
        return reservation

    def finish(self, status):
        active = self.ledger['active']
        elapsed = time.monotonic() - self.started
        refund = active['seconds'] - elapsed
        self.ledger['charged_seconds'] -= refund
        self.ledger['categories'][active['category']] -= refund
        self.ledger['runs'].append({**active, 'elapsed_seconds': elapsed, 'status': status})
        self.ledger['active'] = None
        write_json(self.path, self.ledger)
        return elapsed

    def close(self):
        self.lock.close()


class Guard:
    def __init__(self, root, run, caps, deadline, clock=time.monotonic):
        self.root, self.run, self.caps, self.deadline, self.clock = Path(root), Path(run), caps, deadline, clock

    def check(self, reserve=0, torch_module=None, extra_storage=0):
        if self.clock() >= self.deadline - reserve:
            raise TimeoutError('Wall-time reserve reached')
        limits = self.caps['resources']
        if shutil.disk_usage(self.root).free - extra_storage < limits['disk_free_reserve_gib'] * 2**30:
            raise RuntimeError('Disk reserve reached')
        if tree_bytes(self.run) + extra_storage > limits['per_run_artifact_limit_gib'] * 2**30 or tree_bytes(self.root / 'artifacts') + extra_storage > limits['m1_retained_artifact_limit_gib'] * 2**30:
            raise RuntimeError('Artifact storage cap reached')
        if torch_module and (torch_module.cuda.memory_allocated() > limits['gpu_allocated_limit_gib'] * 2**30 or torch_module.cuda.memory_reserved() > limits['gpu_reserved_limit_gib'] * 2**30):
            raise RuntimeError('GPU memory cap reached')


def validate_search_recipe(recipe, contracts, caps):
    from .models import CANDIDATES
    allowed = {'task', 'description', 'model', 'smoke', 'epochs', 'steps', 'wall_seconds',
               'batch_size', 'lr', 'weight_decay', 'augment', 'normalization', 'seed',
               'optimizer', 'schedule', 'loss', 'head_only', 'backbone_lr_ratio', 'phase', 'train_limit', 'valid_limit'}
    if set(recipe) - allowed:
        raise ValueError('Unknown search recipe fields')
    spec = contracts['tasks'][recipe['task']]
    name = recipe['model']
    legacy = 'resnet18' if spec['kind'] == 'classification' else 'fcn_resnet50'
    if name != legacy and (name not in CANDIDATES or CANDIDATES[name][0] != spec['kind']):
        raise ValueError('Unsupported model/task pairing')
    for key in ('smoke', 'augment', 'head_only'):
        if type(recipe.get(key)) is not bool:
            raise ValueError('Boolean recipe field required')
    phases = {'probe':30, 'screen':150, 'tune':300, 'final':600, 'confirm':600}
    if recipe.get('phase') not in phases or recipe['smoke'] != (recipe['phase'] == 'probe'):
        raise ValueError('Invalid search phase')
    for key, maximum in [('epochs',50), ('steps',10000), ('wall_seconds',phases[recipe['phase']]), ('batch_size',spec['batch_size_ceiling'])]:
        if type(recipe.get(key)) is not int or not 0 < recipe[key] <= maximum:
            raise ValueError('Search recipe exceeds ' + key)
    if recipe['batch_size'] < 2 or recipe.get('seed') not in (2026,2027):
        raise ValueError('Invalid batch or seed')
    if recipe.get('schedule') not in ('constant','cosine') or recipe['optimizer'] not in ('sgd','adamw') or recipe['loss'] not in ('ce','weighted_ce','ce_dice'):
        raise ValueError('Unsupported optimizer/loss')
    if recipe['loss'] == 'ce_dice' and spec['kind'] != 'segmentation':
        raise ValueError('Dice requires segmentation')
    if recipe['normalization'] != ('pretrained' if name in CANDIDATES else 'train_standardize'):
        raise ValueError('Wrong normalization for candidate')
    if recipe['head_only'] and (name not in CANDIDATES or spec['channels'] != 3):
        raise ValueError('Head-only requires a three-channel pretrained model')
    low, high = (1e-5,1e-3) if recipe['optimizer'] == 'adamw' else (1e-3,1e-1)
    for key,lo,hi in [('lr',low,high),('weight_decay',0,1e-2),('backbone_lr_ratio',.01,1)]:
        value = recipe.get(key)
        if type(value) not in (int,float) or not math.isfinite(value) or not lo <= value <= hi:
            raise ValueError('Invalid ' + key)
    if recipe['smoke']:
        if recipe['steps']>2:
            raise ValueError('Probe is capped at two training steps')
        for key in ('train_limit','valid_limit'):
            if type(recipe.get(key)) is not int or not recipe['batch_size'] <= recipe[key] <= 64:
                raise ValueError('Invalid probe subset')
    elif 'train_limit' in recipe or 'valid_limit' in recipe:
        raise ValueError('Only probes permit subsets')
    return spec
