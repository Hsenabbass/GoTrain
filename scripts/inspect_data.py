"""Bounded M1 inspection: selected GEO-Bench tasks; never load test samples."""

import argparse
import hashlib
import json
import importlib.metadata
import shutil
import time
import zipfile
from pathlib import Path, PurePosixPath

from huggingface_hub import HfApi, hf_hub_download

REPO = "recursix/geo-bench-1.0"
REVISION = "1e5754337032f097396db62cc15a5ff88f4618e8"
SOURCE_COMMIT = "17cac9b7bd0d506866d8356f5817b88d173d2891"
ARCHIVES = [
    "classification_v1.0/m-eurosat.zip",
    "segmentation_v1.0/m-pv4ger-seg.zip",
    "classification_v1.0/m-brick-kiln.zip",
    "segmentation_v1.0/m-chesapeake.zip",
]
CORRECT_CHANNELS = {
    "m-eurosat": ["B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08",
                  "B09", "B10", "B11", "B12", "B8A"],
    "m-brick-kiln": ["B01", "B02", "B03", "B04", "B05", "B07", "B8A", "B08",
                     "B11", "B12", "TCI_R", "TCI_G", "TCI_B"],
}


def require_development_split(split):
    if split not in ("train", "valid"):
        raise ValueError("Inspection permits only train and valid")


def open_development_dataset(task, split):
    require_development_split(split)
    return task.get_dataset(split=split, band_names=None)


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, default=str) + "\n")


def safe_destination(root, member):
    name = PurePosixPath(member)
    if name.is_absolute() or ".." in name.parts:
        raise ValueError("Unsafe archive path")
    destination = root.joinpath(*name.parts)
    if not destination.resolve().is_relative_to(root.resolve()):
        raise ValueError("Archive path escapes data root")
    return destination


def verify_materialized(directory, allowed):
    actual = {path.name for path in directory.glob("*.hdf5")}
    if actual != {sample_name + ".hdf5" for sample_name in allowed}:
        raise RuntimeError("Materialized sample files differ from train/valid allowlist")
    return len(actual)


def download_metadata(root, evidence):
    info = HfApi().dataset_info(REPO, revision=REVISION, files_metadata=True)
    sources = {f.rfilename: f for f in info.siblings}
    assert sum(sources[name].size for name in ARCHIVES) < 4_000_000_000
    manifest = {"repo": REPO, "revision": info.sha, "tasks": []}
    for name in ARCHIVES:
        if shutil.disk_usage(root).free < 15 * 2**30:
            raise RuntimeError("Less than 15 GiB free; stopping")
        print("DOWNLOAD", name, flush=True)
        archive = Path(hf_hub_download(
            repo_id=REPO, repo_type="dataset", revision=REVISION,
            filename=name, local_dir=root / "archives",
        ))
        sha = digest(archive)
        lfs = sources[name].lfs
        expected = lfs.get("sha256") if isinstance(lfs, dict) else getattr(lfs, "sha256", None)
        if not expected or sha != expected:
            raise RuntimeError("Archive SHA-256 verification failed")
        task = {"archive": name, "bytes": archive.stat().st_size,
                "sha256": sha, "metadata": {}}
        # ZIP central-directory metadata is consulted only to locate metadata.
        # No sample names are logged and no sample payload is opened here.
        with zipfile.ZipFile(archive) as z:
            for member in z.infolist():
                basename = PurePosixPath(member.filename).name
                if basename == "task_specs.pkl" or basename.endswith("_partition.json"):
                    destination = safe_destination(root / "datasets", member.filename)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(member) as src, destination.open("wb") as dst:
                        shutil.copyfileobj(src, dst)
                    if basename.endswith("_partition.json"):
                        partition = json.loads(destination.read_text())
                        task["metadata"][member.filename] = {
                            split: len(items) for split, items in partition.items()
                        }
                    if basename == "task_specs.pkl":
                        task["dataset_dir"] = str(destination.parent)
        manifest["tasks"].append(task)
        save(evidence / "download-manifest.json", manifest)
        print("VERIFIED", name, "metadata", task["metadata"], flush=True)
    return manifest


