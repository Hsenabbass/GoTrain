"""Configuration-only Strands controller; no shell or arbitrary file tools."""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import math
from pathlib import Path
import subprocess
import sys
import threading
import time
from .training import ROOT, read, digest, run_with_watchdog
from .runtime import validate_recipe, write_json


class Controller:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=False)
        self.caps = read(ROOT / 'configs/m2.json')
        self.contracts = read(ROOT / 'configs/tasks.json')
        self.started = time.monotonic()
        self.lock = threading.RLock()
        reference = read(ROOT / 'docs/m1-evidence.json')['classification']['results'][0]['record']
        self.state = {'task': 'm-eurosat', 'runs': [], 'attempts': 0, 'retries': 0,
                      'model_requests': 0, 'tool_calls': 0, 'usage': [],
                      'best': reference['run_id'], 'decisions': [], 'status': 'running'}
        self.save()

    def save(self):
        write_json(self.folder / 'session.json', self.state)

    def bound(self, counter):
        limit = self.caps['agent']['max_' + counter]
        if time.monotonic() - self.started >= self.caps['agent']['max_wall_seconds'] or self.state[counter] >= limit:
            raise RuntimeError('Agent limit reached: ' + counter)
        self.state[counter] += 1
        self.save()

    def record(self, run_id):
        if run_id not in [self.state['best'], self.state.get('reference'), *self.state['runs']]:
            raise ValueError('Unregistered run ID')
        record = read(ROOT / 'artifacts/runs' / run_id / 'record.json')
        if record['recipe']['task'] != self.state['task']:
            raise ValueError('Wrong task')
        return record

    def eligible(self, run_id):
        r = self.record(run_id)
        metric = r.get('best_validation', {})
        if (r.get('status') not in ('completed', 'budget_exhausted') or not r.get('eligible_reference')
                or not metric.get('full_split') or metric.get('split') != 'valid'
                or r['task_contract_sha256'] != digest(ROOT / 'configs/tasks.json')
                or not math.isfinite(metric['primary']) or not 0 <= metric['primary'] <= 1):
            raise ValueError('Ineligible validation result')
        path = ROOT / 'artifacts/runs' / run_id / r['checkpoint']
        if r['checkpoint'] not in ('best.pt', 'last.pt') or digest(path) != r['checkpoint_sha256']:
            raise ValueError('Checkpoint integrity failed')
        return r

    def inspect_task(self):
        """Read the registered EuroSAT contract, train/validation diagnostics and prior best."""
        inspection = read(ROOT / 'docs/data-inspection.json')
        task = next(t for t in inspection['tasks'] if t['name'] == self.state['task'])
        return {'contract': self.contracts['tasks'][self.state['task']],
                'diagnostics': task['splits'], 'recipe': read(ROOT / 'configs/reference-m-eurosat.json'),
                'best_run': self.state['best'], 'budget': self.caps['agent']}

    def train_candidate(self, changes: dict, hypothesis: str, parent_run: str, retry_of: str = ''):
        """Train one allowlisted configuration change; parent_run must be a registered run."""
        self.record(parent_run)
        if not hypothesis or len(hypothesis) > 2000:
            raise ValueError('Supply a short hypothesis')
        allowed = {'lr', 'weight_decay', 'batch_size', 'epochs', 'steps', 'wall_seconds', 'augment', 'normalization'}
        if not isinstance(changes, dict) or set(changes) - allowed:
            raise ValueError('Unsupported recipe fields')
        recipe = {**read(ROOT / 'configs/reference-m-eurosat.json'), **changes}
        recipe['description'] = self.folder.name
        validate_recipe(recipe, self.contracts, self.caps)
        if time.monotonic() - self.started + recipe['wall_seconds'] + 65 >= self.caps['agent']['max_wall_seconds']:
            raise RuntimeError('Insufficient training wall budget')
        if retry_of:
            if retry_of not in self.state['runs'] or self.state['retries'] >= 1:
                raise ValueError('Retry allowance exhausted')
            parent = self.record(retry_of)
            if parent['status'] != 'failed' or parent.get('retry_of') or parent.get('retryable') not in ('oom', 'transient'):
                raise ValueError('Failure is not retryable')
            if parent['retryable'] == 'oom' and recipe['batch_size'] > parent['recipe']['batch_size'] // 2:
                raise ValueError('OOM retry must halve batch')
        elif self.state['attempts'] >= self.caps['agent']['max_training_runs']:
            raise ValueError('Training run cap reached')
        self.state['retries' if retry_of else 'attempts'] += 1
        self.save()
        path = self.folder / ('recipe-' + str(len(self.state['decisions'])) + '.json')
        write_json(path, recipe)
        args = ['train', '--recipe', str(path)]
        if retry_of:
            args += ['--retry-of', retry_of]
        before = set((ROOT / 'artifacts/runs').iterdir())
        result = self.execute(args)
        new = [p for p in (ROOT / 'artifacts/runs').iterdir() if p not in before and (p / 'record.json').exists()
               and read(p / 'record.json')['recipe']['description'] == self.folder.name]
        if len(new) != 1:
            raise RuntimeError('Runner did not create exactly one recorded attempt: ' + result['error'])
        run_id = new[0].name
        self.state['runs'].append(run_id)
        self.state['decisions'].append({'run_id': run_id, 'parent': parent_run, 'hypothesis': hypothesis, 'changes': changes, 'retry_of': retry_of})
        self.save()
        return {'run_id': run_id, **result, 'record': self.record(run_id)}

    def execute(self, args):
        command = [sys.executable, str(ROOT / 'scripts/train.py'), *args,
                   '--allocation', 'm2', '--data-root', str(ROOT / 'data/geo-bench/datasets')]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        with (self.folder / 'runner.log').open('a') as stream:
            stream.write(result.stdout + result.stderr)
        return {'passed': result.returncode == 0, 'error': result.stderr[-1200:] if result.returncode else ''}

    def read_result(self, run_id: str):
        """Read validation/failure evidence for a registered run."""
        return self.record(run_id)

    def verify_prediction(self, run_id: str):
        """Reload a retained checkpoint, validate and predict on permitted validation input."""
        self.eligible(run_id)
        if time.monotonic() - self.started + 65 >= self.caps['agent']['max_wall_seconds']:
            raise RuntimeError('Insufficient verification wall budget')
        return self.execute(['verify', '--run-id', run_id])

    def select_candidate(self, run_id: str, reason: str):
        """Record keep/reject using trusted full-validation scores; ties keep the prior best."""
        candidate = self.eligible(run_id)
        prior = self.eligible(self.state['best'])
        keep = candidate['best_validation']['primary'] > prior['best_validation']['primary']
        if keep:
            self.state['best'] = run_id
        self.state['decisions'].append({'candidate': run_id, 'kept': keep, 'best': self.state['best'], 'reason': reason[:2000]})
        self.save()
        return {'kept': keep, 'best': self.state['best']}

    def invoke(self, method, **kwargs):
        with self.lock:
            self.bound('tool_calls')
            try:
                return getattr(self, method)(**kwargs)
            except (ValueError, KeyError, RuntimeError) as exc:
                return {'error': str(exc), 'best': self.state['best']}


