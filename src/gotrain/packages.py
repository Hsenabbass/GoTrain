"""Trusted checkpoint to immutable, standalone prediction package export."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import shutil
import tempfile
import zipfile

from .prediction import digest, validate_metadata, verify_package

ROOT = Path(__file__).resolve().parents[2]
DEPENDENCIES = ('torch', 'torchvision', 'numpy', 'Pillow', 'rasterio')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


TERMS = '''# Provenance and distribution restrictions

These are GoTrain research/hackathon model artifacts, selected using validation
only, with single-seed provisional gains. They are not M5 test-finalized models.

Architecture implementations are from TorchVision (BSD-3-Clause):
https://github.com/pytorch/vision/blob/v0.24.0/LICENSE
Initialization backbone and weight provenance are recorded in model.json.
TorchVision explicitly warns that pretrained weights may carry separate dataset
terms: https://docs.pytorch.org/vision/0.24/models.html#general-information-on-pre-trained-weights
ImageNet use/terms: https://www.image-net.org/download.php
Benchmark source and individual dataset provenance:
https://github.com/ServiceNow/geo-bench

Review result: public redistribution permission for the derived weights has NOT
been established. The TorchVision code license is not treated as a weight license.
These artifacts remain private to the existing authorized research workspace and
its recovery custodian. Do not publish/distribute the weight ZIPs externally or
claim commercial permission until ImageNet and the originating task's dataset
terms are resolved. No license for third-party data/weights is granted here.
No dataset or example image is included. Names/URLs are attribution and provenance,
not an endorsement. Known ImageNet held-out overlap remains unknown, as in M3.
'''


def export_package(run, destination, *, class_names, history, dataset, terms=TERMS):
    """Operator API: run is trusted server state, never a client-supplied path.

