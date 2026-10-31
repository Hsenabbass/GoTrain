"""SageMaker CPU verification of retained packages; no retraining/test access."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

# This child is outside the checkout. Network, original checkout/cache reads and
# initialization weight retrieval are denied, rather than merely unnecessary.
CHILD = r'''
import importlib.util, json, os, pathlib, runpy, sys
import numpy as np
import torch
package, image, contract, output, reference, source = sys.argv[1:]
def audit(event, args):
    if event in ('socket.connect', 'socket.getaddrinfo', 'socket.bind'):
        raise RuntimeError('Network access denied in standalone verification')
    if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
        path = pathlib.Path(os.fsdecode(args[0])).resolve()
        if path.is_relative_to(pathlib.Path(source)) or path.is_relative_to(pathlib.Path('/home/sagemaker-user/.cache/torch')):
            raise RuntimeError('Checkout/initialization cache access denied')
sys.addaudithook(audit)
def blocked(*a, **k): raise RuntimeError('Initialization download/cache access denied')
torch.hub.load_state_dict_from_url = blocked
torch.hub.download_url_to_file = blocked
module = importlib.util.spec_from_file_location('standalone_predict', pathlib.Path(package)/'predict.py')
runtime = importlib.util.module_from_spec(module); module.loader.exec_module(runtime)
predictor = runtime.Predictor(package)
declared = json.load(open(contract))
pixels, geo = runtime.load_image(image, predictor.metadata['task_spec'])
logits = predictor.logits(pixels, **declared).numpy()
expected = np.load(reference, allow_pickle=False)
assert np.allclose(logits, expected, atol=1e-5, rtol=1e-5), float(np.max(np.abs(logits-expected)))
assert np.array_equal(logits.argmax(0), expected.argmax(0))
for bad in (pixels[:, :-1], pixels[:1]):
    try: predictor.predict(bad, **declared)
    except ValueError: pass
    else: raise AssertionError('Invalid shape accepted')
try: predictor.predict(pixels, list(reversed(declared['band_names'])), declared['input_divisors'])
except ValueError: pass
else: raise AssertionError('Wrong channel order accepted')
sys.argv = ['predict.py', '--package', package, '--image', image, '--input-contract', contract, '--output', output]
runpy.run_path(str(pathlib.Path(package)/'predict.py'), run_name='__main__')
if predictor.metadata['task_spec']['kind'] == 'segmentation':
    import rasterio
    from PIL import Image
    result = pathlib.Path(output)
    mask = np.array(Image.open(result/'mask.png'))
    assert np.array_equal(mask, expected.argmax(0))
    assert mask.min() >= 0 and mask.max() < predictor.metadata['task_spec']['classes']
    with rasterio.open(result/'mask.tif') as src:
        assert src.crs == geo['crs'] and src.transform == geo['transform']
        assert np.array_equal(src.read(1), mask)
else:
    result = json.load(open(output))
    assert result['class_id'] == int(expected.argmax(0))
    assert abs(sum(result['probabilities'])-1) < 1e-5
print(json.dumps({'passed': True, 'logit_max_absolute_delta': float(np.max(np.abs(logits-expected))), 'class_ids_exact': True, 'network_checkout_cache_denied': True}))
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--packages', type=Path, default=ROOT / 'artifacts/models')
    parser.add_argument('--data-root', type=Path, default=ROOT / 'data/geo-bench/datasets')
    parser.add_argument('--evidence', type=Path, default=ROOT / 'artifacts/runs/m4-package-checks')
    args = parser.parse_args()
    import numpy as np
    import torch
    import rasterio
    from rasterio.transform import from_origin
    from gotrain.data import DevelopmentData
    from gotrain.models import build_candidate, logits_for
    from gotrain.packages import export_retained
    from gotrain.prediction import digest
    torch.set_num_threads(4)
    started = time.monotonic()
    args.evidence.mkdir(parents=True, exist_ok=True)
    before = {name: digest(ROOT / ('artifacts/' + name + '-budget.json')) for name in ('m1', 'm2', 'm3')}
    receipts = export_retained(args.packages)
    (args.evidence / 'exports.json').write_text(json.dumps(receipts, indent=2))
    contracts = json.loads((ROOT / 'configs/tasks.json').read_text())
    inspection = json.loads((ROOT / 'docs/data-inspection.json').read_text())
    report = []
    for receipt in receipts:
        run = ROOT / 'artifacts/runs' / receipt['run_id']
        record = json.loads((run / 'record.json').read_text())
        saved = torch.load(run / record['checkpoint'], weights_only=True, map_location='cpu')
        spec = saved['meta']['task_spec']
        # Original M3 architecture path, independently of packaged reconstruction.
        model = build_candidate(record['recipe']['model'], spec,
                                ROOT / 'artifacts/weights/m3' / record['weight_receipt']['filename'],
                                record['weight_receipt'], record['recipe']['head_only'])
        model.load_state_dict(saved['model'], strict=True)
        model.eval()
        valid = DevelopmentData(args.data_root, receipt['task'], 'valid', contracts, inspection, limit=1)
        valid.normalization = saved['meta']['normalization']
        x, _ = valid[0]
        with torch.inference_mode():
            expected = logits_for(model, x[None], spec)[0].numpy()
        sample = valid.dataset[0]
        raw = np.stack([band.data for band in sample.bands])
        with tempfile.TemporaryDirectory(prefix='gotrain-standalone-') as temp:
            temp = Path(temp)
            with zipfile.ZipFile(args.packages / receipt['archive']) as archive:
                archive.extractall(temp)
            package = temp / (receipt['task'] + '-' + receipt['version'])
            image = temp / 'validation-example.tif'
            transform = from_origin(100, 200, 2, 2)
            with rasterio.open(image, 'w', driver='GTiff', height=spec['height'], width=spec['width'], count=spec['channels'], dtype=raw.dtype, crs='EPSG:32636', transform=transform) as dst:
                dst.write(raw)
            declaration = {k: spec[k] for k in ('band_names', 'input_divisors')}
            (temp / 'input.json').write_text(json.dumps(declaration))
            np.save(temp / 'expected.npy', expected, allow_pickle=False)
            (temp / 'verify.py').write_text(CHILD)
            env = {k: v for k, v in os.environ.items() if k not in ('PYTHONPATH', 'PYTHONSTARTUP')}
            env.update(TORCH_HOME=str(temp / 'empty-torch-cache'), CUDA_VISIBLE_DEVICES='', PYTHONNOUSERSITE='1')
            result = subprocess.run([sys.executable, '-I', str(temp / 'verify.py'), str(package), str(image), str(temp / 'input.json'), str(temp / 'result'), str(temp / 'expected.npy'), str(ROOT)], cwd=temp, env=env, capture_output=True, text=True, timeout=180)
            (args.evidence / (receipt['task'] + '.log')).write_text(result.stdout + result.stderr)
            if result.returncode:
                raise RuntimeError(receipt['task'] + ': ' + result.stderr[-2000:])
            check = json.loads(result.stdout.splitlines()[-1])
        report.append({**receipt, **check, 'approved_example': {'split': 'valid', 'index': 0, 'partition_sha256': next(t['partition_sha256'] for t in inspection['tasks'] if t['name'] == receipt['task'])}, 'comparison': 'CPU float32 original M3 builder versus extracted standalone runtime', 'logit_atol': 1e-5, 'logit_rtol': 1e-5})
        print(receipt['task'], 'PASSED', flush=True)
    after = {name: digest(ROOT / ('artifacts/' + name + '-budget.json')) for name in before}
    assert before == after, 'Historical ledgers changed'
    output = {'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(), 'passed': True, 'models': report, 'seconds': time.monotonic()-started, 'device': 'cpu', 'gpu_jobs': 0, 'test_payloads_opened': 0, 'historical_ledgers_unchanged': before, 'full_validation': 'Reused M3 evidence; no repeated full-validation or test evaluation', 'redistribution': 'Unresolved: private workspace verification only, no public weight distribution'}
    (args.evidence / 'evidence.json').write_text(json.dumps(output, indent=2))
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
