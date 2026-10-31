"""One manual runner: guarded worker, checkpoints and fresh-process verification."""
import argparse
from datetime import datetime, timezone
import errno
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import traceback
from .runtime import Budget, Guard, validate_recipe, write_json

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def environment():
    import importlib.metadata as md
    return {p: md.version(p) for p in ('torch', 'torchvision', 'numpy', 'geobench', 'h5py')}


def evaluate(model, dataset, spec, guard):
    import torch
    from .metrics import Confusion
    from .models import logits_for
    counts = Confusion(spec['classes'])
    land = Confusion(spec['classes'], ignore_target=0, exclude_macro=(0,)) if spec['classes'] == 7 else None
    loader = torch.utils.data.DataLoader(dataset, batch_size=spec['_batch_size'], shuffle=False, num_workers=0)
    model.eval()
    images = 0
    with torch.no_grad():
        for x, y in loader:
            guard.check(torch_module=torch)
            with torch.autocast('cuda', dtype=torch.float16):
                logits = logits_for(model, x.cuda(), spec)
            prediction = logits.argmax(1).cpu()
            counts.update(prediction, y)
            if land:
                land.update(prediction, y)
            images += len(x)
    if images != len(dataset):
        raise ValueError('Incomplete validation traversal')
    result = counts.compute()
    result.update(split='valid', images=images, full_split=images == dataset.official_count,
                  primary_name=spec['primary_metric'], primary=result[spec['primary_metric']])
    if spec['classes'] == 2:
        result.update(positive_precision=result['per_class_precision'][1], positive_recall=result['per_class_recall'][1],
                      positive_f1=result['per_class_f1'][1], foreground_iou=result['per_class_iou'][1], foreground_f1=result['per_class_f1'][1])
    if land:
        result['land_macro_iou_target_0_ignored'] = land.compute(allow_empty=True)['macro_iou']
    return result


def prediction_summary(model, dataset, spec):
    import torch
    from .models import logits_for
    model.eval()
    x, _ = dataset[0]
    with torch.no_grad(), torch.autocast('cuda', dtype=torch.float16):
        logits = logits_for(model, x[None].cuda(), spec)
    probabilities = logits.float().softmax(1)
    prediction = probabilities.argmax(1).cpu()
    return {'prediction_shape': list(prediction.shape), 'probability_shape': list(probabilities.shape),
            'class_ids': prediction.unique().tolist(),
            'prediction_sha256': hashlib.sha256(prediction.numpy().tobytes()).hexdigest(),
            'max_probability_sum_error': float((probabilities.sum(1) - 1).abs().max())}


def checkpoint(path, model, optimizer, meta, guard):
    import torch
    value = {'model': model.state_dict(), 'optimizer': optimizer.state_dict(), 'meta': meta}
    def size(obj):
        if torch.is_tensor(obj):
            return obj.nelement() * obj.element_size()
        if isinstance(obj, dict):
            return sum(size(v) for v in obj.values())
        if isinstance(obj, (list, tuple)):
            return sum(map(size, obj))
        return 0
    guard.check(extra_storage=int(size(value) * 1.1) + 2**20)
    partial = path.with_suffix('.pt.partial')
    torch.save(value, partial)
    guard.check()
    partial.replace(path)  # A failed write never replaces the prior checkpoint.


