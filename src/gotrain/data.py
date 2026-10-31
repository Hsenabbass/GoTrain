"""Registered development splits, fixed scaling and train-only preprocessing."""
import hashlib
import json
from pathlib import Path
import numpy as np
import torch


def require_split(split):
    if split not in ('train', 'valid'):
        raise ValueError('Only train and valid are permitted in M1')


def joint_transform(x, y, horizontal=False, turns=0):
    if horizontal:
        x = x.flip(-1)
        if y.ndim == 2:
            y = y.flip(-1)
    if turns:
        x = x.rot90(turns, (-2, -1))
        if y.ndim == 2:
            y = y.rot90(turns, (-2, -1))
    return x, y


def prepare(x, y, spec, normalization=None):
    x = torch.as_tensor(np.asarray(x).copy(), dtype=torch.float32)
    raw = np.asarray(y)
    if raw.dtype.kind not in 'iu':
        raise ValueError('Targets must have integer class IDs')
    y = torch.as_tensor(raw.copy(), dtype=torch.long)
    shape = (spec['channels'], spec['height'], spec['width'])
    target_shape = shape[1:] if spec['kind'] == 'segmentation' else ()
    if tuple(x.shape) != shape or tuple(y.shape) != target_shape:
        raise ValueError('Input/target shape violates task contract')
    if not torch.isfinite(x).all() or y.min() < 0 or y.max() >= spec['classes']:
        raise ValueError('Invalid pixels or target class IDs')
    x = x / torch.tensor(spec['input_divisors'])[:, None, None]
    if normalization:
        mean = torch.tensor(normalization['mean'])[:, None, None]
        std = torch.tensor(normalization['std'])[:, None, None]
        if normalization.get('fitted_on') not in ('train', 'pretrained_rgb_train_extras') or not torch.isfinite(mean).all() or not torch.isfinite(std).all() or (std <= 0).any():
            raise ValueError('Invalid or non-training normalization')
        if mean.shape[0] != spec['channels'] or std.shape != mean.shape:
            raise ValueError('Normalization channel mismatch')
        x = (x - mean) / std
    return x, y


class DevelopmentData:
    def __init__(self, root, task_id, split, contracts, inspection, limit=None, augment=False):
        require_split(split)  # Before imports, metadata or sample access.
        if augment and split != 'train':
            raise ValueError('Random augmentation is training-only')
        self.spec = contracts['tasks'][task_id]
        self.split, self.augment, self.normalization = split, augment, None
        self.directory = Path(root) / task_id
        evidence = next(t for t in inspection['tasks'] if t['name'] == task_id)
        partition = self.directory / 'default_partition.json'
        if hashlib.sha256(partition.read_bytes()).hexdigest() != evidence['partition_sha256']:
            raise ValueError('Official partition checksum changed')
        from geobench.task import load_task_specs
        task = load_task_specs(self.directory)
        self.dataset = task.get_dataset(split=split, band_names=None)
        self.official_count = evidence['split_counts'][split]
        if len(self.dataset) != self.official_count:
            raise ValueError('Official split size changed')
        self.count = min(limit, self.official_count) if limit is not None else self.official_count

    def __len__(self):
        return self.count

    def __getitem__(self, index):
        if index < 0 or index >= self.count:
            raise IndexError(index)
        sample = self.dataset[index]
        y = sample.label.data if self.spec['kind'] == 'segmentation' else sample.label
        x, y = prepare(np.stack([b.data for b in sample.bands]), y, self.spec, self.normalization)
        if self.augment:
            x, y = joint_transform(x, y, bool(torch.randint(2, ()).item()), int(torch.randint(4, ()).item()))
        return x, y


def fit_normalization(dataset, check=lambda: None):
    require_split(dataset.split)
    if dataset.split != 'train' or dataset.normalization is not None:
        raise ValueError('Fit only on unnormalized training data')
    sums = squares = None
    pixels = 0
    for i in range(len(dataset)):
        check()
        x, _ = dataset[i]
        x = x.double().flatten(1)
        sums = x.sum(1) if sums is None else sums + x.sum(1)
        squares = x.square().sum(1) if squares is None else squares + x.square().sum(1)
        pixels += x.shape[1]
    if not pixels:
        raise ValueError('Empty training data')
    mean = sums / pixels
    std = (squares / pixels - mean.square()).clamp_min(0).sqrt().clamp_min(1e-6)
    return {'fitted_on': 'train', 'samples': len(dataset), 'mean': mean.tolist(), 'std': std.tolist()}


