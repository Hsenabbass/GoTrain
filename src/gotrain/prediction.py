"""Standalone CPU inference runtime, also copied verbatim into model packages.

No training imports, initialization weights, network calls or CUDA admission.
"""
import argparse
import hashlib
import json
from pathlib import Path


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def verify_package(directory):
    directory = Path(directory).resolve()
    checks = json.loads((directory / 'checksums.json').read_text())
    expected = {'model.json', 'weights.pt', 'predict.py', 'requirements.txt', 'README.md', 'TERMS.md', 'history.json'}
    if set(checks) != expected or {p.name for p in directory.iterdir()} != expected | {'checksums.json'}:
        raise ValueError('Package contents differ from the versioned contract')
    for name, checksum in checks.items():
        path = directory / name
        if path.is_symlink() or not path.is_file() or digest(path) != checksum:
            raise ValueError('Package checksum mismatch: ' + name)
    meta = json.loads((directory / 'model.json').read_text())
    validate_metadata(meta)
    identity = {k: v for k, v in meta.items() if k != 'version'}
    version = 'v1-' + hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()[:24]
    if meta['version'] != version or meta['weights_sha256'] != checks['weights.pt']:
        raise ValueError('Model version/content mismatch')
    for field, name in (('runtime_sha256', 'predict.py'), ('dependencies_sha256', 'requirements.txt'), ('history_sha256', 'history.json'), ('terms_sha256', 'TERMS.md')):
        if meta[field] != checks[name]:
            raise ValueError('Versioned package component differs: ' + name)
    return meta


def validate_metadata(meta):
    import math
    if meta.get('schema_version') != 1 or meta.get('device') != 'cpu' or meta.get('precision') != 'float32':
        raise ValueError('Unsupported package runtime contract')
    spec = meta['task_spec']
    if spec['kind'] not in ('classification', 'segmentation'):
        raise ValueError('Unsupported prediction task')
    if any(type(spec[k]) is not int or spec[k] < (2 if k == 'classes' else 1) for k in ('classes', 'channels', 'height', 'width')):
        raise ValueError('Invalid input shape/classes')
    if spec['channels'] * spec['height'] * spec['width'] * 4 > 128 * 1024**2:
        raise ValueError('Input exceeds 128 MiB float32 sample cap')
    if len(spec['band_names']) != spec['channels'] or len(set(spec['band_names'])) != spec['channels']:
        raise ValueError('Explicit unique channel order required')
    if len(meta['class_names']) != spec['classes']:
        raise ValueError('Class mapping differs from output shape')
    norm = meta['normalization']
    for values, positive in ((spec['input_divisors'], True), (norm['mean'], False), (norm['std'], True)):
        if len(values) != spec['channels'] or any(not math.isfinite(v) or (positive and v <= 0) for v in values):
            raise ValueError('Invalid scaling/normalization')
    if norm.get('fitted_on') not in ('train', 'pretrained_rgb_train_extras'):
        raise ValueError('Unverified normalization origin')
    if meta['architecture'] not in ('resnet18', 'resnet18_imagenet', 'fcn_resnet50', 'fcn_imagenet', 'mobilenet_small_imagenet', 'deeplab_mobile_imagenet'):
        raise ValueError('Unsupported architecture')


def build_architecture(name, spec):
    import torch
    from torchvision import models
    from torchvision.models import segmentation
    if name in ('resnet18', 'resnet18_imagenet') and spec['kind'] == 'classification':
        model = models.resnet18(weights=None, num_classes=spec['classes'])
        stem, key = model, 'conv1'
    elif name == 'mobilenet_small_imagenet' and spec['kind'] == 'classification':
        model = models.mobilenet_v3_small(weights=None, num_classes=spec['classes'])
        stem, key = model.features[0], '0'
    elif name in ('fcn_resnet50', 'fcn_imagenet') and spec['kind'] == 'segmentation':
        model = segmentation.fcn_resnet50(weights=None, weights_backbone=None, num_classes=spec['classes'], aux_loss=False)
        stem, key = model.backbone, 'conv1'
    elif name == 'deeplab_mobile_imagenet' and spec['kind'] == 'segmentation':
        model = segmentation.deeplabv3_mobilenet_v3_large(weights=None, weights_backbone=None, num_classes=spec['classes'], aux_loss=False)
        stem, key = model.backbone['0'], '0'
    else:
        raise ValueError('Architecture/task mismatch')
    old = getattr(stem, key)
    if old.in_channels != spec['channels']:
        setattr(stem, key, torch.nn.Conv2d(spec['channels'], old.out_channels, old.kernel_size, old.stride, old.padding, bias=False))
    return model


