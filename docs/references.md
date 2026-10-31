# M1 reference results

Task [1.5](https://github.com/Hsenabbass/GoTrain/issues/10): classification starting
points, separate from the [foundation smoke checks](foundation.json). These are
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
[the raw result record](classification.json); accuracy alone selected the models.
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
the live authority for subsequent work. Task **1.6** is next; M1 remains open.
