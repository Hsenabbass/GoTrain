"""Verified package publication and bounded CPU prediction, independent of the UI."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

from .requests import atomic_json, read_json, RequestError
from .prediction import digest, verify_package

ROOT = Path(__file__).resolve().parents[2]

VERIFY = r'''
import ctypes,os,signal,sys
assert ctypes.CDLL(None).prctl(1,signal.SIGKILL,0,0,0)==0
assert os.getppid()==int(sys.argv[6])
signal.alarm(60)
import importlib.util,json,pathlib,numpy as np,torch
package,image,contract,expected,checkout=sys.argv[1:6]
def audit(event,args):
 if event in ('socket.connect','socket.getaddrinfo','socket.bind'): raise RuntimeError('Offline verification: network denied')
 if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
  path=pathlib.Path(os.fsdecode(args[0])).resolve()
  if path.is_relative_to(pathlib.Path(checkout)) or path.is_relative_to(pathlib.Path('/home/sagemaker-user/.cache/torch')): raise RuntimeError('Checkout/cache access denied')
sys.addaudithook(audit)
def blocked(*a,**k): raise RuntimeError('Initialization download denied')
torch.hub.load_state_dict_from_url=blocked
torch.hub.download_url_to_file=blocked
module=importlib.util.spec_from_file_location('standalone',pathlib.Path(package)/'predict.py')
runtime=importlib.util.module_from_spec(module); module.loader.exec_module(runtime)
predictor=runtime.Predictor(package)
pixels,_=runtime.load_image(image,predictor.metadata['task_spec'])
actual=predictor.logits(pixels,**json.load(open(contract))).numpy()
reference=np.load(expected,allow_pickle=False)
assert np.allclose(actual,reference,atol=1e-5,rtol=1e-5)
assert np.array_equal(actual.argmax(0),reference.argmax(0))
print(json.dumps({'passed':True,'max_logit_delta':float(np.max(np.abs(actual-reference))),'class_ids_exact':True,'atol':1e-5,'rtol':1e-5,'network_checkout_cache_denied':True}))
'''


def registry(root):
    path = Path(root)/'artifacts/models/registry.json'
    return read_json(path) if path.exists() else {}


def publish(root, receipt, dataset):
    root = Path(root)
    folder = root/'artifacts/models'/(receipt['task']+'-'+receipt['version'])
    meta = verify_package(folder)
    archive = root/'artifacts/models'/receipt['archive']
    if meta['version']!=receipt['version'] or digest(archive)!=receipt['sha256']:
        raise ValueError('Package publication checksum/version mismatch')
    value = {**receipt,'dataset':dataset,'task_spec':meta['task_spec'],
             'class_names':meta['class_names'],'validation':meta['validation'],
             'selection_status':meta['selection_status']}
    import fcntl
    with (root/'artifacts/models/registry.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        records = registry(root)
        if receipt['version'] in records and records[receipt['version']]!=value:
            raise ValueError('Cannot replace an immutable model version')
        records[receipt['version']] = value
        atomic_json(root/'artifacts/models/registry.json',records)
    return value


def register_retained(root):
    """Reuse 4.1's verified receipts; no re-export, inference or retraining."""
    root = Path(root)
    evidence = read_json(root/'docs/m4-evidence.json')['packages']['verification']['models']
    from .requests import benchmark_registry
    datasets = benchmark_registry(root)
    records = registry(root)
    for row in evidence:
        if row['version'] in records:
            continue
        receipt = {k:row[k] for k in ('version','task','run_id','archive','sha256','bytes','redistribution_status')}
        receipt['verification'] = {k:row[k] for k in ('passed','logit_max_absolute_delta','class_ids_exact')}
        publish(root,receipt,datasets[row['task']])


def model_record(root, version):
    if not re.fullmatch(r'v1-[0-9a-f]{24}',version):
        raise RequestError('Invalid model version',404)
    value = registry(root).get(version)
    if not value:
        raise RequestError('Verified model version not found',404)
    return value


def package_path(root, version):
    value = model_record(root,version)
    path = Path(root)/'artifacts/models'/value['archive']
    if path.parent.resolve()!=(Path(root)/'artifacts/models').resolve() or path.is_symlink() or digest(path)!=value['sha256']:
        raise RequestError('Package integrity check failed; operator review required',409)
    return path


def example_pixels(root, data, spec):
    """One approved validation example. Never opens a test split or label payload."""
    import numpy as np
    if data['source']=='benchmark':
        from .data import DevelopmentData
        root = Path(root)
        valid = DevelopmentData(root/'data/geo-bench/datasets',data['id'],'valid',read_json(root/'configs/tasks.json'),read_json(root/'docs/data-inspection.json'),limit=1)
        sample = valid.dataset[0]
        return np.stack([band.data for band in sample.bands]), None
    from .m4 import open_frozen
    from .prediction import load_image
    valid = open_frozen(root,{'dataset':data},'valid',limit=1)
    return load_image(valid.resolve(valid.rows[0]['image']),spec)


