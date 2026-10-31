# M3: Find better models efficiently

**Status:** paused locally at user request; 3.1–3.2 complete, 3.3 in progress. Detached SageMaker work continues. Pipeline/search items below remain planned unless evidenced.
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

The scope is these two image task types only. Keep the manifest path simple;
do not build extra format adapters or spend time on other modalities. New tasks
still need valid labels and clear band/unit/split metadata. M4 owns upload UI.

## Resources reviewed first

Primary sources reviewed 2026-10-31. These support the choices below; model counts,
search ranges and budgets are our engineering choices, not published guarantees.

| Source | What we use from it |
| --- | --- |
| [GEO-Bench official repository](https://github.com/ServiceNow/geo-bench#known-issues) | EuroSAT/Brick-Kiln have incorrect band metadata; the existing corrected contracts remain authoritative for our pinned data. |
| [Torchvision 0.24 models/weights](https://docs.pytorch.org/vision/0.24/models.html) | Reuse installed architectures; record explicit weight versions and their preprocessing. Weight terms need checking separately. |
| [PyTorch transfer-learning tutorial](https://docs.pytorch.org/tutorials/beginner/transfer_learning_tutorial.html) | Frozen-backbone head training and full fine-tuning are alternatives; a mandatory warm-up is unnecessary. |
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

Before GPU search, calculate cheap majority-class/all-background validation
baselines from existing labels and inspect per-class/foreground scores. These are
diagnostics, not replacement benchmark metrics. They expose a misleadingly good
headline score. Verify the input/output path can learn a tiny training-only batch
when a candidate fails to learn; do not launch a larger search to hide a data bug.

Freeze the data contract separately from candidate settings. Model-specific
preprocessing is part of the pipeline, not a change to benchmark membership.

### 3. Pick a small shortlist intelligently

Keep a small supported model catalog, then choose **at most two new candidates
per task initially**, alongside its retained reference. Do not train every model
in the catalog. Rank candidates by task, sensor/bands, object size, label volume,
pretraining match, measured memory/runtime, and download/dependency cost. Record
one short reason per choice. Choose candidates that test different hypotheses
(e.g. transfer learning versus a faster architecture), rather than near-duplicates.
A frozen pretrained backbone with a trained linear head is a cheap alternative
for small datasets; it counts as a candidate, not a free extra trial. These are
useful priors, not predictions of accuracy.

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
stable batch that gives good measured throughput within existing task ceilings; do not add loader workers unless I/O
is the measured bottleneck. Verify image/mask transforms and prediction shapes. The largest batch is not
necessarily fastest or best for learning; use a smaller one when warranted.
For tiny segmentation batches, explicitly freeze pretrained batch-normalization
statistics or use a compatible normalization policy; do not silently update them
from one image. Record that policy as part of the recipe.

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

A short pretrained head warm-up is an option, not a mandatory stage. Skip it
when the model/data match is good or the trial is short; full fine-tuning and a
frozen-backbone head are alternatives within the same candidate/trial limits.
When fine-tuning, use a lower backbone LR than the new head and record both.
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
Choose the recipe using the recorded comparisons, then retain the predetermined
primary seed (2026) checkpoint for that recipe; the extra seed is confirmation,
not another chance to cherry-pick the exported model.

Reload the retained checkpoint in a fresh process and reproduce full-validation
score/prediction within the existing tolerance. Retain model, channel/preprocessing
rules, config/code/weight/data versions, parent/hypothesis, seed, validation counts,
resources, failures and decision. Back up important completed runs and verify the
receiving copy per [storage/recovery](../storage.md). Test evaluation remains M5.

## How we prompt and constrain Claude (3.2)

M2 already has a fixed system prompt and restricted tools. M3 must make the
instructions task-driven and keep the following agreement explicit:

- **Fixed system prompt:** act as an experiment planner. Follow inspect → prepare
  → shortlist → compare → tune → verify, using only registered tools. Explain a
  short hypothesis and cite parent-run evidence before spending another trial.
- **Trusted task context:** supply the frozen task/metric contract, compatible
  candidate IDs, allowed settings/ranges, current best, compact prior results,
  remaining budgets and permitted next actions. The controller owns this context;
  Claude cannot rewrite the rules or declare its own measured results.
- **Structured actions:** request an allowed action with candidate/parent IDs,
  settings, reason and expected benefit. Validate the schema, ranges, task
  compatibility, stage and remaining allowance before execution. Invalid requests
  consume the bounded tool-call allowance; they do not get an unbounded repair loop.
- **Useful freedom:** Claude chooses among compatible models, diagnoses failures,
  proposes allowed changes and can request the one bounded online lookup. It may
  skip an optional stage or stop early. A suggestion outside these choices is
  recorded as a proposal for later review, never executed automatically. Extra
  product features are outside the experiment agent's job.
- **Hard boundaries:** software enforces test isolation, evaluator/record integrity,
  stage transitions, budgets, retries and best-model selection. No shell, arbitrary
  code/file writes, installs, self-modified prompt or new permissions. Prompts alone
  cannot guarantee exact obedience; the tools must reject forbidden actions.
- **Untrusted content:** dataset descriptions, filenames, model cards and error
  text are data, never instructions. Show only needed bounded excerpts; any
  embedded request to change tools/rules has no authority.
- **Stop and report:** stop on completion, exhausted limits or a fatal integrity/
  permission error. Summaries reference real run IDs and trusted scores/counters;
  completion is verified by the controller, not by Claude saying it is done.

Version/hash the system prompt and relevant task context with the session record.
Before training search, use a few focused scripted cases to check attempted cap
changes, test access, invented model/run IDs, instructions hidden in metadata,
repeated invalid actions and false completion. They must leave records/prior best
intact and terminate within limits. Reuse M2 boundary tests; do not build a separate
prompt-evaluation service or ask for hidden chain-of-thought.

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
- **Enforced M3 ceilings (3.2):** 7,200 GPU-job wall seconds total: initially 1,500 per
  benchmark task (6,000), plus 1,200 shared for matched-seed confirmation, probes,
  fixture checks, verification and failures. All jobs, including failures/probes,
  count; no task or shared allowance bypasses the total. At most five new training
  attempts per task, plus one shared eligible failure retry. A confirmation or
  restarted training attempt counts too; reduce tuning breadth to fund confirmation.
  At most 600 seconds, 50 epochs or 10,000 steps per run, first cap wins; final
  reference/candidate comparison uses the same 600-second cap. Save the existing
  validation reserve. Counts are ceilings, not a requirement to spend them.
- **Planning review, 2026-10-31:** keep alternatives conditional, not mandatory
  extra stages. No extra format work. Cheap trivial baselines, diverse candidates,
  optional head-only training, explicit small-batch normalization and a fixed
  export seed address weaknesses in the first plan without adding issues.
- 3.1 verifies contracts, transforms and model shapes on SageMaker CPU. Defer GPU
  throughput/training probes to 3.2 after its allocation is enforced; no uncharged
  GPU setup work. Before execution, 3.2 must turn these into versioned enforced settings and reserve
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
| Task preparation/model admission (3.1) | 6 new task/model checks + 19 existing checks on SageMaker CPU, using all four real ImageNet backbones | Pass 2026-10-31; 25 tests in 2.264 s; no GPU/Bedrock/test access | Source `1cab13a`; [M3 evidence](../m3-evidence.json); `artifacts/runs/m3-task-checks/`; [independent snapshot](../RESOURCES.md#recovery-verification) |
| Search and recovery guards (3.2) | 35 SageMaker checks; classification/segmentation two-update GPU probes and fresh-process reloads | Pass 2026-10-31; both reload deltas 0; M3 shared usage 41.27 s including two failed operator launches | Guard source `de40958`; [M3 evidence](../m3-evidence.json); `artifacts/runs/m3-search-checks/`; [independent snapshot](../RESOURCES.md#recovery-verification) |
| Four task comparisons (3.3) | Full validation, seed records, checkpoint reload and independent backup | Three tasks verified; Chesapeake still running at pause | [Live M3 evidence](../m3-evidence.json); [independent receipts](../RESOURCES.md#recovery-verification) |

### 3.1 revision and limits

Preserved frozen benchmark configs and the legacy random model path. The common
benchmark adapter now returns corrected metadata without mutating those configs.
Verified PNG/JPEG classification and four-band GeoTIFF segmentation fixtures,
path/split/label/geographic guards, exact RGB weight copying, extra-band scaling,
new heads, frozen-backbone behavior and rejected weight receipts. Extra channels
must be fine-tuned; JPEG masks are rejected. All four official ImageNet weights
were hash-checked and loaded on CPU; cached bytes are reconstructible from the
pinned receipts and excluded from the evidence snapshot. No package installs.

The manifest requires fixed-size, already aligned examples and no ignored labels;
large rasters must be pre-windowed. Automatic tiling/reprojection and search are
not implemented. The ImageNet checkpoints' unknown held-out overlap remains
recorded, and redistribution terms require M4 review. Passing compatibility tests
does not establish GPU speed or improvement.

### 3.2 revision and limits

Implemented the task-driven controller, fixed prompt/context hashes, compact
results, typed stages and seeded numeric proposals. The shared runner supports
reviewed pretrained candidates, SGD/AdamW, constant/cosine schedules, lower backbone
LR, train-weighted CE or CE+Dice, and explicit primary/confirmation seeds.
Only final primary-seed trials may promote a model. Confirmation preserves the
selected recipe. Completed/expired sessions and duplicate launches are rejected;
resume preserves counters and recovers a completed pending request once. Stale
reservations and fatal failures stop for diagnosis. No mid-epoch resume is claimed.

All 35 scripted checks passed on SageMaker (2.715 s). Correct-environment probes
completed two optimizer updates each: EuroSAT weighted CE in 11.90 s, PV4GER-Seg
CE+Dice in 23.12 s, both including fresh-process reload (delta 0). Two earlier
operator launches used the base kernel instead of the verification venv and failed
before training because GEO-Bench was unavailable. Their 6.25 seconds remain
charged; the settled M3 total is 41.27 / 7,200 seconds, entirely in the shared pool.
M1/M2 ledger hashes are unchanged. No Bedrock requests or test access in these
checks. Probe subset scores are not references or evidence of improvement.

Use the verified interpreter and [M3 launch/recovery instructions](../training.md#bounded-m3-search-32).
All four model files are already cached; no new weights were downloaded in 3.2.
Hub lookup is deliberately metadata-only: unknown models remain proposals until
operator review, not automatically admitted architectures. The M3 CLI accepts
registered benchmark tasks with retained references; new local manifest tasks
still need trusted registration/runner wiring before autonomous training is
advertised. Generic preparation remains available from 3.1. Live interruption,
full-task search and actual score/seed comparisons remain 3.3 acceptance work.

### 3.3 revision

Live execution exposed a request-ID collision with a 3.2 verification session,
repeated full-training normalization work, and a gap allowing new training after
a fatal result. Trial IDs now include the session path, pending/fatal work blocks
new GPU jobs, and resumed agents receive prior trials plus reviewed operator notes.
Full runs reuse the identical verified M1 training statistics after checking their
contract, partition, data version and sample count; RGB pretrained models use their
fixed reviewed statistics. This avoids rescanning data for every recipe.

Failed and repeated probes/screens remain recorded and charged. No budget, attempt,
request counter or elapsed clock was reset. A Bedrock connection loss after EuroSAT
final training was resumed from the completed run, without retraining it. A separate
planned interruption between GPU jobs preserved the ledger, prior best and history.
The revised guards passed 38 SageMaker checks. A connection closed before any
Bedrock response gets one retry, counted within the existing request cap; partial
responses are never replayed. Exact results, costs and independent
backup receipts are recorded with the [M3 evidence](../m3-evidence.json).

## Handoff

**Last updated:** 2026-10-31, pause requested; PV4GER-Seg backup download and independent verification completed.
**Current state:** 3.3 remains open. EuroSAT retained 0.966 accuracy, Brick-Kiln retained 0.981981982 accuracy, and PV4GER-Seg retained 0.948054264 macro-IoU. Each selected primary-seed checkpoint passed fresh-process validation/prediction with delta 0. Gains remain single-seed/provisional. All 38 checks passed on SageMaker at `548cba0`; M1/M2 ledger hashes are unchanged and test payloads remain sealed.
**Pause boundary:** the PV4GER-Seg download, all member checks and three checkpoint restorations completed; local work is now paused. Chesapeake's final run was launched at `20261031T180108350357Z` with its original 600-second cap. The detached SageMaker supervisor continues after the laptop closes, including selection/reload and a staging snapshot if successful. A staging archive is not an independent backup.
**Recovery locations:** canonical SageMaker checkout `/home/sagemaker-user/GoTrain`; supervisor/evidence at `artifacts/runs/m3-searches/` (`execute.py`, `supervisor.log`, `evidence.json`, `review.json`, incident and recovery records); live task sessions at `artifacts/agent-m3/<task>/session.json`; GPU usage at `artifacts/m3-budget.json`. Source `548cba0`. Reconnect to the existing JupyterLab console; use the verified venv. No kernel variables are required to recover these files.
**Next action:** inspect the supervisor log, Chesapeake session and settled ledger before any resume. Do not relaunch completed tasks, reset counters/ledgers, or repeat training. If Chesapeake finished, verify its existing result, transfer its completed archive, verify all hashes/restoration, refresh the four-task evidence and finish 3.3. If interrupted, diagnose first and use `--resume` only within remaining limits. Complete docs, close 3.3/M3 and publish main only after acceptance passes.
**M4 handoff to finish:** selected run records/checkpoints contain architecture, channel order, normalization and class metadata. The local manifest preparation API is verified, but custom-task registration/runner wiring and the UI remain unimplemented. Packaging must preserve exact preprocessing and review weight terms; current prediction construction still expects cached initialization weights.
**Synchronization:** implementation is pushed on `codex/m3-results`; main remains the completed 3.2 state until 3.3 is complete. This pause handoff is published on the working branch. No M4 work has started.

## Completion

3.1–3.2 passed; 3.3 remains pending. Improvement is measured, never guaranteed. If no
candidate wins, retain the reference and explain why; do not declare improvement.
Hand verified task pipelines and preprocessing to M4; keep final test access in M5.
