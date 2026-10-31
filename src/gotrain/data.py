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
        if normalization.get('fitted_on') != 'train' or not torch.isfinite(mean).all() or not torch.isfinite(std).all() or (std <= 0).any():
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