def finalize(root, controller):
    """Publish only after extracted-package CPU output matches the originating model."""
    import numpy as np
    import torch
    from .models import CANDIDATES, build_candidate, build_model, logits_for
    from .data import prepare
    from .packages import export_package
    root = Path(root); runner = controller.runner
    controller.lease.check_time(controller.lease.owned()[1])
    record = runner.result(runner.best)
    run = root/'artifacts/runs'/runner.best
    saved = torch.load(run/record['checkpoint'],map_location='cpu',weights_only=True)
    data = runner.frozen['dataset']; spec = saved['meta']['task_spec']
    existing = next((v for v in registry(root).values() if v['run_id']==runner.best and v['dataset']['sha256']==data['sha256']),None)
    if existing:
        package_path(root,existing['version'])
        return {k:v for k,v in existing.items() if k!='dataset'}
    names = spec.get('class_names')
    if names is None:
        origin = next(t for t in read_json(root/'docs/data-inspection.json')['tasks'] if t['name']==data['id'])
        names = origin['label_metadata'].get('_class_names') or [None]*spec['classes']
    charges = {row['id']:row['elapsed_seconds'] for row in controller.lease.owned()[1].get('trials',[])}
    history = {'selected_run':runner.best,'decisions':controller.state['decisions'],
               'experiments':[{**{k:r[k] for k in ('run_id','recipe','status','best_validation','parent_run','hypothesis','error_type') if k in r},
                               'gpu_job_seconds':charges.get(r.get('m4_trial_id'))}
                              for r in (runner.result(name) for name in runner.runs)]}
    dataset = {'id':data['id'],'revision':runner.contracts['dataset_revision'],
               'contract_sha256':runner.contract_hash,'registered_version':data['sha256']}
    receipt = export_package(run,root/'artifacts/models',class_names=names,history=history,dataset=dataset)
    receipt['label'] = runner.frozen['summary']['goal'][:200]
    model = (build_candidate(record['recipe']['model'],spec,root/'artifacts/weights/m3'/record['weight_receipt']['filename'],record['weight_receipt'],record['recipe']['head_only'])
             if record['recipe']['model'] in CANDIDATES else build_model(record['recipe']['model'],spec))
    model.load_state_dict(saved['model'],strict=True); model.eval(); torch.set_num_threads(4)
    pixels, geo = example_pixels(root,data,spec)
    target = np.zeros((spec['height'],spec['width']),dtype='int64') if spec['kind']=='segmentation' else np.int64(0)
    x,_ = prepare(pixels,target,spec,saved['meta']['normalization'])
    with torch.inference_mode(): expected = logits_for(model,x[None],spec)[0].numpy()
    with tempfile.TemporaryDirectory(prefix='gotrain-delivery-') as temporary:
        temp = Path(temporary)
        with zipfile.ZipFile(root/'artifacts/models'/receipt['archive']) as archive:
            archive.extractall(temp)
        package = temp/(receipt['task']+'-'+receipt['version'])
        import rasterio
        image = temp/'example.tif'
        with rasterio.open(image,'w',driver='GTiff',height=spec['height'],width=spec['width'],count=spec['channels'],dtype=pixels.dtype,**(geo or {})) as dst: dst.write(pixels)
        (temp/'input.json').write_text(json.dumps({k:spec[k] for k in ('band_names','input_divisors')}))
        np.save(temp/'expected.npy',expected,allow_pickle=False)
        (temp/'verify.py').write_text(VERIFY)
        remaining = controller.lease.owned()[1]['runtime_seconds']-(controller.lease.clock()-controller.lease.owned()[1]['started_monotonic'])
        result = subprocess.run([sys.executable,'-I',str(temp/'verify.py'),str(package),str(image),str(temp/'input.json'),str(temp/'expected.npy'),str(root),str(os.getpid())],cwd=temp,
                                env={**os.environ,'CUDA_VISIBLE_DEVICES':'','TORCH_HOME':str(temp/'empty-cache')},capture_output=True,text=True,timeout=max(1,min(60,remaining)))
        if result.returncode:
            raise RuntimeError('Standalone verification failed: '+result.stderr[-600:])
        receipt['verification'] = json.loads(result.stdout.splitlines()[-1])
    controller.lease.check_time(controller.lease.owned()[1])
    publish(root,receipt,data)
    return receipt


def predict(root, version, output, *, image=None, declaration=None, example=False):
    import time
    from .runtime import Guard
    from .prediction import Predictor, load_image, save_mask
    root, output = Path(root), Path(output)
    Guard(root,output,read_json(root/'configs/m3.json'),time.monotonic()+60).check(extra_storage=128*2**20)
    record = model_record(root,version)
    predictor = Predictor(root/'artifacts/models'/(record['task']+'-'+version))
    if example:
        pixels, geo = example_pixels(root,record['dataset'],record['task_spec'])
        declaration = {k:record['task_spec'][k] for k in ('band_names','input_divisors')}
    else:
        pixels, geo = load_image(image,record['task_spec'])
    result = predictor.predict(pixels,**declaration)
    if isinstance(result,dict):
        output.mkdir(parents=True,exist_ok=False)
        atomic_json(output/'result.json',result)
    else:
        save_mask(result,pixels,predictor.metadata,output,geo)
    if sum(path.stat().st_size for path in output.iterdir())>128*2**20:
        raise ValueError('Prediction output exceeded 128 MiB')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('version'); parser.add_argument('output',type=Path)
    parser.add_argument('--image',type=Path); parser.add_argument('--declaration',type=Path)
    parser.add_argument('--example',action='store_true')
    args = parser.parse_args()
    if ROOT!=Path('/home/sagemaker-user/GoTrain'): raise RuntimeError('Use SageMaker')
    from .m4 import protect_parent
    protect_parent(int(os.environ['GOTRAIN_PREDICTION_PARENT']))
    import signal
    signal.alarm(60)
    try:
        predict(ROOT,args.version,args.output,image=args.image,
                declaration=read_json(args.declaration) if args.declaration else None,example=args.example)
    except Exception as exc:
        parser.exit(2,'Input/package mismatch: '+str(exc).replace(str(args.image),'uploaded image')[:500]+'\n')


if __name__=='__main__': main()