def create_agent(controller):
    from strands import Agent, tool
    from strands.models import BedrockModel
    from botocore.config import Config
    from botocore.exceptions import ConnectionClosedError
    class BoundedModel(BedrockModel):
        async def stream(self, *args, **kwargs):
            for attempt in range(2):
                controller.bound('model_requests')
                received = False
                try:
                    async for event in super().stream(*args, **kwargs):
                        if hasattr(controller, 'check_event'):
                            controller.check_event()
                        received = True
                        if 'metadata' in event:
                            controller.state['usage'].append(event['metadata'])
                            controller.save()
                        yield event
                    return
                except ConnectionClosedError:
                    # A stale connection after a long tool call may close before
                    # any response. Retry once, counting the new wire request.
                    if attempt or received:
                        raise
                    controller.state.setdefault('service_retries', []).append({
                        'error_type': 'ConnectionClosedError',
                        'after_model_request': controller.state['model_requests']})
                    controller.save()

    def wrap(method):
        # Preserve the method signature/docstring for Strands' tool schema.
        import functools
        @functools.wraps(method)
        def call(*args, **kwargs):
            import inspect
            values = inspect.signature(method).bind(*args, **kwargs)
            return controller.invoke(method.__name__, **values.arguments)
        return tool(call)

    model = BoundedModel(model_id='eu.anthropic.claude-sonnet-5-5', region_name='eu-central-1',
                         max_tokens=controller.caps['agent']['max_output_tokens'],
                         boto_client_config=Config(connect_timeout=5, read_timeout=30, retries={'total_max_attempts': 1}))
    agent = Agent(model=model, tools=[wrap(getattr(controller, name)) for name in
                  getattr(controller, 'tool_names', ('inspect_task', 'train_candidate', 'read_result', 'verify_prediction', 'select_candidate'))],
                  callback_handler=None, load_tools_from_directory=False,
                  system_prompt=getattr(controller, 'system_prompt', 'You run bounded geospatial experiments. Use only supplied tools. Inspect first, train a starting recipe, read evidence, run one justified configuration change, and select both candidates. Keep prior best if changes fail. Explain hypotheses and decisions. Never access test. Stop on exhausted budget or fatal failure; at most one eligible retry. Verify prediction on the selected best at the end.'))
    return agent


