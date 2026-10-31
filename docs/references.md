# M1 reference results

Task [1.5](https://github.com/Hsenabbass/GoTrain/issues/10): classification starting
points, separate from the [foundation smoke checks](m1-evidence.json). These are
fixed manual baselines for later comparisons, not a tuning search or promised scores.

## Frozen classification recipes

Frozen before either measured run; exact settings live in
[EuroSAT](../configs/reference-m-eurosat.json) and
[Brick-Kiln](../configs/reference-m-brick-kiln.json).

Both use the already calibrated/verified Torchvision ResNet18, **random
initialization (`weights=None`)**, a newly initialized 13-input 7×7/stride-2 stem
and a task-sized output head (10/2 logits). There is no imported weight file,
pretrained-weight license or network retrieval. Torchvision 0.24's architecture
implementation is [BSD-3-Clause](https://github.com/pytorch/vision/blob/v0.24.0/LICENSE);
[its builder](https://docs.pytorch.org/vision/0.24/models/generated/torchvision.models.resnet18.html)
supports random initialization explicitly. This simple all-channel baseline avoids
an unverified RGB-weight adaptation and leaves model improvement to later work.

- Preserve the default official partitions, all 13 channels in corrected storage
  order and all class IDs. Use the [fixed per-channel scales](data.md), then fit
  channel mean/std on **all training images only**. Reuse those saved statistics
  unchanged for full validation and checkpoint prediction.
- Unweighted cross-entropy; SGD, momentum 0.9, learning rate 0.01, weight decay
  0.0001; constant learning rate, no scheduler. Seed 2026; float16 autocast with
  GradScaler (initial scale 1024). Train-only paired flips/90-degree rotations;
  validation has no random transforms. Native 64×64 inputs, no resizing.
- Batch 32; stop at 10 epochs, 5,000 minibatch steps or 600 wall seconds, whichever
  comes first, preserving the agreed validation/saving reserve. No hyperparameter
  or threshold search. A cap-truncated run is accepted only with complete official
  validation and successful fresh-process checkpoint revalidation.
- Choose the highest full-validation accuracy; exact ties keep the earliest
  checkpoint. Supplementary class metrics never select the model. Single-seed
  baselines do not establish retraining stability or published-result equivalence.

## Execution and acceptance

Run sequentially on the canonical SageMaker checkout using the [manual runner](training.md):

```bash
PY=/home/sagemaker-user/gotrain-access-check/venv/bin/python
$PY scripts/train.py train --recipe configs/reference-m-eurosat.json --data-root data/geo-bench/datasets
$PY scripts/train.py verify --run-id <eurosat-run-id> --data-root data/geo-bench/datasets
$PY scripts/train.py train --recipe configs/reference-m-brick-kiln.json --data-root data/geo-bench/datasets
$PY scripts/train.py verify --run-id <brick-kiln-run-id> --data-root data/geo-bench/datasets
```

## Verified classification results (2026-10-31)

| Task | Full-validation accuracy | Validation images | Full epochs / total steps | Training wall time | Fresh-process score delta |
| --- | --- | --- | --- | --- | --- |
| EuroSAT | **87.00%** | 1,000 | 10 / 630 | 169.69 s | 0 |
| Brick-Kiln | **97.80%** (977/999) | 999 | 4 / 2,334 | 575.81 s | 0 |

Brick-Kiln also trained part of epoch 5 before the wall-time reserve stopped
training; its final partial-epoch checkpoint received full validation. Its
`budget_exhausted` status records that planned stop, not a failed evaluation.
The selected best checkpoint scored higher than the last checkpoint (97.50%).
Brick-Kiln positive-class precision, recall and F1 are each **96.73%**;
EuroSAT macro-F1 is **86.84%**. Confusion matrices and all class metrics are in
[the raw result record](m1-evidence.json); accuracy alone selected the models.
These are modest single-seed starting points, with no tuning or test evaluation.

Both ran on the provided Tesla T4 from clean frozen source commit
`828cbf0d2a95df69ceae18e2883ce0c7fd9d3812`, with exact recipe/data/partition/contract
hashes in that record. Saved normalization used all 2,000 EuroSAT / 15,063 Brick-Kiln
training images only. Both selected `best.pt` checkpoints passed separate-process
full-validation and prediction revalidation with **zero score difference**
(tolerance 1e-6). No final test payload was opened or official split changed.

Run directories, relative to SageMaker `/home/sagemaker-user/GoTrain/`:

- EuroSAT: `artifacts/runs/20261031T142814768185Z-m-eurosat-manual/`.
- Brick-Kiln: `artifacts/runs/20261031T143113863281Z-m-brick-kiln-manual/`.
- Controller logs, executed batch driver, settled ledger and combined report:
  `artifacts/runs/classification-checks/`.

Each run retains its selected checkpoint, `record.json`, training/controller logs,
timing and timestamped `revalidation-*.json`. The raw result record includes the
selected checkpoint paths, sizes and SHA-256 values. The operator marked
`is_reference: true` only after complete validation and successful revalidation;
the manual runner deliberately leaves acceptance to this explicit step.

Both selected model/optimizer checkpoints and their records now have independent,
checksum-verified recovery copies on the custodian Mac. See the exact snapshot
receipts in [resources](RESOURCES.md#recovery-verification) and
[restore instructions](storage.md). Checkpoint restoration was byte-verified
locally; ML execution/revalidation ran only on SageMaker.

The two training runs consumed **745.49 s**; fresh-process revalidation consumed
**19.11 s**. The settled M1 ledger total, including earlier reserved access,
calibration and foundation smoke work, is **860.08 / 3,600 s**, with no active
reservation. This is the 1.5 evidence snapshot; `artifacts/m1-budget.json` remains
the live authority for subsequent work. Subsequent work is recorded below.

## Frozen segmentation recipes (1.6)

Frozen before either measured run: [PV4GER-Seg](../configs/reference-m-pv4ger-seg.json),
then [Chesapeake](../configs/reference-m-chesapeake.json). Use the calibrated
[FCN-ResNet50](https://docs.pytorch.org/vision/0.24/models/generated/torchvision.models.segmentation.fcn_resnet50.html) with random initialization (`weights=None`, `weights_backbone=None`),
no auxiliary head or imported weights. Torchvision's BSD-3-Clause implementation
and existing verified environment are unchanged. PV4GER keeps its RGB stem and
2-class head; Chesapeake uses a newly initialized 4-input stem (including NIR)
and a 7-class head. All output logits match native mask resolution.

Use batch 4, unweighted cross-entropy, SGD momentum 0.9, learning rate 0.01,
weight decay 0.0001, constant schedule, seed 2026 and float16 AMP (initial scale
1024). Apply fixed channel divisors, then mean/std fitted on all training images
only. Native 320×320 / 256×256 inputs: no resizing, cropping or mask interpolation;
paired train-only flips/90-degree rotations preserve alignment and integer IDs.
Keep all classes, including background and Chesapeake target 0; no ignored ID or
threshold tuning. Global full-validation macro IoU selects the best checkpoint,
with earliest checkpoint on ties. Report PV foreground IoU/F1 and Chesapeake's
separate target-0-ignored land diagnostic; neither selects the model. Empty/tiny
foreground and globally absent-class behavior follow the verified shared checks.

Use the existing 10-epoch / 5,000-step / 600-second first-hit cap per run, with
60 seconds reserved for full validation/saving. Fresh-process full-validation
revalidation must reproduce the selected score within 1e-6. No tuning search or
test access. Segmentation results and independent model backups are verified below.

Reproduce sequentially on the canonical SageMaker checkout, using the same `PY`
verification environment defined above:

```bash
$PY scripts/train.py train --recipe configs/reference-m-pv4ger-seg.json --data-root data/geo-bench/datasets
$PY scripts/train.py verify --run-id <pv4ger-run-id> --data-root data/geo-bench/datasets
$PY scripts/train.py train --recipe configs/reference-m-chesapeake.json --data-root data/geo-bench/datasets
$PY scripts/train.py verify --run-id <chesapeake-run-id> --data-root data/geo-bench/datasets
```

For existing retained runs, use only `verify`; repeated training is not required
for checkpoint recovery or M1 acceptance. The shared ledger admits jobs under the
current remaining budget, not a fresh allocation per command or clone.

## Verified segmentation results (2026-10-31)

| Task | Full-validation macro IoU | Images / pixels | Full epochs / total steps | Training wall time | Reload delta |
| --- | --- | --- | --- | --- | --- |
| PV4GER-Seg | **0.901692** (90.17%) | 403 / 41,267,200 | 5 / 3,846 | 547.46 s | 0 |
| Chesapeake | **0.405280** (40.53%) | 1,000 / 65,536,000 | 5 / 4,267 | 553.81 s | 0 |

PV foreground IoU / F1: **0.844123 / 0.915474**. Chesapeake land-only target-0-ignored macro IoU: **0.477636** (diagnostic only). The primary Chesapeake metric retains all seven classes.

Each run uses all 3,000 official training images for fitted normalization and the complete official validation split for global confusion-matrix scoring. No test payload or split modification occurred. Epoch totals count complete epochs; a time-capped run may include an additional partial epoch followed by complete validation. `budget_exhausted` records the agreed wall reserve, not an incomplete score. Exact statuses, class diagnostics, normalization, memory, recipe/data/partition hashes and checkpoint sizes/hashes are in [M1 evidence: segmentation](m1-evidence.json).

Both ran from clean frozen source `2786dfc31b4faa00a90a1da0ac22729cf3afc995` on the provided T4. Each selected `best.pt` was revalidated in a separate process with score delta 0.

- PV4GER-Seg: `artifacts/runs/20261031T144800853991Z-m-pv4ger-seg-manual/`.
- Chesapeake: `artifacts/runs/20261031T145719482888Z-m-chesapeake-manual/`.

Paths are relative to SageMaker `/home/sagemaker-user/GoTrain/`. Batch execution, controller logs and the settled 1.6 ledger are in `artifacts/runs/segmentation-checks/`. Both exact selected model/optimizer files have verified independent backups; see [recovery receipts](RESOURCES.md#recovery-verification).

## M1 reproducibility handoff (1.7)

[M1 evidence: handoff](m1-evidence.json) records the final fresh-process revalidation of **all four retained checkpoints**, with full-validation score delta 0 and matching hashes, recipe/source/data provenance, image/pixel counts and prediction shapes. The SageMaker safety suite passed all 12 tests; five explicit cases cover empty foreground, one correct foreground pixel, a missed pixel, a hallucinated pixel and an all-ignored diagnostic. Empty foreground is not dropped from primary scoring; globally absent classes follow the frozen union rule.

Final charged M1 GPU-job wall time: **2044.41 / 3,600 s**; reference training **1846.77 / 2,400 s**, checkpoint revalidation **102.16 / 240 s**. No active reservation remains. This is a completion snapshot; the live ledger remains authoritative. CPU checks/backup transfer are separate from GPU-job wall accounting.

All execution used the existing verified SageMaker venv without installation. The retained single-seed baselines establish starting points, not repeated-training stability or published test performance. M1 is complete; M2 planning is next.