def inspect_tasks(root, evidence, manifest, pixels_per_split=64):
    import numpy as np
    from collections import Counter
    from geobench.dataset import Band, load_sample_hdf5
    from geobench.task import load_task_specs
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # Reject invalid/test selection before touching a task or file.
    for forbidden in ("test", None, "all"):
        try:
            open_development_dataset(None, forbidden)
        except ValueError:
            pass
        else:
            raise AssertionError("Split guard failed")

    report = {"repo": REPO, "revision": REVISION,
              "channel_mapping_source_commit": SOURCE_COMMIT,
              "package_version": importlib.metadata.version("geobench"),
              "pixel_samples_per_split_cap": pixels_per_split,
              "test_payloads_opened": 0, "test_payloads_extracted": 0,
              "invalid_split_guard_passed": True, "tasks": []}
    preview_rows = []
    for item in manifest["tasks"]:
        directory = Path(item["dataset_dir"])
        name = directory.name
        partition_path = directory / "default_partition.json"
        partition = json.loads(partition_path.read_text())
        allowed = partition["train"] + partition["valid"]
        assert len(set(allowed)) == len(allowed), "Train/validation duplicate membership"
        prefix = directory.relative_to(root / "datasets").as_posix()
        archive = root / "archives" / item["archive"]
        # Only request member paths named by train/valid metadata. In particular,
        # never iterate test IDs or extract/read test payloads from the ZIP.
        with zipfile.ZipFile(archive) as z:
            for sample_name in allowed:
                member = prefix + "/" + sample_name + ".hdf5"
                destination = safe_destination(root / "datasets", member)
                if not destination.exists():
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(member) as src, destination.open("wb") as dst:
                        shutil.copyfileobj(src, dst)
        materialized_count = verify_materialized(directory, allowed)

        task = load_task_specs(directory)
        task.benchmark_name = PurePosixPath(item["archive"]).parent.name
        target = {"name": name, "benchmark": task.benchmark_name,
                  "dataset_dir": str(directory), "archive_sha256": item["sha256"],
                  "partition_sha256": digest(partition_path),
                  "materialized_train_valid_files": materialized_count,
                  "split_counts": {s: len(v) for s, v in partition.items()},
                  "patch_size": task.patch_size, "spatial_resolution": task.spatial_resolution,
                  "label_type": type(task.label_type).__name__,
                  "label_description": repr(task.label_type),
                  "label_metadata": vars(task.label_type),
                  "stored_band_names": [b.name for b in task.bands_info],
                  "corrected_channel_names": CORRECT_CHANNELS.get(name),
                  "splits": {}}
        for split in ("train", "valid"):
            dataset = open_development_dataset(task, split)
            assert len(dataset) == len(partition[split])
            histogram = Counter()
            label_shapes, label_dtypes = Counter(), Counter()
            foreground_pixels = total_pixels = empty_masks = 0
            for sample_name in partition[split]:
                sample = load_sample_hdf5(directory / (sample_name + ".hdf5"), label_only=True)
                y = sample.label.data if isinstance(sample.label, Band) else sample.label
                y = np.asarray(y)
                label_shapes[str(y.shape)] += 1
                label_dtypes[str(y.dtype)] += 1
                values, counts = np.unique(y, return_counts=True)
                histogram.update({str(v.item()): int(c) for v, c in zip(values, counts)})
                if y.ndim >= 2:
                    foreground_pixels += int(np.count_nonzero(y))
                    total_pixels += y.size
                    empty_masks += int(not np.any(y))
            selection = np.linspace(0, len(dataset) - 1,
                                    min(pixels_per_split, len(dataset)), dtype=int)
            sums = sums2 = counts = minima = maxima = zero_counts = None
            nonfinite = shape_mismatch = transform_mismatch = 0
            shapes, dtypes = Counter(), Counter()
            stored_order = None
            for index in selection:
                sample = dataset[int(index)]
                bands = list(sample.bands)
                order = [b.band_info.name for b in bands]
                if stored_order is None:
                    stored_order = order
                    n = len(bands)
                    sums, sums2, counts = np.zeros(n), np.zeros(n), np.zeros(n, dtype=np.int64)
                    minima, maxima = np.full(n, np.inf), np.full(n, -np.inf)
                    zero_counts = np.zeros(n, dtype=np.int64)
                assert order == stored_order, "Inconsistent channel storage order"
                for channel, band in enumerate(bands):
                    a = np.asarray(band.data)
                    shapes[str(a.shape)] += 1
                    dtypes[str(a.dtype)] += 1
                    finite = np.isfinite(a)
                    nonfinite += int(a.size - finite.sum())
                    x = a[finite].astype(np.float64)
                    if x.size:
                        sums[channel] += x.sum()
                        sums2[channel] += np.square(x).sum()
                        counts[channel] += x.size
                        minima[channel] = min(minima[channel], x.min())
                        maxima[channel] = max(maxima[channel], x.max())
                        zero_counts[channel] += np.count_nonzero(x == 0)
                    if isinstance(sample.label, Band):
                        shape_mismatch += int(a.shape[:2] != sample.label.data.shape[:2])
                        if band.transform is not None and sample.label.transform is not None:
                            transform_mismatch += int(band.transform != sample.label.transform)
                if name in ("m-pv4ger-seg", "m-chesapeake") and len(preview_rows) < 8:
                    # Keep two examples per task/split; no test images involved.
                    existing = sum(row[0] == name + " " + split for row in preview_rows)
                    if existing < 2:
                        rgb = np.stack([b.data for b in bands[:3]], axis=-1).astype(float)
                        lo, hi = np.percentile(rgb, [1, 99])
                        rgb = np.clip((rgb - lo) / max(hi - lo, 1), 0, 1)
                        preview_rows.append((name + " " + split, rgb, sample.label.data.copy()))
            means = sums / counts
            stats = {"label_histogram": dict(sorted(histogram.items())),
                     "label_shapes": dict(label_shapes), "label_dtypes": dict(label_dtypes),
                     "pixel_samples_inspected": len(selection),
                     "band_shapes": dict(shapes), "band_dtypes": dict(dtypes),
                     "observed_band_order": stored_order,
                     "nonfinite_pixels": nonfinite, "image_mask_shape_mismatches": shape_mismatch,
                     "image_mask_transform_mismatches": transform_mismatch,
                     "channel_min": minima.tolist(), "channel_max": maxima.tolist(),
                     "channel_mean": means.tolist(),
                     "channel_std": np.sqrt(np.maximum(sums2 / counts - means**2, 0)).tolist(),
                     "zero_fraction": (zero_counts / counts).tolist(),
                     "note": "Deterministic diagnostic subset; not fitted normalization statistics."}
            if total_pixels:
                stats.update({"nonzero_label_fraction": foreground_pixels / total_pixels,
                              "empty_masks": empty_masks})
            target["splits"][split] = stats
        report["tasks"].append(target)
        save(evidence / "inspection-summary.json", report)
        print("INSPECTED", name, target["split_counts"], flush=True)

    fig, axes = plt.subplots(len(preview_rows), 3, figsize=(10, 3 * len(preview_rows)), squeeze=False)
    for row, (title, rgb, mask) in enumerate(preview_rows):
        axes[row, 0].imshow(rgb)
        axes[row, 1].imshow(mask, interpolation="nearest", vmin=0)
        axes[row, 2].imshow(rgb)
        axes[row, 2].imshow(np.ma.masked_equal(mask, 0), alpha=0.5, interpolation="nearest")
        for col, suffix in enumerate(("image", "mask", "overlay")):
            axes[row, col].set_title(title + " " + suffix)
            axes[row, col].axis("off")
    fig.tight_layout()
    fig.savefig(evidence / "segmentation-previews.png", dpi=100)
    plt.close(fig)
    save(evidence / "status.json", {"stage": "inspection_complete", "tasks": 4,
                                   "test_sample_payloads_opened": 0})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--stage", choices=("download", "inspect", "all"), default="all")
    args = parser.parse_args()
    args.root = args.root.resolve()
    args.evidence = args.evidence.resolve()
    args.root.mkdir(parents=True, exist_ok=True)
    args.evidence.mkdir(parents=True, exist_ok=True)
    started = time.time()
    if args.stage in ("download", "all"):
        manifest = download_metadata(args.root, args.evidence)
        save(args.evidence / "status.json", {
            "stage": "metadata_complete", "tasks": len(manifest["tasks"]),
            "elapsed_seconds": round(time.time() - started, 1),
            "test_sample_payloads_opened": 0,
        })
    else:
        manifest = json.loads((args.evidence / "download-manifest.json").read_text())
    if args.stage in ("inspect", "all"):
        inspect_tasks(args.root, args.evidence, manifest)
    print("COMPLETE", args.stage, flush=True)


if __name__ == "__main__":
    main()
