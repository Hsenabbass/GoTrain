"""M4 admission/accounting primitives. No worker, agent or GPU launch here.

The future supervisor must own this lease for its entire job. Closing an unsettled
lease releases the OS lock but leaves a durable reservation blocking all allocations.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import time
import uuid
from zoneinfo import ZoneInfo

from .requests import RequestError, atomic_json, opaque, read_json


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


class Admission:
    def __init__(self, root, policy, *, clock=time.monotonic, now=lambda: datetime.now(timezone.utc)):
        self.root, self.policy, self.clock, self.now = Path(root), policy, clock, now
        self.path = self.root / 'artifacts/m4-budget.json'
        self.lock = None
        self.job_id = None

    def __enter__(self):
        # Same canonical lock as M1–M3. Linux-only runtime; no ML dependency.
        import fcntl
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = (self.path.parent / 'm1.lock').open('a')
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self.close()
            raise RequestError('Another job owns the shared GPU lock; no new job admitted', 409) from exc
        return self

    def close(self):
        if self.lock is not None:
            self.lock.close()
            self.lock = None

    def __exit__(self, *_args):
        self.close()  # Never silently settle/refund an interrupted job.

    def ledger(self):
        if self.lock is None:
            raise RuntimeError('Admission requires the shared lock lease')
        value = read_json(self.path) if self.path.exists() else {
            'schema_version': 1, 'policy_sha256': fingerprint(self.policy),
            'charged_seconds': 0, 'active': None, 'jobs': {}}
        if value['policy_sha256'] != fingerprint(self.policy):
            raise RequestError('M4 policy changed; operator reconciliation required, no budget reset', 409)
        if type(value['charged_seconds']) not in (int, float) or not math.isfinite(value['charged_seconds']) or value['charged_seconds'] < 0:
            raise RequestError('Invalid M4 accounting; operator reconciliation required', 409)
        return value

    def admit(self, store, conversation_id, request_id):
        if not store.caps['training_enabled']:
            raise RequestError('Training remains disabled pending runner/supervisor verification', 409)
        opaque(request_id, 'request')
        ledger = self.ledger()
        for job in ledger['jobs'].values():
            if job['request_id'] == request_id or job['conversation_id'] == conversation_id:
                raise RequestError('Request already admitted as ' + job['id'] + '; reconnect instead of relaunching', 409)
        if ledger['active']:
            raise RequestError('Active or interrupted M4 reservation requires reconciliation: ' + ledger['active'], 409)
        for allocation in ('m1', 'm2', 'm3'):
            path = self.path.parent / (allocation + '-budget.json')
            if path.exists() and read_json(path).get('active'):
                raise RequestError('Unsettled ' + allocation + ' reservation; no job admitted', 409)
        with store.locked():
            record = store.get(conversation_id)
            if record['status'] != 'ready_for_review' or record.get('questions'):
                raise RequestError('Resolve the request before admission', 409)
            data = store.dataset(record['dataset_id'])
            if data['counts']['train'] < 2:
                raise RequestError('At least two training images are required by the supported recipes',409)
            summary = record['summary']
            if (data.get('status') != 'validated' or summary['dataset_version'] != data['sha256']
                    or summary['dataset_id'] != data['id'] or summary['task'] != data['task']
                    or summary['counts'] != data['counts'] or summary['goal'] != record['goal']
                    or summary['limits'] != record['proposed_limits'] or summary.get('validation_only') is not True):
                raise RequestError('Resolved data/request changed; validate a new draft', 409)
            limits = store.validate_limits(record['proposed_limits'])
            if any(limits[k] > record['limits'][k] for k in limits):
                raise RequestError('Resolved limits cannot exceed approved limits')
            used = record['model_requests']
            if type(used) is not int or used < record['preflight_requests'] or used < 0:
                raise RequestError('Invalid persisted model usage; operator review required', 409)
            reserves = self.policy['reserves']
            minimum_gpu = reserves['final'] + reserves['verify']
            gpu = min(limits['gpu_seconds'], self.policy['gpu_job_seconds'] - ledger['charged_seconds'])
            minimum_runtime = sum(reserves.values())
            if gpu < minimum_gpu or limits['runtime_seconds'] < minimum_runtime or limits['model_requests'] - used < store.caps['minimum_model_requests']:
                raise RequestError('Insufficient remaining allowance: need 660 GPU seconds, 780 runtime seconds and six model calls', 409)
            deadline = datetime.fromisoformat(self.policy['submission_deadline_local']).replace(tzinfo=ZoneInfo(self.policy['timezone']))
            now = self.now()
            reserve = self.policy['submission_reserve_seconds']
            exception = self.policy.get('single_conversation_reserve_exception')
            # A recorded operator exception applies once to one frozen request.
            # Existing conversation deduplication above prevents reuse after admission.
            if (exception and exception['conversation_id'] == conversation_id
                    and exception['dataset_id'] == data['id']
                    and now < datetime.fromisoformat(exception['expires_utc'])
                    and all(limits[k] <= v for k, v in exception['maximum_limits'].items())):
                reserve = 0
            if now + timedelta(seconds=limits['runtime_seconds'] + reserve) >= deadline:
                raise RequestError('Submission reserve prevents admission', 409)
            if shutil.disk_usage(self.root).free < self.policy['disk_reserve_bytes']:
                raise RequestError('Disk reserve prevents admission', 507)
            frozen = {'summary': summary, 'messages': record['messages'], 'dataset': data,
                      'limits': {**limits, 'gpu_seconds': gpu}, 'approved_limits': record['limits'],
                      'preflight_requests': record['preflight_requests'], 'model_requests': used,
                      'prompt_sha256': record.get('prompt_sha256'), 'context_sha256': record.get('context_sha256')}
            # JSON round trip detaches the immutable snapshot from caller objects.
            frozen = json.loads(json.dumps(frozen, allow_nan=False))
        self.job_id = 'job_' + uuid.uuid4().hex
        job = {'id': self.job_id, 'request_id': request_id, 'conversation_id': conversation_id,
               'status': 'admitted', 'frozen': frozen, 'frozen_sha256': fingerprint(frozen),
               'owner_pid': os.getpid(), 'started_utc': now.isoformat(),
               'started_monotonic': self.clock(), 'runtime_seconds': limits['runtime_seconds'],
               'gpu_seconds': gpu, 'gpu_charged_seconds': 0, 'attempts': 0,
               'model_requests': used, 'active_trial': None, 'trials': []}
        ledger['jobs'][self.job_id] = job
        ledger['active'] = self.job_id
        atomic_json(self.path, ledger)  # The reservation and frozen request commit together.
        return json.loads(json.dumps(job))

    def owned(self):
        ledger = self.ledger()
        if self.job_id is None or ledger['active'] != self.job_id:
            raise RequestError('This lease does not own an active job', 409)
        job = ledger['jobs'][self.job_id]
        if fingerprint(job['frozen']) != job['frozen_sha256']:
            raise RequestError('Frozen request integrity check failed', 409)
        return ledger, job

    def check_time(self, job, reserve=0):
        if self.clock() >= job['started_monotonic'] + job['runtime_seconds'] - reserve:
            raise RequestError('Job runtime/reserve exhausted', 409)

    def charge_model_request(self):
        ledger, job = self.owned()
        self.check_time(job, self.policy['reserves']['package'])
        if job['status'] != 'admitted' or job['model_requests'] >= job['frozen']['limits']['model_requests']:
            raise RequestError('Model request allowance exhausted', 409)
        job['model_requests'] += 1
        atomic_json(self.path, ledger)  # Before every future wire call, even failed calls.

    def reserve_trial(self, phase, seconds):
        ledger, job = self.owned()
        maxima = self.policy['phase_seconds']
        if phase not in maxima or type(seconds) is not int or not 0 < seconds <= maxima[phase]:
            raise RequestError('Trial phase/time exceeds the trusted cap')
        if job['status'] != 'admitted' or job['active_trial']:
            raise RequestError('Another trial is active or job cannot launch work', 409)
        optional = phase not in ('final', 'verify')
        if phase != 'verify' and job['attempts'] >= job['frozen']['limits']['attempts'] - int(optional):
            raise RequestError('Attempt limit/reserved final attempt prevents this trial', 409)
        after = 0 if phase == 'verify' else self.policy['reserves']['verify']
        if optional:
            after += self.policy['reserves']['final']
        if job['gpu_charged_seconds'] + seconds + after > job['gpu_seconds']:
            raise RequestError('GPU allowance/finalization reserve prevents this trial', 409)
        self.check_time(job, seconds + after + self.policy['reserves']['package'])
        trial = {'id': 'trial_' + uuid.uuid4().hex, 'phase': phase, 'reserved_seconds': seconds,
                 'started_monotonic': self.clock()}
        job['active_trial'] = trial
        job['attempts'] += int(phase != 'verify')
        job['gpu_charged_seconds'] += seconds
        ledger['charged_seconds'] += seconds
        atomic_json(self.path, ledger)
        return dict(trial)

    def settle_trial(self, trial_id, status):
        ledger, job = self.owned()
        trial = job['active_trial']
        if status not in ('completed', 'failed', 'stopped') or not trial or trial['id'] != trial_id:
            raise RequestError('Invalid trial settlement/ownership', 409)
        elapsed = self.clock() - trial['started_monotonic']
        if elapsed < 0:
            raise RequestError('Clock changed; operator reconciliation required', 409)
        difference = elapsed - trial['reserved_seconds']
        job['gpu_charged_seconds'] += difference
        ledger['charged_seconds'] += difference
        job['trials'].append({**trial, 'elapsed_seconds': elapsed, 'status': status})
        job['active_trial'] = None
        if difference > 0:
            job['status'] = 'overrun'  # Record actual overrun; never hide/refund it.
        atomic_json(self.path, ledger)

    def finish(self, status):
        ledger, job = self.owned()
        if status not in ('completed', 'failed', 'stopped') or job['active_trial']:
            raise RequestError('Settle active work before finishing the job', 409)
        if job['status'] == 'overrun' and status != 'failed':
            raise RequestError('Overrun jobs must finish as failed', 409)
        job.update(status=status, finished_utc=self.now().isoformat())
        ledger['active'] = None
        atomic_json(self.path, ledger)