def worker(run, data_root, verify=False):
    import random
    import numpy as np
    import torch
    from .data import DevelopmentData, fit_normalization
    from .models import build_model
    run = Path(run)
    record = read(run / 'record.json')
    allocation = os.environ.get('GOTRAIN_ALLOCATION', 'm1')
    if allocation not in ('m1', 'm2'):
        raise ValueError('Unknown allocation')
    active = read(ROOT / ('artifacts/' + allocation + '-budget.json'))['active']
    if not active or active['run_id'] != os.environ.get('GOTRAIN_JOB_ID') or active['owner_pid'] != os.getppid():
        raise RuntimeError('Worker requires a live parent budget reservation')
    caps, contracts, inspection = read(ROOT / ('configs/' + allocation + '.json')), read(ROOT / 'configs/tasks.json'), read(ROOT / 'docs/data-inspection.json')
    guard = Guard(ROOT, run, caps, active['started_monotonic'] + active['seconds'])
    recipe = record['recipe']; spec = {**contracts['tasks'][recipe['task']], '_batch_size': recipe['batch_size']}
    random.seed(2026); np.random.seed(2026); torch.manual_seed(2026); torch.cuda.manual_seed_all(2026)
    torch.set_num_threads(caps['resources']['cpu_threads'])
    torch.backends.cudnn.benchmark = False
    torch.use_deterministic_algorithms(True, warn_only=True)
    if not torch.cuda.is_available():
        raise RuntimeError('Run only on the provided SageMaker CUDA environment')
    torch.cuda.reset_peak_memory_stats()
    valid = DevelopmentData(data_root, recipe['task'], 'valid', contracts, inspection, recipe.get('valid_limit'))
    model = build_model(recipe['model'], spec).cuda()
    if verify:
        path = run / record['checkpoint']
        if digest(path) != record['checkpoint_sha256']:
            raise ValueError('Checkpoint checksum mismatch')
        saved = torch.load(path, map_location='cpu', weights_only=True)
        if saved['meta']['contract_sha256'] != digest(ROOT / 'configs/tasks.json'):
            raise ValueError('Checkpoint contract differs from current contract')
        model.load_state_dict(saved['model'], strict=True)
        valid.normalization = saved['meta']['normalization']
        metrics = evaluate(model, valid, spec, guard)
        prediction = prediction_summary(model, valid, spec)
        delta = abs(metrics['primary'] - saved['meta']['validation']['primary'])
        if delta > contracts['checkpoint_revalidation_absolute_tolerance'] or prediction['prediction_sha256'] != saved['meta']['prediction']['prediction_sha256']:
            raise ValueError('Checkpoint reload did not reproduce evaluation/prediction')
        output = {'kind': 'smoke_reload' if recipe.get('smoke') else 'full_checkpoint_revalidation',
                  'checkpoint_sha256': record['checkpoint_sha256'], 'primary_delta': delta,
                  'validation': metrics, 'prediction': prediction, 'passed': True}
        write_json(run / ('reload.json' if recipe.get('smoke') else 'revalidation-' + os.environ['GOTRAIN_JOB_ID'] + '.json'), output)
        print('RELOAD_PASSED', delta, flush=True)
        return
    record.update(status='running', environment=environment(), gpu=torch.cuda.get_device_name())
    write_json(run / 'record.json', record)
    train = DevelopmentData(data_root, recipe['task'], 'train', contracts, inspection, recipe.get('train_limit'), recipe.get('augment', False))
    normalization = fit_normalization(train, lambda: guard.check(torch_module=torch)) if recipe.get('normalization') == 'train_standardize' else None
    train.normalization = valid.normalization = normalization
    generator = torch.Generator().manual_seed(2026)
    loader = torch.utils.data.DataLoader(train, batch_size=recipe['batch_size'], shuffle=True, drop_last=False, num_workers=0, generator=generator)
    optimizer = torch.optim.SGD(model.parameters(), lr=recipe['lr'], weight_decay=recipe['weight_decay'], momentum=0.9)
    scaler = torch.amp.GradScaler('cuda', init_scale=1024)
    best, steps, epochs, stop, updates = -1.0, 0, 0, False, 0
    reserve = caps['reference_run']['validation_reserve_seconds'][spec['kind']]
    for epoch in range(recipe['epochs']):
        model.train()
        completed_epoch = True
        for x, y in loader:
            try:
                guard.check(reserve=reserve, torch_module=torch)
            except TimeoutError:
                stop, completed_epoch = True, False
                break
            if steps >= recipe['steps']:
                stop, completed_epoch = True, False
                break
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast('cuda', dtype=torch.float16):
                from .models import logits_for
                loss = torch.nn.functional.cross_entropy(logits_for(model, x.cuda(), spec), y.cuda())
            if not torch.isfinite(loss):
                raise ValueError('Non-finite loss')
            before_scale = scaler.get_scale()
            scaler.scale(loss).backward(); scaler.step(optimizer); scaler.update()
            updates += int(scaler.get_scale() >= before_scale)
            steps += 1
            guard.check(torch_module=torch)
        epochs += int(completed_epoch)
        if steps and not updates:
            raise ValueError('AMP produced no optimizer updates')
        if not steps:
            raise TimeoutError('No training step fits before validation reserve')
        metrics = evaluate(model, valid, spec, guard)
        prediction = prediction_summary(model, valid, spec)
        meta = {'recipe': recipe, 'task_spec': spec, 'normalization': normalization, 'seed': 2026,
                'contract_sha256': digest(ROOT / 'configs/tasks.json'), 'steps': steps, 'epochs_completed': epochs,
                'validation': metrics, 'prediction': prediction, 'source_commit': record['source_commit']}
        checkpoint(run / 'last.pt', model, optimizer, meta, guard)
        if metrics['full_split'] and metrics['primary'] > best:
            checkpoint(run / 'best.pt', model, optimizer, meta, guard)
            best = metrics['primary']
            record['best_validation'] = metrics
        record.update(steps=steps, optimizer_updates=updates, amp_skipped_steps=steps-updates, amp_initial_scale=1024, epochs_completed=epochs, last_validation=metrics, normalization=normalization,
                      peak_allocated_bytes=torch.cuda.max_memory_allocated(), peak_reserved_bytes=torch.cuda.max_memory_reserved())
        write_json(run / 'record.json', record)
        print('VALIDATED', epoch + 1, steps, metrics['primary'], 'full=', metrics['full_split'], flush=True)
        if stop or steps >= recipe['steps']:
            break
    selected = 'best.pt' if (run / 'best.pt').exists() else 'last.pt'
    record.update(status='budget_exhausted' if stop or steps >= recipe['steps'] else 'completed', checkpoint=selected,
                  checkpoint_sha256=digest(run / selected), is_reference=False,
                  eligible_reference=not recipe.get('smoke', False) and best >= 0,
                  selection_scope='full_validation' if best >= 0 else 'smoke_only_no_candidate_selection')
    write_json(run / 'record.json', record)


