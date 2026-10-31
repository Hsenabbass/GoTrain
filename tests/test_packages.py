"""Package contract checks; ML behavior executes only on SageMaker."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from gotrain.prediction import validate_metadata, verify_package


class PackageContractTests(unittest.TestCase):
    def setUp(self):
        self.meta = {'schema_version': 1, 'device': 'cpu', 'precision': 'float32',
                     'architecture': 'resnet18_imagenet', 'class_names': ['a', 'b'],
                     'task_spec': {'kind': 'classification', 'channels': 3, 'height': 8, 'width': 8,
                                   'classes': 2, 'band_names': ['R', 'G', 'B'], 'input_divisors': [255]*3},
                     'normalization': {'mean': [0]*3, 'std': [1]*3, 'fitted_on': 'train'}}

    def test_metadata_requires_explicit_preprocessing(self):
        validate_metadata(self.meta)
        for key, value in [('input_divisors', [0]*3), ('band_names', ['R']*3), ('height', 100000000)]:
            meta = copy.deepcopy(self.meta)
            meta['task_spec'][key] = value
            with self.assertRaises(ValueError):
                validate_metadata(meta)

    def test_normalization_is_finite_and_train_derived(self):
        for key, value in [('std', [0]*3), ('mean', [float('nan')]*3), ('fitted_on', 'valid')]:
            meta = copy.deepcopy(self.meta)
            meta['normalization'][key] = value
            with self.assertRaises(ValueError):
                validate_metadata(meta)

    def test_integrity_and_version_cannot_silently_change(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            for name in ('weights.pt', 'predict.py', 'requirements.txt', 'README.md', 'TERMS.md', 'history.json'):
                (directory / name).write_bytes(b'contract fixture, not real weights')
            self.meta['weights_sha256'] = hashlib.sha256((directory / 'weights.pt').read_bytes()).hexdigest()
            for field, name in (('runtime_sha256', 'predict.py'), ('dependencies_sha256', 'requirements.txt'), ('history_sha256', 'history.json'), ('terms_sha256', 'TERMS.md')):
                self.meta[field] = hashlib.sha256((directory / name).read_bytes()).hexdigest()
            self.meta['version'] = 'v1-' + hashlib.sha256(json.dumps(self.meta, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()[:24]
            (directory / 'model.json').write_text(json.dumps(self.meta))
            checks = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.iterdir()}
            (directory / 'checksums.json').write_text(json.dumps(checks))
            verify_package(directory)
            (directory / '__pycache__').mkdir()
            verify_package(directory)  # Ordinary Python imports create this directory.
            (directory / 'weights.pt').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'checksum'):
                verify_package(directory)
            checks['weights.pt'] = hashlib.sha256(b'changed').hexdigest()
            (directory / 'checksums.json').write_text(json.dumps(checks))
            with self.assertRaisesRegex(ValueError, 'version/content'):
                verify_package(directory)


if __name__ == '__main__':
    unittest.main()