def validate_task(spec):
    """Validate the common image contract without opening samples."""
    if spec['kind'] not in ('classification', 'segmentation'):
        raise ValueError('Unsupported task type')
    for name in ('channels', 'height', 'width', 'classes'):
        if type(spec[name]) is not int or spec[name] < (2 if name == 'classes' else 1):
            raise ValueError('Invalid ' + name)
    if len(spec['input_divisors']) != spec['channels'] or any(not np.isfinite(v) or v <= 0 for v in spec['input_divisors']):
        raise ValueError('Explicit positive per-channel divisors required')
    if len(spec['band_names']) != spec['channels'] or len(set(spec['band_names'])) != spec['channels']:
        raise ValueError('Unique band names required in storage order')
    rgb = spec.get('rgb_indices')
    if rgb is not None and (len(rgb) != 3 or len(set(rgb)) != 3 or any(type(i) is not int or not 0 <= i < spec['channels'] for i in rgb)):
        raise ValueError('Invalid RGB positions')
    metric = 'accuracy' if spec['kind'] == 'classification' else 'macro_iou'
    if spec['primary_metric'] != metric or spec.get('ignore_index') is not None:
        raise ValueError('This adapter requires the existing metric and no ignored IDs')
    return spec


def task_spec(task_id, contracts, inspection):
    """Copy benchmark metadata into the common contract; frozen contracts unchanged."""
    spec = dict(contracts['tasks'][task_id])
    evidence = next(t for t in inspection['tasks'] if t['name'] == task_id)
    names = evidence.get('corrected_channel_names')
    spec['band_names'] = names or (['R', 'G', 'B', 'NIR'] if spec['channels'] == 4 else ['R', 'G', 'B'])
    spec['rgb_indices'] = [3, 2, 1] if task_id in ('m-eurosat', 'm-brick-kiln') else [0, 1, 2]
    return validate_task(spec)


class ManifestData:
    """Local image manifest; explicit train/valid members, no test or archive loaders."""
    def __init__(self, manifest, split, augment=False):
        require_split(split)  # Reject before reading manifest or sample.
        if augment and split != 'train':
            raise ValueError('Augmentation is training-only')
        self.path = Path(manifest).resolve()
        value = json.loads(self.path.read_text())
        self.spec = validate_task(value['task'])
        self.split, self.augment, self.normalization = split, augment, None
        self.manifest_sha256 = hashlib.sha256(self.path.read_bytes()).hexdigest()
        splits = value['splits']
        if set(splits) != {'train', 'valid'} or not all(splits.values()):
            raise ValueError('Manifest must contain nonempty train/valid only; keep test separate')
        seen = set()
        for rows in splits.values():
            for row in rows:
                image = self.resolve(row['image'])
                if image in seen:
                    raise ValueError('Duplicate image membership')
                seen.add(image)
                if self.spec['kind'] == 'classification':
                    if type(row['label']) is not int or not 0 <= row['label'] < self.spec['classes']:
                        raise ValueError('Invalid class label')
                else:
                    self.resolve(row['mask'])
        self.rows = splits[split]
        self.count = self.official_count = len(self.rows)

    def resolve(self, name):
        path = (self.path.parent / name).resolve()
        if Path(name).is_absolute() or not path.is_relative_to(self.path.parent):
            raise ValueError('Manifest path escapes its directory')
        if path.suffix.lower() not in ('.png', '.jpg', '.jpeg', '.tif', '.tiff'):
            raise ValueError('Unsupported image path')
        return path

    def __len__(self):
        return self.count

    def __getitem__(self, index):
        if not 0 <= index < self.count:
            raise IndexError(index)
        def load(name, mask=False):
            path = self.resolve(name)
            if path.suffix.lower() in ('.tif', '.tiff'):
                import rasterio
                with rasterio.open(path) as src:
                    if mask and src.count != 1:
                        raise ValueError('Mask must have one channel')
                    data = src.read(1) if mask else src.read()
                    if not (src.read_masks() > 0).all():
                        raise ValueError('Missing pixels require an explicit data contract')
                    geo = (src.crs, src.transform)
                return data, geo
            from PIL import Image
            with Image.open(path) as img:
                data = np.array(img)
            if not mask:
                if data.ndim == 2:
                    data = data[None]
                else:
                    data = data.transpose(2, 0, 1)
            return data, None
        row = self.rows[index]
        x, geo = load(row['image'])
        if self.spec['kind'] == 'segmentation':
            y, target_geo = load(row['mask'], mask=True)
            if geo != target_geo:
                raise ValueError('Image/mask geographic alignment differs')
        else:
            y = np.int64(row['label'])
        x, y = prepare(x, y, self.spec, self.normalization)
        if self.augment:
            # Odd quarter turns change rectangular shapes; use 0/180 there.
            turns = int(torch.randint(4 if x.shape[-2] == x.shape[-1] else 2, ()).item())
            if x.shape[-2] != x.shape[-1]:
                turns *= 2
            x, y = joint_transform(x, y, bool(torch.randint(2, ()).item()), turns)
        return x, y


def open_task(root, task_id, split, contracts=None, inspection=None, manifest=None, augment=False):
    """One trusted adapter entry point; task selection is outside agent text."""
    require_split(split)
    if manifest is not None:
        if task_id is not None:
            raise ValueError('Choose benchmark ID or manifest, not both')
        return ManifestData(manifest, split, augment)
    task_spec(task_id, contracts, inspection)
    return DevelopmentData(root, task_id, split, contracts, inspection, augment=augment)
