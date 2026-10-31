"""Same-origin request/import API. Training admission intentionally stays disabled.

Serve only on loopback behind the existing authenticated SageMaker proxy.
Local mode is an explicit non-agent development preview, never a cloud substitute.
"""
import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
import zipfile

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from .requests import Requests, RequestError, benchmark_registry, read_json

ROOT = Path(__file__).resolve().parents[2]
CANONICAL = Path('/home/sagemaker-user/GoTrain')


class Message(BaseModel):
    model_config = ConfigDict(extra='forbid')
    message: str = Field(min_length=1, max_length=4000)
    request_id: str
    dataset_id: str | None = None
    conversation_id: str | None = None
    limits: dict[str, StrictInt] = Field(default_factory=dict)


def validate_on_sagemaker(manifest):
    # Image decoding is untrusted CPU work: a separate process has a hard deadline.
    command = [sys.executable, '-c',
               'import sys;sys.path.insert(0,sys.argv[1]);from gotrain.requests import full_image_validation;full_image_validation(sys.argv[2])',
               str(ROOT / 'src'), str(manifest)]
    try:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=90)
    except subprocess.TimeoutExpired as exc:
        raise RequestError('Image validation exceeded 90 seconds; use a smaller prepared dataset', 413) from exc
    if result.returncode:
        raise RequestError('Image validation failed: ' + result.stderr[-600:])


def example_zip(kind):
    """Downloadable schema template only; explicitly not a labeled training dataset."""
    task = {'kind': kind, 'channels': 3, 'height': 64, 'width': 64, 'classes': 2,
            'class_names': ['background', 'solar_panel'], 'band_names': ['R', 'G', 'B'],
            'rgb_indices': [0, 1, 2], 'input_divisors': [255, 255, 255],
            'primary_metric': 'accuracy' if kind == 'classification' else 'macro_iou', 'ignore_index': None}
    rows = {split: [{'image': split + '/image.png', **({'label': 1} if kind == 'classification' else {'mask': split + '/mask.png'})}]
            for split in ('train', 'valid')}
    value = {'task': task, 'splits': rows}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as package:
        package.writestr('manifest.json', json.dumps(value, indent=2))
        package.writestr('README.txt', 'SCHEMA TEMPLATE ONLY. Add your labeled images/masks and remove this README before upload.\nTrain and valid files must be different. Change metadata to match your actual data.\n')
    return buf.getvalue()


