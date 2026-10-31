"""Bounded train/valid capacity probe on SageMaker; not a reference experiment."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    deadline = started + 240
    import numpy as np
    import torch
    import torchvision
    from torchvision.models import resnet18
    from torchvision.models.segmentation import fcn_resnet50
    from geobench.task import load_task_specs
    from inspect_data import open_development_dataset

    torch.set_num_threads(2)
    torch.manual_seed(2026)
    torch.backends.cudnn.benchmark = False
    assert torch.cuda.is_available(), 'Provided CUDA GPU is required'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report = {'kind': 'capacity_calibration_not_reference', 'created_utc': datetime.now(timezone.utc).isoformat(),
              'wall_cap_seconds': 240, 'external_timeout_seconds': 300, 'seed': 2026,
              'torch': torch.__version__, 'torchvision': torchvision.__version__,
              'gpu': torch.cuda.get_device_name(), 'precision': 'cuda_float16_autocast_grad_scaler',
              'cpu_threads': 2, 'loader_workers': 0, 'test_payloads_opened': 0,
              'weights_downloaded': False, 'reference_scores_produced': False,
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'disk_free_bytes': shutil.disk_usage(args.data_root).free,
              'tasks': []}
    rows = [('m-eurosat', 13, 10, 32), ('m-brick-kiln', 13, 2, 32),
            ('m-pv4ger-seg', 3, 2, 4), ('m-chesapeake', 4, 7, 4)]
    for name, channels, classes, batch_size in rows:
        if time.monotonic() >= deadline:
            raise TimeoutError('Calibration wall cap reached')
        segmentation = name in ('m-pv4ger-seg', 'm-chesapeake')
        task = load_task_specs(args.data_root / name)
        train, valid = [open_development_dataset(task, split) for split in ('train', 'valid')]
        partitions = json.loads((args.data_root / name / 'default_partition.json').read_text())
        assert len(train) == len(partitions['train']) and len(valid) == len(partitions['valid'])
        counts = {'train': 0, 'valid': 0}
        def batch(dataset, split, step):
            xs, ys = [], []
            # Explicit train/valid membership only. No test/all dataset exists.
            for i in range(batch_size):
                sample = dataset[(step * batch_size + i) % min(64, len(dataset))]
                x = np.stack([band.data for band in sample.bands]).astype('float32')
                if name == 'm-eurosat':
                    x /= 10000.0
                elif name == 'm-brick-kiln':
                    x[:10] /= 10000.0
                    x[10:] /= 255.0
                elif name == 'm-pv4ger-seg':
                    x /= 255.0
                y = sample.label.data if segmentation else sample.label
                xs.append(torch.from_numpy(x)); ys.append(torch.as_tensor(np.asarray(y).copy(), dtype=torch.long))
            counts[split] += batch_size
            return torch.stack(xs).cuda(), torch.stack(ys).cuda()

        model = fcn_resnet50(weights=None, weights_backbone=None, num_classes=classes, aux_loss=False) if segmentation else resnet18(weights=None, num_classes=classes)
        stem = model.backbone if segmentation else model
        if channels != 3:
            stem.conv1 = torch.nn.Conv2d(channels, 64, 7, stride=2, padding=3, bias=False)
        model.cuda()
        optimizer = torch.optim.SGD(model.parameters(), lr=0.001)
        scaler = torch.amp.GradScaler('cuda')
        torch.cuda.reset_peak_memory_stats()
        train_times, valid_times = [], []
        for split, dataset, steps in [('train', train, 8), ('valid', valid, 4)]:
            model.train(split == 'train')
            for step in range(steps):
                if time.monotonic() >= deadline:
                    raise TimeoutError('Calibration wall cap reached')
                torch.cuda.synchronize(); t = time.monotonic()
                x, y = batch(dataset, split, step)
                optimizer.zero_grad(set_to_none=True)
                with torch.set_grad_enabled(split == 'train'), torch.autocast('cuda', dtype=torch.float16):
                    out = model(x)
                    logits = out['out'] if segmentation else out
                    expected = (batch_size, classes, *y.shape[-2:]) if segmentation else (batch_size, classes)
                    assert tuple(logits.shape) == expected
                    loss = torch.nn.functional.cross_entropy(logits, y)
                assert torch.isfinite(loss), 'Non-finite calibration loss'
                if split == 'train':
                    scaler.scale(loss).backward(); scaler.step(optimizer); scaler.update()
                torch.cuda.synchronize()
                elapsed = time.monotonic() - t
                # Three train warmups; one validation warmup. Include data loading.
                if step >= (3 if split == 'train' else 1):
                    (train_times if split == 'train' else valid_times).append(elapsed)
        train_mean, valid_mean = sum(train_times) / len(train_times), sum(valid_times) / len(valid_times)
        row = {'task': name, 'proxy': 'fcn_resnet50_random' if segmentation else 'resnet18_random',
               'batch_size': batch_size, 'channels': channels, 'classes': classes,
               'train_steps_total': 8, 'valid_steps_total': 4, 'sample_loads': counts,
               'train_seconds_per_batch': train_mean, 'valid_seconds_per_batch': valid_mean,
               'train_images_per_second': batch_size / train_mean,
               'valid_images_per_second': batch_size / valid_mean,
               'estimated_full_train_epoch_seconds': math.ceil(len(train) / batch_size) * train_mean,
               'estimated_full_valid_seconds': math.ceil(len(valid) / batch_size) * valid_mean,
               'peak_allocated_bytes': torch.cuda.max_memory_allocated(),
               'peak_reserved_bytes': torch.cuda.max_memory_reserved(),
               'finite_loss_and_shapes_passed': True}
        report['tasks'].append(row)
        report['elapsed_seconds'] = time.monotonic() - started
        args.output.write_text(json.dumps(report, indent=2) + '\n')
        print('CALIBRATED', name, round(train_mean, 3), round(valid_mean, 3), 'seconds/batch', flush=True)
        del model, optimizer, scaler, x, y, logits, out, loss
        torch.cuda.empty_cache()
    report['completed'] = True
    report['elapsed_seconds'] = time.monotonic() - started
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print('CALIBRATION_COMPLETE', flush=True)


if __name__ == '__main__':
    main()
