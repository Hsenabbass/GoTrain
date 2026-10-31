# M3: Find better models efficiently

**Status:** planned; nothing below is implemented or verified yet.
**GitHub:** [M3](https://github.com/Hsenabbass/GoTrain/milestone/3)
**Direction:** [Agreed M3 outcome](../PROJECT_PLAN.md#m3-demonstrate-reliable-improvement)

## Outcome and scope

Give Claude enough reliable choices to improve models, rather than only changing
one learning rate. Run the same inspect → prepare → shortlist → compare → tune →
verify pipeline across all four tasks. Keep the best validated model, even when
no new model wins. Seek the best result within the budget; global optimality is
not a promise.

Build on the [M2 tools and evidence](m2-engine.md), existing runner, frozen
[data/evaluation contracts](../data.md), records and backups. Use three issues,
including their checks and documentation. All execution stays on SageMaker.

### Does this work for other datasets?

Yes, through a shared task description and data adapter, rather than task names
inside the agent. M3 must remove the current EuroSAT-only controller and fixed
model/task pairs. The four benchmarks are our measured acceptance cases.

Here, classification means one class per image; segmentation means one class per
pixel (semantic segmentation). M3 also accepts a local manifest of PNG/JPEG or
GeoTIFF images, with class labels or aligned integer masks, explicit train/valid
membership and channel/label metadata. Prove this path with a small non-GEO-Bench
fixture for each task type, with different channel/class counts and image sizes;
that verifies plumbing, not real-world accuracy.

New datasets still need a readable format, valid labels and enough training and
validation examples. If bands, units, class meanings or splits are unclear, ask
for the missing facts before training. Text/tabular classification, multilabel,
instance segmentation, video and arbitrary file formats need another adapter or
task contract; calling them classification/segmentation does not make them
compatible. M4 owns user-facing imports, upload UI and broader format adapters.
This is a reusable image pipeline, not a claim to handle literally every dataset.

## Resources reviewed first

Primary sources reviewed 2026-10-31. These support the choices below; model counts,
search ranges and budgets are our engineering choices, not published guarantees.

| Source | What we use from it |
| --- | --- |
| [GEO-Bench official repository](https://github.com/ServiceNow/geo-bench#known-issues) | EuroSAT/Brick-Kiln have incorrect band metadata; the existing corrected contracts remain authoritative for our pinned data. |
| [Torchvision 0.24 models/weights](https://docs.pytorch.org/vision/0.24/models.html) | Reuse installed architectures; record explicit weight versions and their preprocessing. Weight terms need checking separately. |
| [TorchGeo pretrained model catalog](https://docs.torchgeo.org/en/stable/api/models.html#pretrained-weights) | Find sensor/band-compatible pretrained backbones; use it as a catalog, not a reason to install another whole stack. |
| [Hugging Face model cards](https://huggingface.co/docs/hub/model-cards) | Inspect intended task, library, datasets and license before admitting a checkpoint. A model card is evidence to review, not a guarantee of compatibility. |
| [scikit-learn leakage guidance](https://scikit-learn.org/stable/common_pitfalls.html#data-leakage) and [grouped splitting](https://scikit-learn.org/stable/modules/cross_validation.html#cross-validation-iterators-for-grouped-data) | Fit preprocessing only on training data; keep related examples together when defining splits for new data. No scikit-learn dependency is required for these rules. |
| [Random Search (Bergstra & Bengio)](https://jmlr.org/papers/v13/bergstra12a.html) and [Hyperband (Li et al.)](https://www.jmlr.org/papers/v18/16-558.html) | Prefer a small bounded search to a large grid; spend more compute on promising trials. Borrow staged allocation without implementing a full tuning framework. |

## The pipeline

### 1. Understand the task before spending GPU time

Make one task record: task type, classes, metric, sample counts, image sizes,
sensor, band order/wavelengths, pixel units, missing-value codes, mask IDs and
available compute. Include dataset version, split hashes and geographic/time/group
information where available. Inspect train/validation only; reuse M1 inspection
for the four benchmarks instead of repeating it.

Check unreadable images, bad labels, empty classes, duplicates across development
splits, missing pixels and image/mask alignment. Report suspected label errors.
For benchmarks, preserve samples, labels, official splits and frozen scoring.
For new data, agree and version repairs/exclusions before search. If no splits
exist, split once before fitted preprocessing: group tiles from the same scene,
site or subject together (and use time order for future prediction). Balance class
coverage where feasible; do not randomly scatter neighboring tiles across splits.
If grouping metadata is unavailable, record the leakage risk. Test stays sealed.

### 2. Prepare the data for the candidate model

- **Bands and units:** use actual storage order and scale each band correctly.
  Brick-Kiln's true-colour channels differ from reflectance; Chesapeake is already
  scaled. Channel count alone never proves two sensors/checkpoints match.
- **Normalization:** use the pretrained checkpoint's documented scaling/statistics
  when applicable; do not also apply training-standardization blindly. Otherwise
  fit per-channel statistics on training only. Save the exact transform for inference.
- **Missing pixels:** detect and report them; no silent zero-filling, guessed
  ignore labels or benchmark sample removal. New-data imputation/valid-pixel rules
  must be explicit, training-fitted where learned, and frozen before comparison.
- **Size and alignment:** preserve native resolution first. If a model needs
  padding/resizing, document it; restore segmentation logits to the original grid
  before scoring. Use paired spatial transforms and nearest-neighbor for class
  masks. Large new rasters use aligned windows; split by scene before windowing,
  stitch predictions once, and avoid double-counting overlapping pixels.
- **Augmentation and imbalance:** use train-only flips/rotations when task meaning
  permits. Start with cross-entropy. Add train-derived class weights or a Dice
  loss term only when rare-class/foreground errors justify it; retain the same
  primary metric. Avoid stacking oversampling and weighting without evidence.

Freeze the data contract separately from candidate settings. Model-specific
preprocessing is part of the pipeline, not a change to benchmark membership.

### 3. Pick a small shortlist intelligently

Keep a small supported model catalog, then choose **at most two new candidates
per task initially**, alongside its retained reference. Do not train every model
in the catalog. Rank candidates by task, sensor/bands, object size, label volume,
pretraining match, measured memory/runtime, and download/dependency cost. Record
one short reason per choice. These are useful priors, not predictions of accuracy.

| Data/task | First choices to consider; only admit compatible ones |
| --- | --- |
| RGB classification | ImageNet-pretrained ResNet18; a small MobileNet alternative when speed/memory matters. |
| Multispectral classification | Sensor-compatible pretrained ResNet18; otherwise reuse an ImageNet backbone with an explicitly adapted input layer, retaining all meaningful bands. |
| RGB segmentation / tiny foreground | Existing FCN with an ImageNet-pretrained backbone and new task head; lightweight DeepLabV3-MobileNet as the architecture alternative. Keep small objects visible. |
| RGB + NIR segmentation | The same segmentation choices with an explicitly adapted four-channel input; prefer matching aerial weights only if provenance and integration pass. |

These are starting choices, not fixed winners. Existing Torchvision code comes
first. Replace the output head for our classes. For extra channels, preserve RGB
weights only on verified RGB positions and explicitly initialize the remaining
channels; record the rule and test it. Do not pretend new channels are pretrained.
Do not force 224-pixel crops/upscaling just because a classification weight lists
that default; compare the full preprocessing choice under the task's budget.

**Online expansion is conditional.** If the shortlist has a clear coverage gap
(e.g. no matching multispectral weights), or both candidates fail for a diagnosed
reason, permit one focused catalog/Hub lookup per task, capped at 10 minutes and
one added candidate. It replaces a remaining trial; it does not increase budgets.
Check source revision/hash, bands, preprocessing, architecture, license and known
benchmark train/validation/test overlap. Reject target-label-finetuned checkpoints
and known held-out contamination; record unknown pretraining overlap. Published
scores are context, not our validation results.

Claude may request a candidate ID/reason through a typed tool. Trusted code checks
and registers compatible weights. No arbitrary Hub code, shell or install tool;
load reviewed tensor weights through supported architectures. Cache downloads,
reuse them, and fall back when access or compatibility fails. No dependency
upgrade is justified merely to try a model.

### 4. Measure cost, then compare

“Bandwidth” includes both spectral bands above and network/storage here: inspect
metadata before downloading, budget weight bytes and transfer time, cache weights
on SageMaker, read local data, and record source/hash. Start with a 500 MiB total
new-weight download ceiling and a 120-second cap per retrieval, with one transient
retry inside that time/byte allowance. Skip oversized or unavailable candidates.

For each new model/input recipe, use a short training-only probe to check shapes,
finite loss, peak VRAM, steps/second and data-loading cost. Choose the largest
stable batch within existing task ceilings; do not add loader workers unless I/O
is the measured bottleneck. Verify image/mask transforms and prediction shapes.

Screen candidates cheaply on training data with the same full validation split.
Use equal screening wall caps, log actual steps/epochs, and inspect learning curves.
Do not discard a slow starter solely on its first epoch; allow a useful warm-up
and stop only a clearly invalid/diverging/unpromising trial at a recorded boundary.
If the budget cannot support a meaningful screen, try fewer models. Screening
scores are provisional. Compare finalists against M1 with a common final run cap,
unchanged metric/splits and explicit differences in pretraining, epoch/step ceilings and total search
cost. Keep frozen M1 recipes intact; if testing a longer-training reference as a
control, give it a new run/recipe ID and report it separately from M1. Never compare a subset score to a full-validation reference.

### 5. Tune only the promising model

Claude diagnoses learning curves and per-class errors and chooses the next small
search. A deterministic seeded sampler handles numeric proposals; typed tools
validate them. No Optuna/service is needed for this small search.

| Evidence | Next useful change |
| --- | --- |
| Loss unstable or not learning | Check data/gradients first; then lower or raise learning rate. |
| Training and validation both still improving | Allow more epochs/steps within the same wall cap; do not keep M2's arbitrary 10-epoch ceiling. |
| Training good, validation poor | Try weight decay or mild augmentation; do not just train longer. |
| Rare classes / panels missed | Try class-weighted cross-entropy or segmentation CE + Dice, checking class diagnostics. |

Start with a short pretrained head warm-up, then fine-tune the backbone at a lower
learning rate; keep the warm-up short enough to leave a real fine-tuning budget.
Use one recorded scheduler, e.g. cosine decay, not a scheduler search. For AdamW
fine-tuning, initial learning-rate range `1e-5–1e-3` and weight decay `1e-6–1e-2`
(log-uniform) are proposed starting ranges, not universal optima. SGD recipes use
a separate `1e-3–1e-1` LR range; never mix the ranges across optimizers. Reuse a
reasonable default batch after the probe; do not jointly search everything.

Try at most two tuning proposals after screening, varying one or two relevant
settings. Each proposal names its hypothesis and parent. Each fresh training run
starts from the same declared initialization for a fair recipe comparison.
Extending a screen is allowed only for an unchanged recipe with optimizer,
scheduler, scaler, random state and data-order state restored; otherwise retrain
and charge all time. No approximate resume claim. Preserve prior best after a
failure. Stop at the budget or after two non-improving proposals; do not generate
unlimited follow-up experiments from repeated validation feedback.

### 6. Confirm, retain and back up

Run the chosen recipe to the agreed final budget if its screen was shorter. For
a promising gain, reserve a second seed for both candidate and matching reference;
compare the pair at the same run cap. Reuse existing matched results when valid.
Two seeds are a repeatability check, not proof of significance. If confirmation
cannot fit, label the gain provisional; report every seed, not only the best.
Select by the frozen full-validation metric; keep the earlier pipeline on ties.
A repeatability claim compares seed results, not the luckiest checkpoint across seeds.

Reload the retained checkpoint in a fresh process and reproduce full-validation
score/prediction within the existing tolerance. Retain model, channel/preprocessing
rules, config/code/weight/data versions, parent/hypothesis, seed, validation counts,
resources, failures and decision. Back up important completed runs and verify the
receiving copy per [storage/recovery](../storage.md). Test evaluation remains M5.

## Work sequence

| Step / issue | Prerequisites | Tools, inputs, outputs | Completion check |
| --- | --- | --- | --- |
| [3.1: Add reusable task preparation and model choices](https://github.com/Hsenabbass/GoTrain/issues/15) | Completed M2 | Existing data/model modules + manifest adapter + reviewed Torchvision weights → task-driven tools and small catalog | Four existing contracts preserved; non-GEO classification and segmentation fixtures pass; bands, pretrained transforms, masks and output heads verified on SageMaker. Incompatible/contaminated candidates rejected. |
| [3.2: Add bounded model comparison and tuning](https://github.com/Hsenabbass/GoTrain/issues/16) | 3.1 | Existing controller/ledger/records → task parameter, staged search, typed knobs and enforced M3 limits | Candidate selection, numeric tuning, full-validation selection, call/download caps and stop/failure rules pass focused checks. Interrupted sessions retain records; stale GPU reservations block until audited. Safe restart can read prior results without resetting usage or duplicating jobs. |
| [3.3: Run and verify the four-task search](https://github.com/Hsenabbass/GoTrain/issues/17) | 3.2 | Sequential SageMaker jobs + retained M1 references → comparisons, selected pipelines and recovery receipts | Every task has a completed autonomous comparison and explained keep/reject outcome; reloads/backups verified; seed confirmation recorded where applicable. One bounded interruption/recovery exercise proves no lost prior best or duplicate charged work. No test access; M4 handoff is current. |

## Decisions and open questions

- **2026-10-31, user direction:** M3 must think about data/model fit, transfer
  cost and useful tuning, and support new image tasks through a common contract.
  This extends M3 with a local manifest adapter; broad import UX stays in M4.
  Replace M2's EuroSAT-only/fixed-recipe limits through reviewed code, never by
  giving Claude evaluator/budget/code-edit access.
- **Proposed M3 ceilings:** 7,200 GPU-job wall seconds total: initially 1,500 per
  benchmark task (6,000), plus 1,200 shared for matched-seed confirmation, probes,
  fixture checks, verification and failures. All jobs, including failures/probes,
  count; no task or shared allowance bypasses the total. At most five new training
  attempts per task, plus one shared eligible failure retry. A confirmation or
  restarted training attempt counts too; reduce tuning breadth to fund confirmation.
  At most 600 seconds, 50 epochs or 10,000 steps per run, first cap wins; final
  reference/candidate comparison uses the same 600-second cap. Save the existing
  validation reserve. Counts are ceilings, not a requirement to spend them.
- Before execution, 3.2 must turn these into versioned enforced settings and reserve
  a feasible task schedule using observed throughput. Keep a M3 ledger under the
  shared GPU lock; never reset M1/M2. Keep existing VRAM/disk/storage guards and
  the two-hour final-submission buffer. Record any inadequate convergence budget
  instead of calling an undertrained model inferior. Exact organizer quotas remain
  unknown; these are internal project allocations, not confirmed entitlements.
- Per-task agent invocation: at most 24 model requests, 32 tool calls, 2,048 output
  tokens/request and 2,400 wall seconds; all repair/retry requests count. Return
  compact score/error summaries to Claude and retain full records on disk, avoiding
  M2's repeated large payloads. Enforce metadata/search/download allowances in
  trusted tools. Total GPU use remains governed by the shared M3 ledger even if
  the agent is restarted. Stop on permission/contract/test/integrity failures.
- Prefer no new library. TorchGeo/Hub are discovery sources; install an additional
  runtime package only if a selected candidate demonstrably requires it and its
  value exceeds the integration cost. No new cloud services, UI, code-writing
  agent, exhaustive model zoo or separate tuning framework in this milestone.

## Verification and evidence

| Outcome | Check and environment | Result | Evidence |
| --- | --- | --- | --- |
| Task preparation/model admission (3.1) | Focused fixtures and model shape/preprocessing checks on SageMaker | Not run | Add implementation evidence here |
| Search and recovery guards (3.2) | Budget/selection/stop/restart checks on SageMaker | Not run | Add results here |
| Four task comparisons (3.3) | Full validation, seed records, checkpoint reload and independent backup | Not run | One M3 evidence record and resource receipts when available |

## Handoff

**Last updated:** 2026-10-31.
**Current state:** research and plan only. M1/M2 remain complete; M3 adapter, model catalog, tuning and new limits are not implemented. Sources are not proof of SageMaker compatibility.
**Blockers:** none for planning. Dataset metadata gaps, exact weight licenses/preprocessing, candidate throughput and usable remaining budget are admission checks during implementation, not assumed facts.
**Next action:** implement 3.1 when authorized. Keep shared code/docs; add only what the first working pipeline needs.
**Synchronization:** plan and three linked issues published together; local/GitHub source aligned at the planning commit. SageMaker has not been updated by this planning task. No execution or installs performed.

## Completion

Pending the three checks above. Improvement is measured, never guaranteed. If no
candidate wins, retain the reference and explain why; do not declare improvement.
Hand verified task pipelines and preprocessing to M4; keep final test access in M5.