def create_app(store=None, *, local=False):
    caps = read_json(ROOT / 'configs/service.json')
    if store is None:
        if not local and ROOT.resolve() != CANONICAL.resolve():
            raise RuntimeError('Live service runs only in the canonical SageMaker checkout')
        from .preflight import BedrockPreflight
        store = Requests(ROOT / 'artifacts/service', caps, benchmark_registry(ROOT),
                         validator=validate_on_sagemaker,
                         interpreter=None if local else BedrockPreflight())
    caps = store.caps
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.state.store = store
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='dataset-import')
    import_lock = asyncio.Lock()

    @app.exception_handler(RequestError)
    async def request_error(_request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=exc.status)

    @app.middleware('http')
    async def same_origin(request: Request, call_next):
        if request.method not in ('GET', 'HEAD'):
            if request.headers.get('x-gotrain-request') != '1' or request.headers.get('sec-fetch-site') == 'cross-site':
                return JSONResponse({'detail': 'Use the same-origin GoTrain client'}, status_code=403)
            origin = request.headers.get('origin')
            expected = os.environ.get('GOTRAIN_ORIGIN') or str(request.base_url).rstrip('/')
            # Prefix is not part of an Origin.
            from urllib.parse import urlsplit
            parsed = urlsplit(expected)
            expected = parsed.scheme + '://' + parsed.netloc
            if origin and origin != expected:
                return JSONResponse({'detail': 'Origin does not match this workspace'}, status_code=403)
            if request.url.path.endswith('/api/conversations'):
                length = request.headers.get('content-length', '')
                if not length.isdigit() or int(length) > 65536:
                    return JSONResponse({'detail': 'JSON request requires Content-Length at most 64 KiB'}, status_code=413)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        return response

    @app.get('/api/health')
    def health():
        return {'service': 'gotrain', 'preflight_enabled': store.interpreter is not None,
                'training_enabled': False, 'upload_bytes': caps['upload_bytes'],
                'scope': 'request_validation', 'limits': caps['limits']}

    @app.get('/api/datasets')
    def datasets():
        records = list(store.benchmarks.values())
        records += [read_json(path) for path in (store.root / 'datasets').glob('dataset_*/record.json')]
        return records

    @app.get('/api/examples/{kind}.zip')
    def template(kind: str):
        if kind not in ('classification', 'segmentation'):
            raise RequestError('Unsupported task type', 404)
        return Response(example_zip(kind), media_type='application/zip',
                        headers={'Content-Disposition': 'attachment; filename="' + kind + '-template.zip"'})

    @app.post('/api/datasets')
    async def upload(request: Request):
        if local:
            raise RequestError('Full dataset validation requires the SageMaker runtime', 503)
        if request.headers.get('content-type', '').split(';')[0] != 'application/zip':
            raise RequestError('Upload a manifest ZIP using application/zip')
        length = request.headers.get('content-length')
        if length and (not length.isdigit() or int(length) > caps['upload_bytes']):
            raise RequestError('Dataset ZIP exceeds the compressed upload limit', 413)
        if import_lock.locked():
            raise RequestError('Another dataset import is active; retry when it finishes', 409)
        await import_lock.acquire()
        path = store.root / 'uploads' / (uuid.uuid4().hex + '.zip')
        total = 0
        deferred_cleanup = False
        try:
            async with asyncio.timeout(caps['import_seconds']):
                with path.open('xb') as target:
                    async for chunk in request.stream():
                        total += len(chunk)
                        if total > caps['upload_bytes']:
                            raise RequestError('Dataset ZIP exceeds the compressed upload limit', 413)
                        if shutil.disk_usage(store.root).free - len(chunk) < caps['disk_reserve_bytes']:
                            raise RequestError('Disk reserve reached during upload', 507)
                        target.write(chunk)
            future = pool.submit(store.import_zip, path)
            try:
                return await asyncio.shield(asyncio.wrap_future(future))
            except asyncio.CancelledError:
                # A disconnect does not release the import slot while CPU work
                # still owns the file. No second decompression can be queued.
                loop = asyncio.get_running_loop()
                def cleanup(_future):
                    path.unlink(missing_ok=True)
                    loop.call_soon_threadsafe(import_lock.release)
                future.add_done_callback(cleanup)
                deferred_cleanup = True
                raise
            except (zipfile.BadZipFile, json.JSONDecodeError, UnicodeError) as exc:
                raise RequestError('Invalid ZIP or manifest JSON') from exc
        except TimeoutError as exc:
            raise RequestError('Dataset upload timed out', 408) from exc
        finally:
            if not deferred_cleanup:
                path.unlink(missing_ok=True)
                import_lock.release()

    @app.post('/api/conversations')
    def message(value: Message):
        return store.submit(value.message, value.request_id, value.dataset_id,
                            value.limits, value.conversation_id)

    @app.get('/api/conversations/{conversation_id}')
    def conversation(conversation_id: str):
        return store.get(conversation_id)

    @app.post('/api/conversations/{conversation_id}/start')
    def start(conversation_id: str):
        store.get(conversation_id)
        raise RequestError('Training admission is not enabled: the M4 runner and durable supervisor integration must be verified first. No GPU job was launched.', 409)

    @app.get('/')
    def index():
        return FileResponse(ROOT / 'ui/index.html')

    app.mount('/src', StaticFiles(directory=ROOT / 'ui/src'), name='ui')
    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--root-path', default='')
    parser.add_argument('--local-preview', action='store_true')
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('Use an unprivileged port')
    import uvicorn
    uvicorn.run(create_app(local=args.local_preview), host='127.0.0.1', root_path=args.root_path,
                port=args.port, access_log=False, log_level='warning')


if __name__ == '__main__':
    main()
