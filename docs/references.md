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

Results are pending. Accept only finite complete-validation metrics, saved
checkpoints with source/config/data/preprocessing provenance, and fresh-process
revalidation within absolute 1e-6. No test sample is accessed. Full logs/checkpoints
remain under their run directories; small result summaries and safe locations are
linked here after verification. Independent checkpoint backup follows
[storage/recovery](storage.md).
