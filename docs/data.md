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
  Retain official membership; the evaluation policy below includes ID 0 in the
  benchmark primary metric and provides a no-data-excluded diagnostic.

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
with all label-0 pixels confined to the all-zero masks. We describe ID 0 as
observed no-data/padding; the original codebook maps 1–6 as above. **Keep ID 0 in
the benchmark primary metric and cross-entropy loss**, matching the official
experiment implementation's lack of an ignored ID. Also report a separately named
land-only diagnostic that excludes target-0 pixels. Never shift IDs based on tuple
order, remove black samples, or present the diagnostic as the primary score.
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
directory. Large datasets, archives and previews do not belong in Git.
Follow [storage and recovery](storage.md) for teammate access, sealed archive
caching and reconstruction after environment loss. A small
sanitized result record is committed here so completion is reviewable.

## Task and prediction contract (1.3)

[Machine-readable task settings](../configs/tasks.json) freeze the four supported
IDs, source revision, default partition, tensor sizes, scales and scoring rules.
M1 accepts a registered task ID, task-description string, pinned dataset reference,
seed and explicit budget no larger than [M1 caps](../configs/m1.json). Arbitrary
uploads, external paths and new dataset adapters belong later. The [manual foundation](training.md) implements and tests enforcement before
reference runs; the settings alone are not enforcement.

- **Input:** float32 `N×C×H×W`, all channels in corrected storage order, original
  patch sizes. Divide EuroSAT channels by 10,000; Brick-Kiln's first ten by 10,000
  and last three by 255; PV4GER RGB by 255; Chesapeake stays unchanged. These are
  fixed scale conversions, not fitted statistics. Do not clamp reflectance to 1:
  observed values exceed 10,000. Any later learned normalization must be fitted on
  train only, saved with the recipe and reused unchanged on validation/prediction.
- **Targets:** classification int64 `N`; segmentation int64 `N×H×W`. Keep all class
  IDs and official split membership. Reject invalid shapes, non-finite inputs/loss
  and out-of-range targets rather than silently dropping samples or pixels.
- **Outputs:** logits and float32 softmax probabilities `N×K` for classification,
  `N×K×H×W` for segmentation; class IDs `N` or masks `N×H×W` from `argmax(dim=1)`.
  Ties select the lowest ID. Both binary tasks use two logits, with no tuned binary
  threshold. Segmentation logits must match the original grid. Resample class masks
  only with nearest-neighbor; paired train spatial augmentation must keep alignment.
  Validation/prediction have no random augmentation. Probability tensors are streamed
  by batch; do not retain full-resolution probability maps by default.
- **Run result:** unique UTC/task run ID; completed/budget-exhausted/failed/cancelled
  status; source commit and exact recipe/config; data revision and partition hash;
  seed, steps/epochs and runtime/resources; checkpoint path; validation metrics,
  per-class/confusion counts and logs; prediction IDs/masks or their artifact path.
  Each metric records its split and completeness. Retain best and last checkpoints
  (at most two); class/mask outputs may be stored compactly as uint8 without changing IDs.

## Evaluation and checkpoint rules (1.3)

| Task | Primary metric (maximize, range 0–1) | Included IDs | Supplementary diagnostics |
| --- | --- | --- | --- |
| EuroSAT | Overall top-1 accuracy | 0–9 | Macro F1, per-class recall/confusion matrix |
| Brick-Kiln | Overall top-1 accuracy | 0–1 | Positive-class precision/recall/F1 and macro F1 |
| PV4GER-Seg | Macro IoU | 0–1, including background | Solar-PV IoU/F1 and per-class IoU |
| Chesapeake | Macro IoU | 0–6, including no-data/padding | `land_macro_iou_target_0_ignored`, per-class IoU |

