# GEO-Bench data contracts

Task [1.2: Inspect the four GEO-Bench datasets without test access](https://github.com/Hsenabbass/GoTrain/issues/7).
Inspection evidence is recorded in [data-inspection.json](data-inspection.json).

## Source and version

Use GEO-Bench **1.1.0** with the selected archives from
[`recursix/geo-bench-1.0`](https://huggingface.co/datasets/recursix/geo-bench-1.0),
pinned to dataset revision `1e5754337032f097396db62cc15a5ff88f4618e8`.
All four archive SHA-256 values were checked against Hugging Face LFS metadata.
The published metadata and labels are preserved; no conversion, relabeling or
re-splitting is performed. The dataset card declares CC BY-SA-4.0; retain original
dataset provenance and check task-specific terms before distribution/export.

GEO-Bench's upstream source reference for channel corrections and converter
semantics is commit `17cac9b7bd0d506866d8356f5817b88d173d2891`.
Do not substitute GEO-Bench-2: these are the hackathon's original selected tasks.

## Inspection results

Completed on SageMaker, 2026-10-31. The four archives total **3.41 GB** compressed.
All train/validation labels were read; pixel diagnostics used **64 images per split**.
Test counts below come only from published partition metadata.

| Loader ID | Benchmark | Train / valid / test | Image H×W×C; stored dtype | Target |
| --- | --- | --- | --- | --- |
| `m-eurosat` | `classification_v1.0` | 2,000 / 1,000 / 1,000 | 64×64×13; int16 | Scalar int64, IDs 0–9 |
| `m-brick-kiln` | `classification_v1.0` | 15,063 / 999 / 999 | 64×64×13; float64 | Scalar int64, IDs 0–1 |
| `m-pv4ger-seg` | `segmentation_v1.0` | 3,000 / 403 / 403 | 320×320×3; uint8 | 320×320 uint8 mask, IDs 0–1 |
| `m-chesapeake` | `segmentation_v1.0` | 3,000 / 1,000 / 1,000 | 256×256×4; float32 | 256×256 int64 mask, IDs 0–6 |

- **EuroSAT:** balanced: 200 training and 100 validation images per class.
  Sampled values span 3–16,692; do not treat these as 8-bit RGB.
- **Brick-Kiln:** training has 10,000 negatives / 5,063 positives; validation has
  663 / 336. Reflectance and true-colour channels have different scales; all are
  stored as float64, including fractional resampled values. Cast explicitly in a
  future adapter rather than retaining float64 GPU inputs.
- **PV4GER-Seg:** solar-PV pixels comprise 19.96% of training and 19.95% of
  validation. There are 6 / 1 all-background masks. Sampled RGB values span 6–255.
- **Chesapeake:** sampled images are already scaled to 0–1; do not divide by 255
  again. Labels are imbalanced; exact per-ID counts are in the JSON. There are
  125 / 20 all-zero masks; one reviewed validation image is also entirely black.
  Retain official membership and resolve no-data handling in 1.3.

The sampled images had no non-finite pixels or image/mask shape mismatches.
PV4GER transforms agreed where present. Chesapeake transforms are absent, so
geographic alignment cannot be checked from them. Two train and two validation
image/mask/overlay examples per segmentation task were visually reviewed: masks
follow the visible features; the black Chesapeake example is flagged above.
These are bounded diagnostics, not a guarantee that every image is defect-free.

## Channel and label handling

The published EuroSAT/Brick-Kiln pixel values are valid but their stored band names
and wavelengths are wrong. Interpret **storage position**, not the misleading band
name. Do not rewrite the benchmark files. The corrected order is:

| Zero-based channel | EuroSAT | Brick-Kiln |
| --- | --- | --- |
| 0–4 | B01, B02, B03, B04, B05 | B01, B02, B03, B04, B05 |
| 5 | B06 | B07 |
| 6 | B07 | B8A |
| 7 | B08 | B08 |
| 8 | B09 | B11 |
| 9 | B10 | B12 |
| 10 | B11 | TCI_R |
| 11 | B12 | TCI_G |
| 12 | B8A | TCI_B |

Brick-Kiln's last three channels are 8-bit true-colour composites, not reflectance.
Keep their scaling separate from the reflectance channels. A future RGB-only
adapter must explicitly record which channels it selects; do not rely on default
band-name selection. [Upstream correction](https://github.com/ServiceNow/geo-bench/blob/17cac9b7bd0d506866d8356f5817b88d173d2891/README.md#known-issues).

PV4GER-Seg is RGB with binary masks: 0 = background/no solar PV, 1 = solar PV.
Use the published masks; future transforms must apply the same spatial operation
to image and mask, with nearest-neighbor resampling for labels.
[PV4GER converter](https://github.com/ServiceNow/geo-bench/blob/17cac9b7bd0d506866d8356f5817b88d173d2891/make_benchmark/dataset_converters/pv4ger.py).

Chesapeake uses RGB plus near-infrared. Published task metadata declares seven
classes but omits their names. The converter's `LABELS` tuple is not saved as class
names and must not be interpreted as a verified ID-to-name mapping. The original
[source codebook](https://lila.science/datasets/chesapeakelandcover#data-description)
uses IDs 1–6 for water, tree canopy, low vegetation, barren land, impervious-other
and roads; its original no-data ID is 15. Our benchmark masks contain only 0–6,
with all label-0 pixels confined to the all-zero masks. This indicates padding or
no-data, rather than water, but **1.3 must finalize the benchmark-compatible
ignored-label policy before scoring**. Preserve the labels and these ambiguities;
do not shift IDs based on tuple order or silently discard samples.
[Versioned converter](https://github.com/ServiceNow/geo-bench/blob/17cac9b7bd0d506866d8356f5817b88d173d2891/make_benchmark/dataset_converters/chesapeake_land_cover.py).

Classification targets remain one integer per image. Segmentation targets remain
integer class-ID masks aligned to the image grid. Future adapters may arrange
inputs as channel-first float tensors but must preserve explicit channel order,
class IDs and split membership. No model or training recipe is selected in 1.2.

## Splits, statistics and test protection

- Use `default_partition.json` unchanged. The loader split names are exactly
  `train`, `valid`, and `test`; our inspection accepts **only `train` and `valid`**.
- The four downloaded ZIPs bundle test payloads. Keep them sealed in their archives.
  Extract metadata and only sample files named in train/valid membership; never
  instantiate a test/all-split dataset, open a test sample, or render test previews.
  Published split counts/checksums are metadata, not test evaluation.
- Complete training/validation label histograms are measured. Pixel-level
  diagnostics use 64 deterministically spaced images per split, not an exhaustive
  quality audit. Means/ranges from these subsets are diagnostic only; no learned
  preprocessing is fitted. Future normalization statistics must be fitted on
  training data only, never validation or the bundled all-split statistics.
- Source manifests remain intact. Preserve partition hashes and the four archive
  hashes in the evidence. The script rejects test/all selections before loading
  and verifies materialized HDF5 files against train/valid membership.
- This protects the inspection path; it is not the M2 sandbox against an agent
  modifying code. Primary metrics, aggregation, ignored labels, budgets and
  repeatability settings are defined in task 1.3 before reference training.

## Storage and reproducible inspection

The inspection utility is [scripts/inspect_data.py](../scripts/inspect_data.py).
Load a task explicitly from its directory using
`geobench.task.load_task_specs(Path(dataset_dir))`, then
`task.get_dataset(split="train", band_names=None)` (or `valid`).
`band_names=None` keeps all channels in storage order; GEO-Bench's default RGB
selection would hide multispectral channels. Samples expose separate 2-D bands,
not an already stacked training tensor.

On SageMaker, data is under `/home/sagemaker-user/GoTrain/data/geo-bench/`:
`archives/` retains the four verified ZIPs; `datasets/` holds metadata and extracted
train/valid HDF5 files. Both are ignored by Git. The resource index owns safe
[operational locations](RESOURCES.md); no credentials or access URLs are recorded.

Run with the verification environment from the [setup record](setup.md):

```bash
cd /home/sagemaker-user/GoTrain
timeout 1800 /home/sagemaker-user/gotrain-access-check/venv/bin/python \
  scripts/inspect_data.py --stage download \
  --root data/geo-bench --evidence artifacts/data-inspection
timeout 900 /home/sagemaker-user/gotrain-access-check/venv/bin/python \
  scripts/inspect_data.py --stage inspect \
  --root data/geo-bench --evidence artifacts/data-inspection
```

Download is restricted to the four allowlisted archives (under 4 GB compressed)
and stops if free disk falls below 15 GiB. Logs, full download manifest, inspection
summary, status and train/valid segmentation previews remain in the evidence
directory. Large datasets, archives and previews do not belong in Git. A small
sanitized result record is committed here so completion is reviewable.
