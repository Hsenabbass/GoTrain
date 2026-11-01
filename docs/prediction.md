# Model packages and standalone prediction

All four retained packages passed CPU prediction/CLI verification on SageMaker at
source ae7c246, outside the checkout with network/cache access denied. Predictions
matched the original M3 builders exactly. Independent recovery transfer, member
verification and restoration of all four retained package ZIPs passed. M4 also published one synthetic classification and one synthetic segmentation integration package under the same contract; both passed fresh isolated CPU parity with checkout/cache/network denied. [M4 evidence](m4-evidence.json) records verified results and receipts.

## Shared contract

`gotrain.packages.export_package(run, destination, class_names=..., history=...,
dataset=...)` consumes a trusted registered run directory, its checkpoint and
record. This is an operator API, not a browser path interface. It requires full
validation, primary seed 2026, matching checkpoint/recipe/contract hashes and
explicit class names (null where unknown). It never trains or finalizes a model.
Future custom-task runs use the same task specification and export interface.

A selected immutable version is `v1-<24 hex>` from canonical model metadata. It
binds inference weights, preprocessing, runtime, dependencies, terms and history
checksums, origin checkpoint/run, training code, validation and dataset identity.
Exports refuse to overwrite an existing version and preserve 15 GiB free disk
plus staging space. Source b609ef9 additionally passed the low-space rejection
check on SageMaker; package prediction contents are unchanged from ae7c246.
Trials remain in compact history;
only selected full-validation checkpoints become model versions. No M5 status is
implied. The ZIP filename is `gotrain-<task>-<version>.zip`, with one clean folder.

Contents: `weights.pt` (tensor state only), `model.json`, `predict.py`,
`requirements.txt`, `README.md`, `TERMS.md`, `history.json`, `checksums.json`.
No datasets, optimizer state, credentials, initialization cache or unrelated logs.
Weights and large exports remain ignored under `artifacts/models/`.

`gotrain.prediction.Predictor(package_directory)` verifies the package and loads
CPU float32 weights with `weights_only=True`. `predict(pixels, band_names,
input_divisors)` requires raw numeric CHW pixels plus the actual stored band order
and units/scaling declaration. It reuses checkpoint divisors and normalization,
without resize, crop or image repair. A matching channel count alone does not prove
spectral compatibility. GPU inference is deliberately unavailable in this runtime;
later GPU support must first use the shared M4 ledger/lock and admission guards.

Classification returns version, class ID/name and probabilities (uncalibrated).
Segmentation returns an aligned uint16 class-ID array; `save_mask` adds PNG mask,
preview, legend, optional RGB overlay and GeoTIFF mask retaining supplied CRS and
transform. Unknown Chesapeake class names remain null; verified numeric IDs apply.
Overlay stretch/opacity affect display only, never prediction inputs.

## Commands on SageMaker

Use the existing verified Python 3.12 environment; no new installation is needed.

```bash
# First export and verify together, using an empty destination:
python scripts/verify_packages.py --packages artifacts/models

# Alternatively export only (do not run both against the same destination):
PYTHONPATH=src python -m gotrain.packages --destination artifacts/models
```

Use existing verified versions for normal operation. Exports never overwrite;
choose a new empty destination only when a fresh verification is necessary.
The verifier exports all four retained M3 models, extracts each outside the
checkout, and uses a fresh isolated Python process. Network, initialization-cache
and checkout reads are denied. Compare CPU float32 logits with the original M3
model builder (`atol=rtol=1e-5`) and require identical predicted IDs. Each uses the
approved official validation example at index 0; no test samples or new training.
Exercise CLI prediction, incompatible shape/channel rejection and mask/CRS/transform
round trips (synthetic geographic metadata wrapped around the validation image).
Reuse existing M3 full-validation evidence. Evidence is written under
`artifacts/runs/m4-package-checks/`; frozen M1–M3 ledger hashes must remain unchanged.

After extracting a trusted package elsewhere:

```bash
python predict.py --image /path/image.tif --input-contract /path/input.json --output /new/path/result
```

`input.json` contains `band_names` and `input_divisors` describing that image.
Classification output is a new JSON file; segmentation output is a new directory.
PNG/JPEG/GeoTIFF are supported within the model's native shape and channel contract.
The direct requirements record the tested environment, not universal compatibility
or a transitive dependency lock. Compare the ZIP SHA with the trusted receipt before
extracting it; package checksums prove integrity, not publisher authenticity.

## Terms review

Review date: 2026-11-01. TorchVision architecture code is BSD-3-Clause, but its
[pretrained-weight notice](https://docs.pytorch.org/vision/0.24/models.html#general-information-on-pre-trained-weights)
requires a separate use/terms review. M3's ImageNet backbone provenance is retained.
Public redistribution permission for the derived weights is unresolved; these
artifacts remain private research outputs in the already authorized workspace and
recovery location. Do not publish the weight ZIPs or claim commercial permission.
This explicitly reported restriction remains a 4.1 delivery limitation. No source
code license is treated as a license for training data or weights.