def child(run, data_root, active, log, verify=False):
    args = [sys.executable, str(ROOT / 'scripts/train.py'), '_worker', '--run', str(run), '--data-root', str(data_root)]
    if verify:
        args.append('--verify')
    remaining = active['seconds'] - (time.monotonic() - active['started_monotonic'])
    if remaining <= 0:
        raise TimeoutError('No wall budget remains')
    run_with_watchdog(args, remaining, log, {**os.environ, 'GOTRAIN_JOB_ID': active['run_id'], 'GOTRAIN_ALLOCATION': active['allocation']})


def run_with_watchdog(args, seconds, log, env=None):
    with log.open('a') as stream:
        process = subprocess.Popen(args, stdout=stream, stderr=subprocess.STDOUT,
                                   start_new_session=True, env=env)
        try:
            code = process.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
            raise TimeoutError('Hard wall watchdog terminated worker')
    if code:
        raise RuntimeError('Worker failed; see ' + str(log))


def main():
    if ROOT != Path('/home/sagemaker-user/GoTrain').resolve():
        raise RuntimeError('Use the canonical SageMaker GoTrain checkout so GPU lock and budget stay shared')
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    train = sub.add_parser('train'); train.add_argument('--recipe', type=Path, required=True); train.add_argument('--retry-of')
    verify = sub.add_parser('verify'); verify.add_argument('--run-id', required=True)
    internal = sub.add_parser('_worker', help=argparse.SUPPRESS); internal.add_argument('--run', type=Path, required=True); internal.add_argument('--verify', action='store_true')
    for command in (train, verify, internal):
        command.add_argument('--data-root', type=Path, required=True)
        command.add_argument('--allocation', choices=('m1', 'm2'), default='m1')
    args = parser.parse_args()
    if args.command == '_worker':
        try:
            worker(args.run, args.data_root, args.verify)
        except BaseException as exc:
            if not args.verify:
                record = read(args.run / 'record.json')
                reason = 'oom' if type(exc).__name__ == 'OutOfMemoryError' else 'transient' if isinstance(exc, ConnectionError) or isinstance(exc, OSError) and exc.errno in (errno.ETIMEDOUT, errno.ECONNRESET) else 'fatal'
                record.update(status='failed', error_type=type(exc).__name__, error=str(exc), retryable=reason)
                write_json(args.run / 'record.json', record)
            traceback.print_exc(); raise SystemExit(1)
        return
    caps, contracts = read(ROOT / ('configs/' + args.allocation + '.json')), read(ROOT / 'configs/tasks.json')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    runs = ROOT / 'artifacts/runs'; runs.mkdir(parents=True, exist_ok=True)
    if args.command == 'train':
        recipe = read(args.recipe); validate_recipe(recipe, contracts, caps)
        run_id = stamp + '-' + recipe['task'] + ('-smoke' if recipe.get('smoke') else '-manual')
        run = runs / run_id; run.mkdir()
        category = 'foundation_smoke' if recipe.get('smoke') else 'four_reference_runs'
        if args.retry_of:
            parent = read(runs / Path(args.retry_of).name / 'record.json')
            if parent['status'] != 'failed' or parent.get('retry_of') or parent.get('retryable') not in ('oom', 'transient'):
                raise ValueError('Failure is not eligible for a linked retry')
            if recipe['task'] != parent['recipe']['task'] or parent['retryable'] == 'oom' and recipe['batch_size'] > parent['recipe']['batch_size'] // 2:
                raise ValueError('OOM retry must halve the original batch')
            category = 'failure_reserve'
        git = lambda *a: subprocess.check_output(['git', '-C', str(ROOT), *a], timeout=15).decode().strip()
        if git('ls-files', '--others', '--exclude-standard'):
            raise ValueError('Commit untracked source before starting a recorded run')
        patch = subprocess.check_output(['git', '-C', str(ROOT), 'diff', '--binary', 'HEAD'], timeout=15).decode()
        if patch:
            (run / 'source.patch').write_text(patch)
        record = {'run_id': run_id, 'status': 'created', 'created_utc': stamp, 'recipe': recipe,
                  'source_commit': git('rev-parse', 'HEAD'), 'dirty': bool(patch), 'seed': 2026,
                  'data_revision': contracts['dataset_revision'], 'partition_sha256': next(t['partition_sha256'] for t in read(ROOT / 'docs/data-inspection.json')['tasks'] if t['name'] == recipe['task']),
                  'task_contract_sha256': digest(ROOT / 'configs/tasks.json'), 'budget_contract_sha256': digest(ROOT / ('configs/' + args.allocation + '.json')),
                  'data_root': str(args.data_root.resolve()), 'retry_of': args.retry_of, 'is_reference': False}
        write_json(run / 'record.json', record)
        seconds = recipe['wall_seconds']
    else:
        run = runs / Path(args.run_id).name
        record = read(run / 'record.json'); run_id = record['run_id'] + '-verify-' + stamp
        category, seconds = 'checkpoint_revalidation', 60
    (run / 'run.log').touch(exist_ok=True)
    budget = Budget(ROOT, caps, read(ROOT / 'docs/calibration.json')['elapsed_seconds'], args.allocation)
    active = None
    try:
        active = budget.begin(run_id, category, seconds, getattr(args, 'retry_of', None))
        Guard(ROOT, run, caps, active['started_monotonic'] + seconds).check()
        child(run, args.data_root, active, run / ('verify.log' if args.command == 'verify' else 'run.log'), args.command == 'verify')
        if args.command == 'train' and recipe.get('smoke'):
            child(run, args.data_root, active, run / 'run.log', verify=True)
        status = 'verified' if args.command == 'verify' else read(run / 'record.json')['status']
    except BaseException as exc:
        status = 'failed'
        if args.command == 'train':
            record = read(run / 'record.json'); record.update(status='failed', controller_error=str(exc))
            write_json(run / 'record.json', record)
        raise
    finally:
        if active:
            elapsed = budget.finish(status)
            write_json(run / ('verify-timing-' + stamp + '.json' if args.command == 'verify' else 'timing.json'), {'elapsed_seconds': elapsed, 'ledger': 'artifacts/' + args.allocation + '-budget.json'})
        budget.close()
    print(json.dumps({'run_id': record['run_id'], 'status': status, 'smoke': record['recipe'].get('smoke', False)}))