class Predictor:
    def __init__(self, directory):
        import torch
        self.directory = Path(directory)
        self.metadata = verify_package(directory)
        torch.set_num_threads(4)
        self.model = build_architecture(self.metadata['architecture'], self.metadata['task_spec'])
        self.model.load_state_dict(torch.load(self.directory / 'weights.pt', map_location='cpu', weights_only=True), strict=True)
        self.model.eval()

    def prepare(self, pixels, band_names, input_divisors):
        import numpy as np
        import torch
        spec = self.metadata['task_spec']
        if band_names != spec['band_names'] or input_divisors != spec['input_divisors']:
            raise ValueError('Input channel order or units differ; use the model.json input contract')
        pixels = np.asarray(pixels)
        if pixels.shape != (spec['channels'], spec['height'], spec['width']) or pixels.dtype.kind not in 'uif':
            raise ValueError('Expected numeric CHW pixels with shape ' + str((spec['channels'], spec['height'], spec['width'])))
        x = torch.as_tensor(pixels.copy(), dtype=torch.float32)
        if not torch.isfinite(x).all():
            raise ValueError('Input contains missing or non-finite pixels')
        x = x / torch.tensor(spec['input_divisors'])[:, None, None]
        norm = self.metadata['normalization']
        return (x - torch.tensor(norm['mean'])[:, None, None]) / torch.tensor(norm['std'])[:, None, None]

    def logits(self, pixels, band_names, input_divisors):
        import torch
        x = self.prepare(pixels, band_names, input_divisors)
        with torch.inference_mode():
            output = self.model(x[None])
        logits = output['out'] if isinstance(output, dict) else output
        spec = self.metadata['task_spec']
        expected = (1, spec['classes'], spec['height'], spec['width']) if spec['kind'] == 'segmentation' else (1, spec['classes'])
        if tuple(logits.shape) != expected or not torch.isfinite(logits).all():
            raise ValueError('Invalid prediction logits')
        return logits[0]

    def predict(self, pixels, band_names, input_divisors):
        logits = self.logits(pixels, band_names, input_divisors)
        spec = self.metadata['task_spec']
        if spec['kind'] == 'classification':
            probabilities = logits.softmax(0).tolist()
            selected = int(logits.argmax(0))
            return {'version': self.metadata['version'], 'class_id': selected,
                    'class_name': self.metadata['class_names'][selected], 'probabilities': probabilities,
                    'probabilities_calibrated': False}
        return logits.argmax(0).numpy().astype('uint16')


def load_image(path, spec):
    import numpy as np
    path = Path(path)
    geo = None
    if path.suffix.lower() in ('.tif', '.tiff'):
        import rasterio
        with rasterio.open(path) as src:
            if (src.count, src.height, src.width) != (spec['channels'], spec['height'], spec['width']):
                raise ValueError('GeoTIFF dimensions/channels differ from model.json')
            if not (src.read_masks() > 0).all():
                raise ValueError('Missing pixels are not supported')
            pixels = src.read()
            geo = {'crs': src.crs, 'transform': src.transform}
    elif path.suffix.lower() in ('.png', '.jpg', '.jpeg'):
        from PIL import Image
        with Image.open(path) as image:
            if image.size != (spec['width'], spec['height']) or image.mode not in ('RGB', 'L'):
                raise ValueError('Expected native-size RGB or grayscale image; no automatic conversion/resizing')
            pixels = np.array(image)
        pixels = pixels[None] if pixels.ndim == 2 else pixels.transpose(2, 0, 1)
    else:
        raise ValueError('Use a compatible PNG, JPEG or GeoTIFF image')
    return pixels, geo


def save_mask(mask, pixels, metadata, directory, geo=None, opacity=0.45):
    import numpy as np
    from PIL import Image
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    Image.fromarray(mask).save(directory / 'mask.png')
    if geo:
        import rasterio
        with rasterio.open(directory / 'mask.tif', 'w', driver='GTiff', height=mask.shape[0], width=mask.shape[1], count=1, dtype='uint16', **geo) as dst:
            dst.write(mask, 1)
    palette = np.array([[(53 + i * 97) % 256, (131 + i * 61) % 256, (211 + i * 43) % 256] for i in range(metadata['task_spec']['classes'])], dtype='uint8')
    preview = palette[mask]
    Image.fromarray(preview).save(directory / 'preview.png')
    rgb = metadata['task_spec'].get('rgb_indices')
    if rgb is not None:
        # Fixed display stretch only; inference pixels are never stretched.
        image = pixels[rgb].astype('float32').transpose(1, 2, 0)
        lo, hi = np.percentile(image, (2, 98), axis=(0, 1))
        image = np.clip((image - lo) / np.maximum(hi - lo, 1e-6), 0, 1) * 255
        Image.fromarray(((1 - opacity) * image + opacity * preview).astype('uint8')).save(directory / 'overlay.png')
    (directory / 'result.json').write_text(json.dumps({'version': metadata['version'], 'class_names': metadata['class_names'], 'colors': palette.tolist(), 'overlay_opacity': opacity}, indent=2))


def main():
    parser = argparse.ArgumentParser(description='CPU prediction using a verified GoTrain package')
    parser.add_argument('--package', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--input-contract', type=Path, required=True, help='JSON with band_names and input_divisors, declaring actual input semantics')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--opacity', type=float, default=0.45)
    args = parser.parse_args()
    if not 0 <= args.opacity <= 1:
        parser.error('opacity must be between 0 and 1')
    try:
        predictor = Predictor(args.package)
        pixels, geo = load_image(args.image, predictor.metadata['task_spec'])
        declared = json.loads(args.input_contract.read_text())
        result = predictor.predict(pixels, declared['band_names'], declared['input_divisors'])
        if isinstance(result, dict):
            with args.output.open('x') as stream:
                json.dump(result, stream, indent=2, allow_nan=False)
        else:
            save_mask(result, pixels, predictor.metadata, args.output, geo, args.opacity)
        print('Prediction saved:', args.output)
    except (ValueError, KeyError) as error:
        parser.exit(2, 'Incompatible input/package: ' + str(error) + '\n')


if __name__ == '__main__':
    main()