def run_agent(folder, task=None, resume=False):
    if task:
        from .search import SearchController
        controller = SearchController(folder, task, resume)
    else:
        controller = Controller(folder)
    agent = create_agent(controller)
    try:
        instruction = ('Complete the bounded search for '+task+' using inspect_task and finish_search. Do not ask routine human questions.'
                       if task else 'Complete one EuroSAT improvement cycle without asking routine human questions.')
        if task and resume:
            instruction += (' Resume existing work: inspect_task includes prior_trials and prior_selections. '
                            'Do not repeat completed stages or shortlist again. If a final trial exists, '
                            'select it, verify the retained best, then finish. Reuse the supplied results; '
                            'preserve all counters and budgets.')
        result = agent(instruction)
        controller.state.update(status=controller.state['status'] if task and controller.state.get('stage')=='done' else 'incomplete' if task else 'agent_returned', response=str(result))
    except BaseException as exc:
        controller.state.update(status='failed', error=str(exc))
        raise
    finally:
        controller.save()


def main():
    if ROOT != Path('/home/sagemaker-user/GoTrain').resolve():
        raise RuntimeError('Run only on canonical SageMaker checkout')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--task', choices=tuple(read(ROOT/'configs/tasks.json')['tasks']))
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    if args.worker:
        run_agent(args.worker,args.task,args.resume)
        return
    directory = ROOT / ('artifacts/agent-m3' if args.task else 'artifacts/agent')
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'controller.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        folder = directory / (args.task or datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
        if args.task and folder.exists() and not args.resume:
            raise RuntimeError('Task session exists; use --resume after reviewing its state')
        command = [sys.executable, str(ROOT/'scripts/agent.py'), '--worker',str(folder)]
        seconds = read(ROOT/('configs/m3.json' if args.task else 'configs/m2.json'))['agent']['max_wall_seconds']
        if args.task:command += ['--task',args.task]
        if args.resume:
            command += ['--resume']
            created = read(folder/'session.json')['created_utc']
            seconds -= (datetime.now(timezone.utc)-datetime.fromisoformat(created)).total_seconds()
        if seconds<=0:raise RuntimeError('Session wall allowance exhausted')
        try:
            run_with_watchdog(command, seconds, directory/'agent.log')
        except BaseException:
            if (folder / 'session.json').exists():
                state = read(folder / 'session.json'); state['status'] = 'interrupted'; write_json(folder / 'session.json', state)
            raise
        print(folder)