The [official experiment implementation](https://github.com/ServiceNow/geo-bench-experiments/blob/96958fbf209b758954231ea387b4cf61b26e8c4c/geobench_exp/torch_toolbox/model.py#L260)
uses multiclass accuracy for classification and multiclass Jaccard for segmentation,
without an ignore index; its segmentation loss is ordinary cross-entropy. Our
explicit reduction follows [TorchMetrics' versioned IoU reduction](https://github.com/Lightning-AI/torchmetrics/blob/v1.9.0/src/torchmetrics/functional/classification/jaccard.py#L34).
We do not install the reproduction harness or use its test-access/training defaults.

Aggregate one confusion matrix over **the entire official validation split**, rows
= targets and columns = predictions. Accuracy is diagonal sum / sample count.
For class k, IoU = TP / (TP + FP + FN). Macro-average class IoUs with equal weight;
exclude a class only when both its global target and prediction counts are zero.
A class absent from targets but predicted still contributes IoU 0. Never average
batch or image IoUs. Per-class zero divisions are reported as 0 with support/union
counts; an entirely empty evaluation is invalid, not a perfect score. Supplementary
macro F1 uses the fixed class list and zero division 0.

For the Chesapeake land-only diagnostic, remove target-0 pixels before accumulating
counts and average IDs 1–6 with the same absent-class rule. Predictions of 0 on
nonzero targets still count as errors. The primary metric ignores **no** target ID;
all-background/all-zero patches remain in validation. No test sample is accessed
in M1; the eventual M5 evaluator must reuse the frozen selected pipeline/contract.

Select checkpoints using the highest **complete-validation primary metric**;
ties keep the earliest checkpoint. Use no supplementary score or training loss to
break ties. A partial validation may be logged as a smoke result, never a reference
or selection score. A budget-limited run qualifies only if its retained checkpoint
has a complete validation pass and full provenance. Reload it in a fresh process
and reproduce the primary score within absolute 1e-6 before accepting the reference.

Default seed is 2026; record initialization, data-order and worker seeds, AMP and
versions. Disable cuDNN benchmarking; log any deterministic-operation warnings.
One seed does not establish retraining stability or bitwise reproducibility.

These are frozen internal benchmark rules, **not announced organizer judging
metrics**. Those requirements remain pending the user's update. If they differ,
version the contract and re-evaluate saved validation predictions/checkpoints;
do not silently change reference definitions or inspect test to choose a metric.

## Measured M1 budgets (1.3)

[Versioned numeric caps](../configs/m1.json) own limits; [calibration evidence](calibration.json)
and [setup capacity](setup.md#capacity-calibration-and-m1-budgets) explain the basis.
All GPU jobs run sequentially. Total M1 GPU-job wall allocation is **3,600 seconds**,
including calibration (cap 300), foundation smoke (300), four references (2,400),
checkpoint revalidation (240), earlier-access accounting allowance (60) and failure
reserve (300). The 1.1 CUDA smoke runtime was not instrumented; that allowance is
not a measured duration. Charge actual job elapsed
wall time including startup/data loading/validation/saving; a retry also consumes
this shared allocation. These are project caps, not verified cloud entitlements.

Each reference stops at the first of **600 seconds, 10 epochs, or 5,000 training
steps**. Reserve the last 30 seconds for classification or 60 for segmentation for
full validation and checkpoint/report saving. Validate throughout at epoch boundaries;
admission estimates must leave room for a complete final pass. Default batch ceilings
are 32/4 (classification/segmentation), two CPU threads, no loader workers. Changed
architectures/precision/loader settings require a short bounded cost check within
the remaining allocation; the probe is not a speed guarantee for other recipes.

Keep at least 15 GiB free disk; cap retained M1 artifacts (including backup staging) at 20 GiB and a run at
2 GiB. GPU allocation must stay below 10 GiB, reserved memory below 12 GiB. Allow
one logged transient retry per failed run, within the total budget; an OOM retry
halves the batch under a new run ID. Permission, test-guard, label, non-finite-loss
and checksum failures require diagnosis, not automatic retries. Stop and surface
the tradeoff if four complete validation records cannot fit; never drop tasks or
substitute subsets. The [manual runner](training.md) enforces these rules for tasks 1.5/1.6.

Reserve at least two hours before the user-confirmed **2026-11-01 15:00 Asia/Beirut**
submission for final evaluation/presentation/submission. Admit no development job
that would cross that buffer. The one-hour M1 GPU allocation leaves the remaining
event time for M2–M5 without assuming unlimited organizer quotas. Existing M1
Bedrock smoke caps are recorded in the config (two requests, one tool call, 128
output tokens/request, 60 seconds); 1.3 makes no new Bedrock calls. Model-weight
retrieval later has a 120-second cap and one transient retry; record provenance
and license when choosing reference recipes. Calibration uses random weights and
selects no final model or performance target.
