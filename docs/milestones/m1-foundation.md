# M1: Establish the foundation

**Status:** complete 2026-10-31; tasks 1.1–1.7 verified.
**GitHub:** [M1](https://github.com/Hsenabbass/GoTrain/milestone/1)
**Direction:** [Agreed M1 outcome](../PROJECT_PLAN.md#m1-establish-the-foundation)

## Outcome and scope

Deliver verified required access, documented task/evaluation contracts and explicit
resource budgets, and reusable manual training/validation recipes with starting
results for all four selected tasks. These are the fixed reference points for M3,
not promised performance targets. M2 will turn the working operations into tools
and an autonomous improvement loop.

Prerequisites are the organizer's private JupyterLab link/role and team GitHub
access. Local GitHub access does not prove SageMaker, GPU, Bedrock or storage access.
All runtime work happens on the provided SageMaker environment. The initial
planning change performed no runtime work; current access-check progress is
recorded in the verification and handoff sections below.

The Strands response/tool-call smoke test belongs here; the autonomous engine,
agent code-editing controls, broad recovery/restart tests, tuning search, UI,
arbitrary imports, production exports and final test evaluation belong later.
Do not add cloud resources, hosted services, a database, or multi-agent orchestration.

## Work sequence

GitHub issues own task state and detailed acceptance checks. Each row below links
its implementation issue; use that issue for ongoing discussion and evidence.

| Step / issue | Prerequisites | Tools, inputs, outputs | Completion check |
| --- | --- | --- | --- |
| [1.1: Verify SageMaker, Bedrock, storage and development access](https://github.com/Hsenabbass/GoTrain/issues/6) | Organizer access and team permissions | SageMaker GPU, Bedrock/Strands, PyTorch, storage, GitHub → verified setup and capacity inventory | Required model responds and calls a harmless tool; GPU, persistence/disconnect and SageMaker clone/push checks have sanitized evidence. |
| [1.2: Inspect the four GEO-Bench datasets without test access](https://github.com/Hsenabbass/GoTrain/issues/7) | 1.1 | GEO-Bench/Hugging Face; selected train/validation splits → sourced data contracts | All four task versions, loader IDs, channels/scales, labels, split handling and data issues documented without loading test samples. |
| [1.3: Define task contracts, evaluation rules and measured budgets](https://github.com/Hsenabbass/GoTrain/issues/8) | 1.1, 1.2 | Data contracts, organizer rules, bounded calibration → input/output, metric and budget definitions | Scoring rules and numeric caps recorded before reference training; unresolved requirements remain explicit. |
| [1.4: Build the shared manual training and validation foundation](https://github.com/Hsenabbass/GoTrain/issues/9) | 1.3 | PyTorch, verified dependencies, configs, storage → shared train/validation path and run records | Split/metric/preprocessing/budget checks pass; a small run saves a checkpoint and reloads for prediction. |
| [1.5: Record EuroSAT and Brick-Kiln classification references](https://github.com/Hsenabbass/GoTrain/issues/10) | 1.4 | EuroSAT then Brick-Kiln → two fixed recipes and validation records | Full-validation scores, traceable configs/logs/checkpoints and checkpoint revalidation evidence. |
| [1.6: Record PV4GER-Seg and Chesapeake segmentation references](https://github.com/Hsenabbass/GoTrain/issues/11) | 1.4 | PV4GER-Seg then Chesapeake → two fixed recipes and validation records | Full-validation scores, correct mask/channel handling and checkpoint revalidation evidence. |
| [1.7: Verify reproducibility and complete the M2 handoff](https://github.com/Hsenabbass/GoTrain/issues/12) | 1.5, 1.6 and all earlier evidence | Fresh-process SageMaker checks and documentation review → completed evidence record | Every milestone outcome evidenced; four reference results usable by M2/M3; docs and GitHub agree. |

Work within each task family may proceed as its data contract is ready, but no
reference run precedes its verified metric and numeric caps. Classification and
segmentation share one GPU/storage budget: schedule jobs sequentially initially.
No speculative owners, dates, package versions, architecture choices or experiment
counts are assigned. Choose recipes after actual data/capacity checks.

## Decisions and open questions

### Constraints carried into implementation

- **Data:** use only the four tasks already selected in the project plan. Verify
  loader identifiers rather than treating shorthand as executable loader names.
  Preserve official splits and labels. Fit learned preprocessing on training only.
  Resolve EuroSAT/Brick-Kiln band metadata and scale issues using versioned official
  sources; verify PV4GER image/mask alignment and Chesapeake channels/ignored IDs.
- **Test isolation:** no test sample inspection, previews, scoring, or tuning in M1.
  Metadata-only split checks are allowed. If a task download bundles test files,
  keep them sealed; do not enumerate/decode samples. Development entry points must
  reject test before loading it, with a synthetic check demonstrating rejection.
  There is no final-test command in M1. Full protection from agent edits is M2's
  responsibility; folder names alone are not enforcement.
- **Evaluation:** settle primary metric/direction, aggregation, class inclusion,
  ignored/absent labels, thresholds and checkpoint selection before scoring.
  Use verified benchmark conventions; ask organizers about unspecified judging
  metrics. Record any difference between benchmark and submission requirements.
  Never silently invent a metric or compare validation with published test scores.
- **References:** train on official training data and evaluate full validation.
  Freeze a justified starting recipe per task before its reference run; record any
  necessary correction as a new run with a reason. Subset smoke/calibration scores
  are not reference scores. Re-evaluate saved checkpoints with a documented
  tolerance; repeated training is optional and any seed variability remains explicit.
- **Runtime:** verify the exact Bedrock model and region specified in the shared
  plan; a failure requires clarification, not a silent substitute. No separate
  Anthropic key is assumed. Keep temporary access links and credentials private.
- **Storage:** begin with a verified persistent filesystem. S3 is optional and
  requires verified permissions; no bucket creation is assumed. Ignored local data
  and artifacts are not backups. Retain durable logs/checkpoints and safe references.

### Budget gate

The [versioned caps](../../configs/m1.json) now define the M1 allocation and
per-run/resource/retry limits, based on [bounded calibration](../setup.md#capacity-calibration-and-m1-budgets).
Exact organizer quotas remain unknown. The [manual foundation](../training.md) now implements and tests enforcement
before reference runs; no settings file by itself enforces a budget.

| Required setting | How to settle it |
| --- | --- |
| Per-run wall time and epoch/step ceiling | Short train/validation throughput and memory measurements; stop at the first applicable cap. |
| Total M1 GPU allocation and job concurrency | Confirm remaining hackathon capacity/deadline; reserve time for M2-M5 and record a shared allocation. |
| Memory/batch and storage limits | Measure GPU memory and dataset/checkpoint sizes; leave an explicit disk reserve. |
| Retry allowance | Cap retries and record failures; do not loop on permissions, OOM or downloads indefinitely. |
| Strands smoke-test calls, output size and timeout | Confirm Bedrock quotas and set explicit caps; no experimental training loop in M1. |

If all four references cannot fit, reduce recipe cost within the same evaluation
contract and record the change. If required outcomes still cannot fit, surface the
tradeoff for agreement; do not quietly drop tasks, use test data, or declare M1 done.

### Questions to resolve during M1

Access verification is complete with the user's operational clarifications.
The [setup operating agreement](../setup.md#operating-agreements-and-follow-ups)
owns the confirmed submission deadline, instruction to preserve the active session,
and outstanding quota/judging/presentation details. Tasks 1.2/1.3 own data and
metric/budget decisions. Unknown quotas require conservative caps in task 1.3;
new judging requirements will be reconciled when the user receives them.

Completion decision, 2026-10-31: the user accepted the recorded unknown quotas and
pending event requirements as follow-ups, supplied session-renewal/deadline details,
and approved publication and closure of task 1.1. No claim of expiry/restart testing
is made. Later tasks retain their original acceptance requirements.

Planning decision, 2026-10-31: follow the agreed manual-first hybrid approach and
defer numeric budgets and recipe choices to observed capacity. This elaborates the
project plan without replacing a previous decision or broadening M1's outcome.

Tracking update, 2026-10-31: at the user's request, tasks use titles 1.1–1.7
with stable GitHub link destinations. Milestone documents hold acceptance outcomes; redundant overview
issues were retired as not planned, then deleted with explicit user approval. This supersedes the earlier overview-issue
convention, with no change to M1 scope or completion requirements.

Evaluation/budget decision, 2026-10-31 (1.3): use sourced overall accuracy and
global macro IoU, with no ignored ID in the primary metric. Chesapeake keeps all
seven stored classes; a target-0-excluded land metric is supplementary. Freeze
absent-class/checkpoint rules and numeric caps from the measured probe before
references. Organizer judging rules remain an explicit follow-up; version and
re-evaluate validation records if they differ. See [contracts](../data.md).

Storage decision, 2026-10-31: the user approved Git-based source sharing, SageMaker
working data/artifacts, and independent local recovery copies. Follow the shared
[storage guide](../storage.md); verified backup locations/status belong in the
[resource index](../RESOURCES.md#recovery-verification). This does not advance task
1.3 or change test isolation.

Classification reference decision, 2026-10-31 (1.5): freeze modest random-initialized,
all-channel ResNet18 recipes before either run; no imported weights or tuning search.
Both full-validation checkpoint revalidations passed exactly. Brick-Kiln stopped
at the agreed wall reserve; complete validation makes its selected checkpoint
eligible. See [recipes/results](../references.md) and [independent backups](../RESOURCES.md#recovery-verification).

## Documentation and deliverables

Follow the [repository workflow](../WORKFLOW.md): create these implementation files
only as their contents become verified. This milestone links to lasting facts
rather than keeping second copies.

| Home | Contents produced by M1 |
| --- | --- |
| `docs/setup.md` | Verified SageMaker setup, pinned working dependencies, smoke/run commands, observed capacity and persistence checks. |
| `docs/data.md` | Versioned task/input/output contracts, official split handling, channels/labels, preprocessing and evaluation definitions. |
| `docs/RESOURCES.md` | Safe access routes and verified durable dataset/run/checkpoint locations; links to evidence. |
| `src/gotrain/`, `configs/`, `scripts/`, `tests/` | Minimal shared manual workflow, non-secret recipes/caps and meaningful checks. Exact module names chosen during implementation. |
| Persistent `artifacts/runs/<run-id>/` or verified external equivalent | Exact run settings, code/data versions, seed, metrics, runtime/resources, failures, logs and checkpoints per workflow conventions. |
| This document and linked GitHub issues | Decisions, completion evidence, limitations and next action. Small sanitized summaries may be committed; large records stay outside Git. |

When implementation changes setup or contracts, update that shared document in
the same change. Record material changes and invalidated evidence here, retaining
old run records. Update resource verification states only after checks pass. Update
README/project status when capabilities change; do not copy full results there.

## Verification and evidence

Access evidence is in the [setup record](../setup.md); reference evidence is linked below. Keep this table tied to authoritative records; issue closure does not substitute for verification. A run record owns each exact numeric score.

| Required outcome | Check and environment | Result | Evidence |
| --- | --- | --- | --- |
| Required access (1.1) | SageMaker GPU, exact Bedrock/Strands, storage and Git checks | Complete 2026-10-31; recorded limitations accepted | [2026-10-31 setup evidence](../setup.md) |
| Data inspection/contracts (1.2) | Four SHA-256-verified archives; full train/valid labels, 64 pixel samples per split, eight segmentation previews; split/file guards | Complete 2026-10-31; channel corrections and Chesapeake no-data question recorded; no test payload access | [Data contracts](../data.md), [inspection JSON](../data-inspection.json) |
| Evaluation and budget contracts (1.3) | Versioned official metric sources; four-task bounded T4 calibration, no test access | Complete 2026-10-31; frozen primary/diagnostic rules and explicit caps; judging metrics still pending | [Data/evaluation contracts](../data.md), [capacity](../setup.md#capacity-calibration-and-m1-budgets), [task settings](../../configs/tasks.json), [caps](../../configs/m1.json) |
| Shared foundation (1.4) | 12 focused SageMaker checks; two bounded smoke jobs and fresh-process checkpoint reloads | Complete 2026-10-31; two optimizer updates per task, reload score delta 0; no reference results | [Manual guide](../training.md), [raw evidence](../foundation.json), [dependencies](../../requirements.txt) |
| EuroSAT reference (1.5) | Full validation and saved-checkpoint revalidation on SageMaker | Complete 2026-10-31; 87.00% accuracy on 1,000 images; revalidation delta 0; selected model backed up | [Recipes/results](../references.md), [raw evidence](../classification.json), [recovery receipts](../RESOURCES.md#recovery-verification) |
| Brick-Kiln reference (1.5) | Full validation and saved-checkpoint revalidation on SageMaker | Complete 2026-10-31; 97.80% accuracy on 999 images; planned cap stop; revalidation delta 0; selected model backed up | [Recipes/results](../references.md), [raw evidence](../classification.json), [recovery receipts](../RESOURCES.md#recovery-verification) |
| PV4GER-Seg reference (1.6) | Full validation and saved-checkpoint revalidation on SageMaker | Complete 2026-10-31; macro IoU 0.901692; full validation, delta 0; selected model independently backed up | [Recipes/results](../references.md), [raw evidence](../segmentation.json), [recovery receipts](../RESOURCES.md#recovery-verification) |
| Chesapeake reference (1.6) | Full validation and saved-checkpoint revalidation on SageMaker | Complete 2026-10-31; macro IoU 0.405280; full validation, delta 0; selected model independently backed up | [Recipes/results](../references.md), [raw evidence](../segmentation.json), [recovery receipts](../RESOURCES.md#recovery-verification) |
| Reproducible handoff (1.7) | Fresh-process safety/setup and all four retained checkpoint revalidations on SageMaker | Complete 2026-10-31; 12 checks + 5 edge cases; four full-validation deltas 0; settled budgets | [Handoff evidence](../handoff.json), [reference guide](../references.md) |

## Handoff

**Last updated:** 2026-10-31.
**Current state:** M1 and tasks 1.1–1.7 complete. Required access, the four selected datasets/contracts, manual runner/resource enforcement and four accepted reference checkpoints have linked evidence above. All four selected model/optimizer files have independent checksum-verified recovery copies on the custodian Mac; source is in GitHub/local Git. The active JupyterLab session remains open.
**Constraints/limitations:** preserve official splits and sealed test payloads. Exact organizer quotas and judging/presentation details remain unknown; the deadline is 2026-11-01 at 15:00 Asia/Beirut with the agreed submission reserve. GoTrain-only GitHub access expires 2026-11-01. The tested venv inherits 17 dependency conflicts; the verified direct versions are not a universal environment lock. Restart/expiry persistence, S3 permissions and another shared backup destination remain unverified. Single-seed references establish starting points, not retraining stability. See [setup](../setup.md), [data contracts](../data.md) and [recovery coverage](../RESOURCES.md#recovery-verification).
**Next action:** plan M2 using the accepted checkpoints, canonical manual runner and frozen data/evaluation contracts. Version new experiment budgets while preserving historical usage; protect evaluation/records before allowing agent edits. Reuse the verified Strands/Bedrock model/region and pin the runtime dependencies when adding tools. No M2 engine or detailed future milestone plan is included here.
**Synchronization:** documentation, numbered GitHub task closures and M1 completion are published together; local/GitHub/SageMaker source is aligned at the completion commit.

## Completion

All broad M1 outcomes have evidence in the table above. The four starting runs are:

- `m-eurosat`: `20261031T142814768185Z-m-eurosat-manual`.
- `m-brick-kiln`: `20261031T143113863281Z-m-brick-kiln-manual`.
- `m-pv4ger-seg`: `20261031T144800853991Z-m-pv4ger-seg-manual`.
- `m-chesapeake`: `20261031T145719482888Z-m-chesapeake-manual`.

Exact recipes, scores, source/data/checkpoint hashes and fresh-process checks are linked in [reference results](../references.md) and [handoff evidence](../handoff.json). No final-test invocation, autonomous improvement cycle or UI was added.
