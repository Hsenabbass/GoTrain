"""Non-ML request/service checks. Agent and full image decoder are explicit doubles.

Run this file independently on a laptop; existing ML tests still run on SageMaker.
"""
import copy
import io
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
import uuid
import zipfile
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from gotrain.requests import Requests, RequestError, read_json, validate_manifest
from gotrain.service import create_app


def request_id():
    return 'request_' + uuid.uuid4().hex


def manifest(kind='classification'):
    return {'task': {'kind': kind, 'channels': 3, 'height': 32, 'width': 32,
                     'classes': 2, 'class_names': ['background', 'solar_panel'],
                     'band_names': ['R', 'G', 'B'], 'rgb_indices': [0, 1, 2],
                     'input_divisors': [255, 255, 255], 'ignore_index': None,
                     'primary_metric': 'accuracy' if kind == 'classification' else 'macro_iou'},
            'splits': {split: [{'image': split + '.png', **({'label': 1} if kind == 'classification' else {'mask': split + '-mask.png'})}]
                       for split in ('train', 'valid')}}


def zip_bytes(value=None, extra=None):
    value = value or manifest()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as package:
        package.writestr('manifest.json', json.dumps(value))
        for split, rows in value['splits'].items():
            for row in rows:
                package.writestr(row['image'], b'EXPLICIT_DECODER_TEST_DOUBLE')
                if 'mask' in row:
                    package.writestr(row['mask'], b'EXPLICIT_MASK_TEST_DOUBLE')
        if extra:
            for name, body in extra:
                package.writestr(name, body)
    return buf.getvalue()


def decision(status='ready', kind='classification', dataset='m-eurosat', questions=None, constraints=None):
    return {'status': status, 'kind': kind, 'dataset_id': dataset,
            'goal': 'Classify the labeled imagery.', 'questions': questions or [],
            'constraints': constraints or {}}


class RequestChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.caps = read_json(ROOT / 'configs/service.json')
        self.caps['disk_reserve_bytes'] = 0
        self.benchmarks = {'m-eurosat': {'id': 'm-eurosat', 'task': manifest()['task'],
                                       'counts': {'train': 4, 'valid': 2}, 'sha256': 'frozen-test-contract'}}
        self.decoded = []
        def decoder(path):
            self.decoded.append(str(path))
        self.store = Requests(self.root, self.caps, self.benchmarks, validator=decoder)

    def tearDown(self):
        self.temp.cleanup()

    def agent(self, output):
        def call(context, reserve, receipt):
            reserve()
            receipt({'usage': {'inputTokens': 5, 'outputTokens': 2}})
            return copy.deepcopy(output)
        self.store.interpreter = call

    def archive(self, body):
        path = self.root / 'upload.zip'
        path.write_bytes(body)
        return path

    def test_classification_and_segmentation_imports_use_decoder_and_opaque_ids(self):
        for kind in ('classification', 'segmentation'):
            result = self.store.import_zip(self.archive(zip_bytes(manifest(kind))))
            self.assertEqual(result['status'], 'validated')
            self.assertEqual(self.store.dataset(result['id']), result)
            self.assertEqual(result['counts'], {'train': 1, 'valid': 1})
        self.assertEqual(len(self.decoded), 2)

    def test_archive_traversal_nested_archives_and_extra_files_rejected_before_decode(self):
        for name in ('../evil.png', 'C:/evil.png', 'nested.zip', 'run.py', 'unreferenced.png', 'a\\evil.png'):
            with self.assertRaises(RequestError):
                self.store.import_zip(self.archive(zip_bytes(extra=[(name, b'x')])))
        self.assertEqual(self.decoded, [])
        self.assertEqual(list((self.root / 'datasets').iterdir()), [])

    def test_zip_symlink_and_case_collision_rejected(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as package:
            link = zipfile.ZipInfo('link.png')
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            package.writestr(link, '../outside')
        with self.assertRaises(RequestError):
            self.store.import_zip(self.archive(buf.getvalue()))
        with self.assertRaises(RequestError):
            self.store.import_zip(self.archive(zip_bytes(extra=[('TRAIN.PNG', b'x')])))

    def test_size_filecount_and_decoder_failure_leave_no_registered_dataset(self):
        for key in ('upload_bytes', 'expanded_bytes', 'file_count'):
            original = self.caps[key]
            self.caps[key] = 1
            with self.assertRaises(RequestError):
                self.store.import_zip(self.archive(zip_bytes()))
            self.caps[key] = original
        def invalid(_path):
            raise RequestError('Actual image shape mismatch')
        self.store.validator = invalid
        with self.assertRaisesRegex(RequestError, 'shape'):
            self.store.import_zip(self.archive(zip_bytes()))
        self.assertEqual(list((self.root / 'datasets').iterdir()), [])

    def test_bad_labels_splits_scales_and_missing_class_names(self):
        values = []
        value = manifest(); value['splits']['valid'] = value['splits']['train']; values.append(value)
        value = manifest(); value['splits']['test'] = []; values.append(value)
        value = manifest(); value['splits']['train'][0]['label'] = True; values.append(value)
        value = manifest(); value['task']['input_divisors'][0] = 0; values.append(value)
        value = manifest(); del value['task']['class_names']; values.append(value)
        value = manifest(); value['task']['rgb_indices'] = [0, 0, 2]; values.append(value)
        for value in values:
            with self.assertRaises(RequestError):
                validate_manifest(value)

    def test_duplicate_submit_is_idempotent_and_content_change_conflicts(self):
        self.agent(decision())
        key = request_id()
        first = self.store.submit('classify land cover', key)
        second = self.store.submit('classify land cover', key)
        self.assertEqual(first, second)
        self.assertEqual(second['model_requests'], 1)
        self.assertEqual(first['status'], 'ready_for_review')
        with self.assertRaises(RequestError):
            self.store.submit('different goal', key)

    def test_clarification_preserves_dataset_limits_and_charge_after_restart(self):
        self.agent(decision('needs_input', questions=['Which class should the model predict?']))
        first = self.store.submit('help with this dataset', request_id(), 'm-eurosat')
        self.assertEqual(first['status'], 'needs_input')
        self.store = Requests(self.root, self.caps, self.benchmarks)
        self.agent(decision())
        second = self.store.submit('Predict the provided class labels.', request_id(), conversation=first['id'])
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(second['dataset_id'], 'm-eurosat')
        self.assertEqual(first['limits'], second['limits'])
        self.assertEqual(second['model_requests'], 2)
        self.assertEqual(len(second['messages']), 3)
        self.assertEqual(second['messages'][1]['role'], 'assistant')
        self.assertTrue(all(message.get('created_at') for message in second['messages']))
        self.assertEqual(second['status'], 'ready_for_review')

    def test_late_saved_dataset_preserves_draft_and_duplicate_reply_charge(self):
        self.agent(decision('needs_input', dataset=None, questions=['Attach data.']))
        first = self.store.submit('Classify the image labels.', request_id())
        self.assertIsNone(first['dataset_id'])
        self.agent(decision())
        key = request_id()
        second = self.store.submit('Use these labels.', key, 'm-eurosat',
                                   conversation=first['id'])
        again = self.store.submit('Use these labels.', key, 'm-eurosat',
                                  conversation=first['id'])
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(first['limits'], second['limits'])
        self.assertEqual(second['dataset_id'], 'm-eurosat')
        self.assertEqual(second['model_requests'], 2)
        self.assertEqual(second, again)
        self.assertEqual(len(second['messages']), 3)
        with self.assertRaises(RequestError):
            self.store.submit('Change frozen request.', request_id(), 'm-eurosat',
                              conversation=second['id'])

    def test_late_attachment_rejects_invalid_ids_replacements_and_limit_changes(self):
        self.agent(decision('needs_input', dataset=None, questions=['Attach data.']))
        first = self.store.submit('Classify the image labels.', request_id())
        for dataset, limits in [('dataset_' + '0' * 32, None),
                                ('m-eurosat', {'attempts': 1})]:
            with self.assertRaises(RequestError):
                self.store.submit('Use data.', request_id(), dataset, limits,
                                  conversation=first['id'])
        unchanged = self.store.get(first['id'])
        self.assertIsNone(unchanged['dataset_id'])
        self.assertEqual(unchanged['model_requests'], first['model_requests'])
        self.agent(decision('needs_input', questions=['Clarify the target.']))
        bound = self.store.submit('Use these labels.', request_id(), 'm-eurosat',
                                  conversation=first['id'])
        with self.assertRaises(RequestError):
            self.store.submit('Replace dataset.', request_id(), 'm-brick-kiln',
                              conversation=bound['id'])
        self.assertEqual(self.store.get(bound['id'])['model_requests'], 2)

    def test_four_wire_calls_are_a_persistent_cap_even_on_failure(self):
        def broken(_context, reserve, _receipt):
            reserve()
            raise ConnectionError('No response')
        self.store.interpreter = broken
        record = None
        for _ in range(5):
            record = self.store.submit('classify', request_id(), conversation=record['id'] if record else None)
        self.assertEqual(record['preflight_requests'], 4)
        self.assertEqual(record['model_requests'], 4)
        self.assertIn('exhausted', record['questions'][0])

    def test_instruction_conflict_forged_ids_and_budget_increase_never_ready(self):
        for output in (decision(kind='segmentation'), decision(dataset='../bad'),
                       decision(constraints={'runtime_seconds': 99999}),
                       decision(constraints={'runtime_seconds': 800, 'gpu_seconds': 900})):
            self.agent(output)
            record = self.store.submit('request', request_id())
            self.assertEqual(record['status'], 'needs_input')
            self.assertNotIn('summary', record)

    def test_unsupported_schema_and_infeasible_limits_block_training_proposal(self):
        self.agent({**decision(), 'shell': 'do something'})
        record = self.store.submit('classify', request_id())
        self.assertEqual(record['status'], 'needs_input')
        self.agent(decision(constraints={'runtime_seconds': 100, 'gpu_seconds': 90}))
        record = self.store.submit('classify', request_id())
        self.assertEqual(record['status'], 'needs_input')
        self.assertIn('780 seconds', record['questions'][0])

    def test_interrupted_preflight_requires_explicit_reconciliation_without_refund(self):
        self.agent(decision('needs_input', questions=['Clarify']))
        record = self.store.submit('classify', request_id())
        record['status'] = 'checking'
        self.store.save(record)
        with self.assertRaises(RequestError):
            self.store.submit('reply', request_id(), conversation=record['id'])
        self.store.reconcile_interrupted_preflights()
        after = self.store.get(record['id'])
        self.assertEqual(after['model_requests'], 1)
        self.assertEqual(after['error'], 'interrupted_preflight')

    def test_opaque_ids_and_unknown_or_boolean_limits_rejected(self):
        for identifier in ('../record', 'conversation_bad', '/etc/passwd'):
            with self.assertRaises(RequestError): self.store.get(identifier)
        for limits in ({'shell': 1}, {'gpu_seconds': True}, {'attempts': 6}):
            with self.assertRaises(RequestError): self.store.submit('classify', request_id(), limits=limits)

    def test_api_origin_strict_limits_and_disabled_start(self):
        self.agent(decision())
        self.caps['training_enabled'] = False
        with TestClient(create_app(self.store)) as client:
            payload = {'message': 'classify land cover', 'request_id': request_id()}
            self.assertEqual(client.post('/api/conversations', json=payload).status_code, 403)
            self.assertEqual(client.post('/api/conversations', json=payload, headers={'X-GoTrain-Request': '1', 'Origin': 'https://other.invalid'}).status_code, 403)
            headers = {'X-GoTrain-Request': '1'}
            response = client.post('/api/conversations', json=payload, headers=headers)
            self.assertEqual(response.status_code, 200, response.text)
            record = response.json()
            history = client.get('/api/conversations').json()
            self.assertEqual(history[0]['id'], record['id'])
            self.assertEqual(history[0]['title'], 'classify land cover')
            self.assertEqual(client.get('/api/conversations/' + record['id']).json(), record)
            self.assertEqual(client.post('/api/conversations/' + record['id'] + '/start', headers=headers).status_code, 409)
            bad = {**payload, 'request_id': request_id(), 'limits': {'attempts': True}}
            self.assertEqual(client.post('/api/conversations', json=bad, headers=headers).status_code, 422)
            self.assertFalse(client.get('/api/health').json()['training_enabled'])

    def test_api_stream_upload_examples_and_prefix_relative_assets(self):
        prefix = '/jupyterlab/default/proxy/8766'
        with TestClient(create_app(self.store), root_path=prefix) as client:
            headers = {'X-GoTrain-Request': '1', 'Content-Type': 'application/zip'}
            response = client.post(prefix + '/api/datasets', content=zip_bytes(), headers=headers)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(len(client.get(prefix + '/api/datasets').json()), 2)
            for kind in ('classification', 'segmentation'):
                archive = client.get(prefix + '/api/examples/' + kind + '.zip')
                with zipfile.ZipFile(io.BytesIO(archive.content)) as package:
                    validate_manifest(json.loads(package.read('manifest.json')))
            html = client.get(prefix + '/').text
            self.assertIn('src="src/app.js"', html)
            self.assertNotIn('src="/src/app.js"', html)
            self.assertEqual(client.get(prefix + '/src/app.js').status_code, 200)


@unittest.skipUnless(sys.platform == 'linux' and ROOT == Path('/home/sagemaker-user/GoTrain'),
                     'Real image-adapter checks run only on canonical SageMaker')
class SageMakerImageChecks(unittest.TestCase):
    def test_full_actual_image_validation_for_both_task_types(self):
        import numpy as np
        from PIL import Image
        from gotrain.requests import full_image_validation
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            caps = read_json(ROOT / 'configs/service.json')
            for kind in ('classification', 'segmentation'):
                buf = io.BytesIO()
                value = manifest(kind)
                with zipfile.ZipFile(buf, 'w') as archive:
                    archive.writestr('manifest.json', json.dumps(value))
                    for split in ('train', 'valid'):
                        pixels = io.BytesIO()
                        Image.fromarray(np.full((32, 32, 3), 128, np.uint8)).save(pixels, format='PNG')
                        archive.writestr(split + '.png', pixels.getvalue())
                        if kind == 'segmentation':
                            pixels = io.BytesIO()
                            Image.fromarray(np.zeros((32, 32), np.uint8)).save(pixels, format='PNG')
                            archive.writestr(split + '-mask.png', pixels.getvalue())
                path = root / (kind + '.zip')
                path.write_bytes(buf.getvalue())
                store = Requests(root / kind, caps, {}, validator=full_image_validation)
                record = store.import_zip(path)
                self.assertEqual(record['status'], 'validated')
                # Real decoding must reject a mismatched image, not just metadata.
                directory = store.root / 'datasets' / record['id']
                Image.fromarray(np.zeros((16, 16, 3), np.uint8)).save(directory / 'train.png')
                with self.assertRaisesRegex(ValueError, 'shape'):
                    full_image_validation(directory / 'manifest.json')


if __name__ == '__main__':
    unittest.main()