Supports the common task spec used by future custom-task runs; no benchmark-ID
assumption. Export does not train, score, promote or finalize the model.
"""
    import torch
    run, destination = Path(run), Path(destination)
    record = json.loads((run / 'record.json').read_text())
    checkpoint_name = record['checkpoint']
    if checkpoint_name not in ('best.pt', 'last.pt'):
        raise ValueError('Expected a registered run checkpoint')
    checkpoint = run / checkpoint_name
    if digest(checkpoint) != record['checkpoint_sha256']:
        raise ValueError('Origin checkpoint checksum differs from run record')
    destination.mkdir(parents=True, exist_ok=True)
    # Reserve for weights, ZIP and staging without consuming the service's floor.
    if shutil.disk_usage(destination).free < 15 * 2**30 + 3 * checkpoint.stat().st_size:
        raise ValueError('Package export needs staging space above the 15 GiB reserve')
    saved = torch.load(checkpoint, map_location='cpu', weights_only=True)
    meta = saved['meta']
    if meta['recipe'] != record['recipe'] or meta['seed'] != 2026:
        raise ValueError('Checkpoint recipe/primary seed differs from retained run')
    if not meta['validation'].get('full_split') or meta['validation'].get('split') != 'valid':
        raise ValueError('Only fully validated checkpoints can become selected versions')
    if dataset['contract_sha256'] != meta['contract_sha256']:
        raise ValueError('Dataset contract does not match checkpoint')
    if len(class_names) != meta['task_spec']['classes'] or any(v is not None and not isinstance(v, str) for v in class_names):
        raise ValueError('Verified names or explicit null class names required')
    destination.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='package-', dir=destination))
    try:
        # Only inference tensors; never optimizer state or executable pickle objects.
        torch.save({k: v.detach().cpu() for k, v in saved['model'].items()}, stage / 'weights.pt')
        shutil.copyfile(Path(__file__).with_name('prediction.py'), stage / 'predict.py')
        requirements = ''.join(name + '==' + importlib.metadata.version(name) + '\n' for name in DEPENDENCIES)
        (stage / 'requirements.txt').write_text(requirements)
        (stage / 'TERMS.md').write_text(terms)
        (stage / 'history.json').write_text(json.dumps(history, indent=2, allow_nan=False))
        model = {'schema_version': 1, 'task': record['recipe']['task'],
                 'architecture': record['recipe']['model'], 'task_spec': meta['task_spec'],
                 'normalization': meta['normalization'], 'class_names': class_names,
                 'device': 'cpu', 'precision': 'float32', 'seed': meta['seed'],
                 'selection_status': 'validation_selected_not_test_finalized',
                 'run_id': record['run_id'], 'origin_checkpoint_sha256': record['checkpoint_sha256'],
                 'training_source_commit': record.get('source_commit'),
                 'dataset': dataset, 'validation': meta['validation'],
                 'weight_provenance': record.get('weight_receipt'),
                 'weights_sha256': digest(stage / 'weights.pt'),
                 'runtime_sha256': digest(stage / 'predict.py'),
                 'dependencies_sha256': digest(stage / 'requirements.txt'),
                 'history_sha256': digest(stage / 'history.json'), 'terms_sha256': digest(stage / 'TERMS.md'),
                 'redistribution_status': 'unresolved_private_research_only',
                 'prediction': 'softmax_then_argmax_lowest_id_ties',
                 'geometry': 'native_grid_no_resize_no_crop',
                 'input_contract': 'Caller explicitly declares stored channel order and divisors; no spectral inference'}
        validate_metadata(model)
        model['version'] = 'v1-' + hashlib.sha256(canonical(model).encode()).hexdigest()[:24]
        (stage / 'model.json').write_text(json.dumps(model, indent=2, allow_nan=False))
        (stage / 'README.md').write_text('''# GoTrain standalone model

Private research package; read TERMS.md before sharing. CPU float32 inference.
Use Python 3.12 and the tested SageMaker environment. requirements.txt records
observed direct dependencies; it is not a universal hardware or transitive lock.
Install dependencies through your normal approved environment provisioning first.
Prediction then requires no network, model cache, GEO-Bench, or GoTrain checkout.

Inspect model.json. Supply a compatible native-size PNG/JPEG/GeoTIFF and a separate
input.json declaring its actual `band_names` and `input_divisors` in stored order.
Copy those fields only when they accurately describe your image. No automatic
resizing, channel conversion, missing-pixel repair or geographic reprojection.

    python predict.py --image /path/image.tif --input-contract /path/input.json --output /new/path/result

Classification writes a new JSON file (probabilities are not calibrated).
Segmentation creates a new directory with mask.png (uint16 class IDs), preview.png,
overlay.png when RGB positions are known, and result.json with colors/legend.
mask.tif retains CRS/transform if the input supplies geographic metadata.
--opacity controls only the display overlay (0..1). No input image is bundled.
Unknown class names are explicit nulls; use verified numeric IDs.

Python callers may import Predictor from predict.py and call predict(pixels,
band_names, input_divisors) with numeric CHW pixels. No labels are needed.
checksums.json verifies package integrity, not publisher authenticity; compare the
ZIP checksum with a trusted registry/receipt before extracting any received ZIP.
''')
        checks = {p.name: digest(p) for p in stage.iterdir()}
        (stage / 'checksums.json').write_text(json.dumps(checks, indent=2))
        verify_package(stage)
        task = model['task']
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,79}', task):
            raise ValueError('Task needs a safe registered identifier')
        folder = destination / (task + '-' + model['version'])
        archive = destination / ('gotrain-' + task + '-' + model['version'] + '.zip')
        if folder.exists() or archive.exists():
            raise FileExistsError('Immutable version already exists; reuse it rather than overwrite')
        stage.rename(folder)
        try:
            with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as stream:
                for path in sorted(folder.iterdir()):
                    stream.write(path, folder.name + '/' + path.name)
        except Exception:
            if archive.exists():
                archive.unlink()
            raise
        receipt = {'version': model['version'], 'task': task, 'run_id': record['run_id'],
                   'archive': archive.name, 'sha256': digest(archive), 'bytes': archive.stat().st_size,
                   'redistribution_status': model['redistribution_status']}
        (destination / (archive.name + '.sha256')).write_text(receipt['sha256'] + '  ' + archive.name + '\n')
        return receipt
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def export_retained(destination):
    evidence = json.loads((ROOT / 'docs/m3-evidence.json').read_text())['searches']['results']
    inspection = json.loads((ROOT / 'docs/data-inspection.json').read_text())
    receipts = []
    for task in evidence:
        origin = next(t for t in inspection['tasks'] if t['name'] == task['task'])
        classes = json.loads((ROOT / 'configs/tasks.json').read_text())['tasks'][task['task']]['classes']
        names = origin['label_metadata'].get('_class_names') or [None] * classes
        dataset = {'id': task['task'], 'repository': 'recursix/geo-bench-1.0',
                   'revision': '1e5754337032f097396db62cc15a5ff88f4618e8',
                   'contract_sha256': digest(ROOT / 'configs/tasks.json'), 'partition_sha256': origin['partition_sha256']}
        history = {k: task[k] for k in ('task', 'selected_run', 'selected_primary', 'gain_status', 'trials', 'decisions', 'reload')}
        receipts.append(export_package(ROOT / 'artifacts/runs' / task['selected_run'], destination,
                                       class_names=names, history=history, dataset=dataset))
    return receipts


def main():
    parser = argparse.ArgumentParser(description='Export the four retained M3 models without retraining')
    parser.add_argument('--destination', type=Path, default=ROOT / 'artifacts/models')
    args = parser.parse_args()
    print(json.dumps(export_retained(args.destination), indent=2))


if __name__ == '__main__':
    main()
