"""Durable request preflight and bounded ZIP imports; no training entry point.

This module deliberately has no ML/agent imports. Full image validation is an
injected SageMaker adapter; semantic preflight is an injected bounded agent.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import threading
import time
import uuid
import zipfile


class RequestError(ValueError):
    def __init__(self, message, status=422):
        super().__init__(message)
        self.status = status


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.partial')
    try:
        with temp.open('x', encoding='utf-8') as stream:
            json.dump(value, stream, allow_nan=False, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def opaque(value, prefix):
    if not isinstance(value, str) or not re.fullmatch(prefix + r'_[0-9a-f]{32}', value):
        raise RequestError('Invalid ' + prefix + ' ID')
    return value


def safe_member(name):
    if not isinstance(name, str) or not name or '\\' in name or ':' in name or '\x00' in name:
        raise RequestError('Dataset paths must be relative POSIX paths')
    parts = PurePosixPath(name).parts
    if name.startswith('/') or any(part in ('.', '..') or part.startswith('.') for part in parts):
        raise RequestError('Unsafe or hidden dataset path')
    if any(part in ('__MACOSX',) for part in parts):
        raise RequestError('Remove operating-system metadata from the ZIP')
    return PurePosixPath(name).as_posix()


def validate_manifest(value):
    """Structural checks complement (not replace) the M3 full-sample adapter."""
    try:
        spec, splits = value['task'], value['splits']
        if not isinstance(spec, dict) or spec['kind'] not in ('classification', 'segmentation'):
            raise RequestError('Declare classification or segmentation in task.kind')
        allowed = {'kind', 'channels', 'height', 'width', 'classes', 'class_names', 'band_names',
                   'rgb_indices', 'input_divisors', 'primary_metric', 'ignore_index', 'description'}
        if set(value) != {'task', 'splits'} or set(spec) - allowed:
            raise RequestError('Unknown manifest/task fields; use the supported schema')
        if not isinstance(spec.get('description', ''), str) or len(spec.get('description', '')) > 1000:
            raise RequestError('Dataset description must be at most 1000 characters')
        for key in ('channels', 'height', 'width', 'classes'):
            if type(spec[key]) is not int or not 1 <= spec[key] <= {'channels': 64, 'height': 4096, 'width': 4096, 'classes': 256}[key]:
                raise RequestError('Invalid task.' + key)
        if spec['classes'] < 2:
            raise RequestError('At least two class IDs are required')
        if spec['channels'] * spec['height'] * spec['width'] * 4 > 128 * 2**20:
            raise RequestError('One decoded sample exceeds 128 MiB; prepare smaller fixed-size windows')
        names = spec['band_names']
        if not isinstance(names, list) or len(names) != spec['channels'] or any(not isinstance(n, str) or not n or len(n) > 80 for n in names) or len(set(names)) != len(names):
            raise RequestError('Declare unique band_names in storage order')
        divisors = spec['input_divisors']
        if not isinstance(divisors, list) or len(divisors) != spec['channels'] or any(type(n) not in (int, float) or not math.isfinite(n) or n <= 0 for n in divisors):
            raise RequestError('Declare a positive input_divisor for each channel')
        classes = spec.get('class_names')
        if not isinstance(classes, list) or len(classes) != spec['classes'] or any(not isinstance(n, str) or not n or len(n) > 100 for n in classes) or len(set(classes)) != len(classes):
            raise RequestError('Declare task.class_names in class-ID order')
        rgb = spec.get('rgb_indices')
        if not isinstance(rgb, list) or len(rgb) != 3 or any(type(i) is not int or not 0 <= i < spec['channels'] for i in rgb) or len(set(rgb)) != 3:
            raise RequestError('Verified rgb_indices are required for the reviewed pretrained models')
        metric = 'accuracy' if spec['kind'] == 'classification' else 'macro_iou'
        if spec.get('primary_metric') != metric or spec.get('ignore_index') is not None:
            raise RequestError('Use the supported primary metric and no ignored class IDs')
        if not isinstance(splits, dict) or set(splits) != {'train', 'valid'}:
            raise RequestError('Declare train and valid only; keep test data outside the upload')
        seen, files = set(), {'manifest.json'}
        for split, rows in splits.items():
            if not isinstance(rows, list) or not rows:
                raise RequestError('Both splits must be nonempty')
            for row in rows:
                image = safe_member(row['image'])
                if image in seen:
                    raise RequestError('Duplicate image membership across or within splits')
                if PurePosixPath(image).suffix.lower() not in ('.png', '.jpg', '.jpeg', '.tif', '.tiff'):
                    raise RequestError('Images must be PNG, JPEG or GeoTIFF')
                seen.add(image)
                files.add(image)
                if spec['kind'] == 'classification':
                    if type(row['label']) is not int or not 0 <= row['label'] < spec['classes']:
                        raise RequestError('Classification labels must be integer class IDs')
                else:
                    mask = safe_member(row['mask'])
                    if mask == image or PurePosixPath(mask).suffix.lower() not in ('.png', '.tif', '.tiff'):
                        raise RequestError('Masks must be separate lossless PNG/TIFF files')
                    files.add(mask)
        return spec, files
    except (KeyError, TypeError, AttributeError) as exc:
        raise RequestError('Incomplete manifest; include task metadata and labeled train/valid splits') from exc


def full_image_validation(manifest):
    """Runs only in the approved SageMaker runtime, using the existing M3 adapter."""
    from .data import ManifestData
    for split in ('train', 'valid'):
        data = ManifestData(manifest, split)
        for index in range(len(data)):
            row = data.rows[index]
            for key in ('image', 'mask'):
                if key not in row:
                    continue
                path = data.resolve(row[key])
                if path.suffix.lower() in ('.tif', '.tiff'):
                    import rasterio
                    with rasterio.open(path) as image:
                        dimensions, channels = (image.width, image.height), image.count
                else:
                    from PIL import Image
                    with Image.open(path) as image:
                        dimensions, channels = image.size, len(image.getbands())
                if dimensions != (data.spec['width'], data.spec['height']) or channels != (1 if key == 'mask' else data.spec['channels']):
                    raise RequestError('Image/mask shape or channel count differs from the manifest')
            data[index]  # Validates actual shape, channel count, targets and alignment.


class Requests:
    def __init__(self, root, caps, benchmarks, validator=full_image_validation, interpreter=None):
        self.root, self.caps, self.benchmarks = Path(root), caps, benchmarks
        self.validator, self.interpreter = validator, interpreter
        self.root.mkdir(parents=True, exist_ok=True)
        for folder in ('datasets', 'conversations', 'uploads'):
            (self.root / folder).mkdir(exist_ok=True)
        self.thread_lock = threading.RLock()

    @contextmanager
    def locked(self):
        # Refuse unresolved interprocess locks rather than risk duplicate spending.
        with self.thread_lock:
            lock = self.root / 'request.lock'
            try:
                fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError as exc:
                raise RequestError('Request store busy or interrupted; retry or ask the operator to audit the lock', 409) from exc
            try:
                os.write(fd, str(os.getpid()).encode())
                yield
            finally:
                os.close(fd)
                lock.unlink()

    def save(self, record):
        record['updated_utc'] = datetime.now(timezone.utc).isoformat()
        atomic_json(self.root / 'conversations' / (record['id'] + '.json'), record)

    def get(self, conversation):
        opaque(conversation, 'conversation')
        path = self.root / 'conversations' / (conversation + '.json')
        if not path.exists():
            raise RequestError('Conversation not found', 404)
        return read_json(path)

    def conversations(self):
        """Return a compact, newest-first index without exposing request internals."""
        rows = []
        for path in (self.root / 'conversations').glob('conversation_*.json'):
            try:
                record = read_json(path)
                first = next((item.get('content', '') for item in record.get('messages', [])
                              if item.get('role') == 'user'), 'Untitled request')
                title = ' '.join(first.split()) or 'Untitled request'
                rows.append({'id': record['id'], 'title': title[:80],
                             'status': record.get('status', 'draft'),
                             'updated_at': record.get('updated_utc'),
                             'dataset_id': record.get('dataset_id')})
            except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
                continue
        return sorted(rows, key=lambda row: row.get('updated_at') or '', reverse=True)

    def dataset(self, dataset):
        if dataset in self.benchmarks:
            return self.benchmarks[dataset]
        opaque(dataset, 'dataset')
        path = self.root / 'datasets' / dataset / 'record.json'
        if not path.exists():
            raise RequestError('Dataset not found', 404)
        return read_json(path)

    def import_zip(self, archive):
        archive = Path(archive)
        if archive.stat().st_size > self.caps['upload_bytes']:
            raise RequestError('Dataset ZIP exceeds the compressed upload limit', 413)
        started = time.monotonic()
        dataset_id = 'dataset_' + uuid.uuid4().hex
        staging = self.root / 'datasets' / (dataset_id + '.partial')
        staging.mkdir()
        try:
            with zipfile.ZipFile(archive) as package:
                members = package.infolist()
                if len(members) > self.caps['file_count']:
                    raise RequestError('Dataset ZIP has too many files', 413)
                names, all_names, declared = {}, set(), 0
                for member in members:
                    name = safe_member(member.filename.rstrip('/'))
                    if name.casefold() in all_names:
                        raise RequestError('Duplicate or normalized-duplicate ZIP path')
                    all_names.add(name.casefold())
                    mode = member.external_attr >> 16
                    if member.flag_bits & 1 or stat.S_ISLNK(mode) or stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR):
                        raise RequestError('Encrypted files, links and special files are unsupported')
                    if member.is_dir():
                        continue
                    if name != 'manifest.json' and PurePosixPath(name).suffix.lower() not in ('.png', '.jpg', '.jpeg', '.tif', '.tiff'):
                        raise RequestError('ZIP may contain only manifest.json and referenced images/masks')
                    names[name] = member
                    declared += member.file_size
                if declared > self.caps['expanded_bytes']:
                    raise RequestError('Expanded dataset exceeds the limit', 413)
                if 'manifest.json' not in names or names['manifest.json'].file_size > self.caps['manifest_bytes']:
                    raise RequestError('A bounded manifest.json is required at the ZIP root')
                value = json.loads(package.read(names['manifest.json']))
                spec, required = validate_manifest(value)
                if set(names) != required:
                    raise RequestError('ZIP contents must exactly match the manifest; missing or unreferenced files found')
                if shutil.disk_usage(self.root).free < declared + self.caps['disk_reserve_bytes']:
                    raise RequestError('Insufficient space after the required disk reserve', 507)
                total = 0
                for name, member in names.items():
                    target = staging / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with package.open(member) as src, target.open('xb') as dst:
                        while chunk := src.read(1024 * 1024):
                            total += len(chunk)
                            if total > self.caps['expanded_bytes'] or time.monotonic() - started > self.caps['import_seconds']:
                                raise RequestError('Dataset expansion exceeded its size/time allowance', 413)
                            if shutil.disk_usage(self.root).free - len(chunk) < self.caps['disk_reserve_bytes']:
                                raise RequestError('Disk reserve reached while extracting', 507)
                            dst.write(chunk)
            self.validator(staging / 'manifest.json')
            if time.monotonic() - started > self.caps['import_seconds']:
                raise RequestError('Dataset validation exceeded its time allowance', 413)
            sha = hashlib.sha256()
            with archive.open('rb') as src:
                for chunk in iter(lambda: src.read(1024 * 1024), b''):
                    sha.update(chunk)
            record = {'id': dataset_id, 'source': 'manifest_zip', 'sha256': sha.hexdigest(),
                      'task': spec, 'counts': {key: len(rows) for key, rows in value['splits'].items()},
                      'compressed_bytes': archive.stat().st_size, 'expanded_bytes': total,
                      'status': 'validated', 'created_utc': datetime.now(timezone.utc).isoformat()}
            atomic_json(staging / 'record.json', record)
            staging.rename(self.root / 'datasets' / dataset_id)
            return record
        except BaseException:
            # Only this newly-created, verified child directory can be removed.
            if staging.resolve().parent == (self.root / 'datasets').resolve():
                shutil.rmtree(staging)
            raise

    def validate_limits(self, requested):
        if not isinstance(requested, dict) or set(requested) - self.caps['limits'].keys():
            raise RequestError('Unknown request limits')
        limits = {}
        for key, rule in self.caps['limits'].items():
            value = requested.get(key, rule['default'])
            if type(value) is not int or not 0 < value <= rule['maximum']:
                raise RequestError('Invalid or excessive ' + key)
            limits[key] = value
        if limits['gpu_seconds'] > limits['runtime_seconds']:
            raise RequestError('GPU allowance cannot exceed total runtime')
        return limits

    def submit(self, message, request_id, dataset_id=None, limits=None, conversation=None):
        if not isinstance(message, str) or not 1 <= len(message.strip()) <= self.caps['message_chars']:
            raise RequestError('Provide a nonempty task message within the length limit')
        opaque(request_id, 'request')
        limits = self.validate_limits(limits or {})
        fingerprint = hashlib.sha256(json.dumps([message, dataset_id, limits, conversation], sort_keys=True).encode()).hexdigest()
        with self.locked():
            index_path = self.root / 'request-index.json'
            index = read_json(index_path) if index_path.exists() else {}
            if request_id in index:
                entry = index[request_id]
                if entry['fingerprint'] != fingerprint:
                    raise RequestError('Request ID already used for different content', 409)
                return self.get(entry['conversation'])
            if conversation:
                record = self.get(conversation)
                if record['status'] == 'checking':
                    raise RequestError('Preflight already active or interrupted; operator must reconcile before retry', 409)
                if record['status'] in ('ready_for_review', 'running', 'stopping', 'ready'):
                    raise RequestError('This request is frozen; create a new draft for a different task', 409)
                if dataset_id not in (None, record['dataset_id']) or limits != record['limits']:
                    raise RequestError('Replies must preserve the draft dataset and limits', 409)
            else:
                record = {'id': 'conversation_' + uuid.uuid4().hex, 'status': 'draft',
                          'dataset_id': dataset_id, 'limits': limits, 'messages': [],
                          'model_requests': 0, 'preflight_requests': 0, 'usage_receipts': []}
            if len(record['messages']) >= self.caps['max_messages']:
                raise RequestError('Conversation message limit reached')
            data = self.dataset(record['dataset_id']) if record['dataset_id'] else None
            record['messages'].append({'role': 'user', 'content': message.strip(),
                                       'created_at': datetime.now(timezone.utc).isoformat()})
            record.update(status='needs_input', questions=[], error=None)
            index[request_id] = {'fingerprint': fingerprint, 'conversation': record['id']}
            self.save(record)
            atomic_json(index_path, index)
            if record['preflight_requests'] >= min(self.caps['max_preflight_requests'], record['limits']['model_requests']):
                record['questions'] = ['Preflight request allowance exhausted; the operator must review this draft.']
                self.save(record)
                return record
            if self.interpreter is None:
                record['questions'] = ['Agent access is unavailable. Your message is saved; no training has started.']
                self.save(record)
                return record
            nonce = uuid.uuid4().hex
            context = {'messages': record['messages'], 'dataset': data,
                       'benchmarks': self.benchmarks, 'limits': record['limits']}
            prompt = getattr(self.interpreter, 'system_prompt', 'explicit_test_interpreter')
            record.update(status='checking', preflight_nonce=nonce,
                          prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
                          context_sha256=hashlib.sha256(json.dumps(context, sort_keys=True).encode()).hexdigest())
            self.save(record)

        def reserve():
            with self.locked():
                fresh = self.get(record['id'])
                if fresh.get('preflight_nonce') != nonce or fresh['status'] != 'checking':
                    raise RequestError('Preflight ownership changed', 409)
                if fresh['preflight_requests'] >= min(self.caps['max_preflight_requests'], fresh['limits']['model_requests']):
                    raise RequestError('Preflight request cap reached')
                fresh['preflight_requests'] += 1
                fresh['model_requests'] += 1
                self.save(fresh)  # Charge before every wire call, including failed calls.

        def receipt(usage):
            with self.locked():
                fresh = self.get(record['id'])
                fresh['usage_receipts'].append(usage)
                self.save(fresh)

        decision = None
        try:
            decision = self.interpreter(context, reserve, receipt)
            with self.locked():
                fresh = self.get(record['id'])
                fresh['preflight_decision'] = decision
                self.apply_decision(fresh, decision)
                self.save(fresh)
                return fresh
        except Exception as exc:
            with self.locked():
                fresh = self.get(record['id'])
                fresh.update(status='needs_input', error=type(exc).__name__,
                             error_detail=str(exc)[:500] if isinstance(exc, RequestError) else 'Provider or validation failure',
                             preflight_decision=decision,
                             questions=['Preflight could not finish. The request is saved and no training started.'])
                self.save(fresh)
                return fresh

    def apply_decision(self, record, decision):
        allowed = {'status', 'dataset_id', 'kind', 'goal', 'questions', 'constraints'}
        if not isinstance(decision, dict) or set(decision) != allowed or decision['status'] not in ('ready', 'needs_input'):
            raise RequestError('Invalid preflight decision schema')
        if not isinstance(decision['questions'], list) or len(decision['questions']) > 4 or any(not isinstance(q, str) or not 1 <= len(q) <= 500 for q in decision['questions']):
            raise RequestError('Invalid clarification questions')
        if not isinstance(decision['goal'], str) or len(decision['goal']) > 1000:
            raise RequestError('Invalid resolved goal')
        constraints = decision['constraints']
        if not isinstance(constraints, dict) or set(constraints) - self.caps['limits'].keys():
            raise RequestError('Invalid interpreted constraints')
        for key, value in constraints.items():
            if type(value) is not int or not 0 < value <= record['limits'][key]:
                raise RequestError('Text cannot increase the approved limits')
        if record['dataset_id'] and decision['dataset_id'] not in (None, record['dataset_id']):
            raise RequestError('Preflight cannot replace an attached dataset')
        dataset_id = record['dataset_id'] or decision['dataset_id']
        data = self.dataset(dataset_id) if dataset_id else None
        questions = decision['questions'][:]
        if not data:
            questions.append('Attach a manifest ZIP or name one of the four prepared benchmark datasets.')
        elif decision['kind'] != data['task']['kind']:
            questions.append('The requested output must match the dataset labels: ' + data['task']['kind'] + '.')
        limits = self.validate_limits({**record['limits'], **constraints})
        if (limits['runtime_seconds'] < self.caps['minimum_runtime_seconds']
                or limits['gpu_seconds'] < self.caps['minimum_gpu_seconds']
                or limits['model_requests'] - record['model_requests'] < self.caps['minimum_model_requests']):
            questions.append('The proposed workflow needs at least 780 seconds runtime, 660 GPU seconds and six remaining model requests. No job was admitted.')
        if decision['status'] == 'needs_input' and not questions:
            questions.append('Clarify the desired output and how it relates to the dataset labels.')
        if not decision['goal'].strip():
            questions.append('Describe the desired model output.')
        record.update(dataset_id=dataset_id, questions=questions, goal=decision['goal'], proposed_limits=limits,
                      status='needs_input' if questions else 'ready_for_review')
        if questions:
            record['messages'].append({'role': 'assistant', 'content': '\n'.join(questions),
                                       'created_at': datetime.now(timezone.utc).isoformat()})
        if not questions:
            record['summary'] = {'dataset_id': dataset_id, 'dataset_version': data['sha256'],
                                 'task': data['task'], 'counts': data['counts'], 'goal': decision['goal'],
                                 'limits': limits, 'validation_only': True}
            record['reviewed_at'] = datetime.now(timezone.utc).isoformat()

    def reconcile_interrupted_preflights(self):
        """Operator-only recovery: never reissue a potentially charged model call."""
        with self.locked():
            for path in (self.root / 'conversations').glob('conversation_*.json'):
                record = read_json(path)
                if record['status'] == 'checking':
                    record.update(status='needs_input', error='interrupted_preflight',
                                  questions=['Preflight was interrupted; reply to continue. All charged requests are retained.'])
                    self.save(record)


def benchmark_registry(repo):
    repo = Path(repo)
    contracts = read_json(repo / 'configs/tasks.json')
    inspection = read_json(repo / 'docs/data-inspection.json')
    version = hashlib.sha256((repo / 'configs/tasks.json').read_bytes()).hexdigest()
    return {task_id: {'id': task_id, 'source': 'benchmark', 'status': 'validated',
                     'sha256': contracts['dataset_revision'] + ':' + version, 'task': spec,
                     'counts': next(row['split_counts'] for row in inspection['tasks'] if row['name'] == task_id)}
            for task_id, spec in contracts['tasks'].items()}
