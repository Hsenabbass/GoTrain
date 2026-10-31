# Manual training foundation

Task [1.4](https://github.com/Hsenabbass/GoTrain/issues/9). This is a small manual
PyTorch runner. Reference recipes/results belong to 1.5/1.6; orchestration and
strong protection against agent edits belong to M2. No final-test command, UI,
external tracker, cloud provisioning or automatic pretrained-weight download exists.

## Verified commands

Use the existing [SageMaker verification environment](setup.md#verification-environment),
from `/home/sagemaker-user/GoTrain`. This is the single execution checkout;
other clones are for editing. The entry point rejects other checkout paths so
teammates cannot accidentally create independent locks/budgets:

```bash
PY=/home/sagemaker-user/gotrain-access-check/venv/bin/python
$PY -m unittest discover -s tests -v
$PY scripts/train.py train --recipe configs/smoke-classification.json \
  --data-root data/geo-bench/datasets
$PY scripts/train.py train --recipe configs/smoke-segmentation.json \
  --data-root data/geo-bench/datasets
# For a saved run, re-evaluate its selected checkpoint in another process:
$PY scripts/train.py verify --run-id <run-id> --data-root data/geo-bench/datasets
```

Both committed smoke recipes train two minibatches and validate small official
train/valid subsets. They use random initialization, training-only fitted channel
standardization and paired flip/90-degree rotations; they are **not reference
recipes or scores**. Smoke runs automatically reload the checkpoint in a fresh
process and reproduce validation/prediction before returning success. Their
`budget_exhausted` status is expected when the deliberately small step cap is hit.

[requirements.txt](../requirements.txt) records the exact direct versions tested
on the provided Python 3.12/CUDA image. All checks and ML execution ran on SageMaker;
no packages were installed for 1.4. Use the existing overlay venv rather than
reinstalling the provided GPU stack. The inherited 17 dependency conflicts remain
an explicitly recorded limitation; this is not a universal clean environment lock.

## Small shared modules

- [data.py](../src/gotrain/data.py): reject test/all before metadata/sample access,
  verify partition hash/count, keep all channels in storage order, validate/scale
  tensors, pair spatial transforms and fit optional normalization on train only.
- [metrics.py](../src/gotrain/metrics.py): independent global confusion matrices,
  including the frozen absent-class and Chesapeake diagnostic rules.
- [models.py](../src/gotrain/models.py): the two calibrated ResNet18/FCN-ResNet50
  families with compatible input/output channels and no implicit downloads.
- [runtime.py](../src/gotrain/runtime.py): single-job lock, shared ledger, admission
  caps, deadline reserve, disk/storage/GPU guards and explicit retry allowance.
- [training.py](../src/gotrain/training.py): bounded training/validation,
  atomic checkpoints, structured failures and fresh-process verification.
  [scripts/train.py](../scripts/train.py) is only the entry point.

## Recipe and run record

A recipe names a registered task/model, description, epochs, minibatch-step limit,
wall seconds, batch size, learning rate, weight decay, augmentation and
`normalization` (`fixed` or `train_standardize`). Seed 2026 and evaluator settings
come from the frozen [task contract](../configs/tasks.json). Only `smoke: true`
permits `train_limit`/`valid_limit`; reference jobs traverse full official splits.
The [M1 caps](../configs/m1.json) remain authoritative and cannot be widened by a
recipe. The [1.5 classification recipes/results](references.md) are frozen and verified with random initialization; the [1.6 segmentation recipes](references.md#frozen-segmentation-recipes-16) are also frozen and verified. These reference recipes are separate from smoke configurations.

Each unique UTC/task run has `artifacts/runs/<run-id>/` containing:

| File | Meaning |
| --- | --- |
| `record.json` | Recipe, seed, code commit/dirty flag, dataset revision and partition/contract hashes, dependency versions, status/errors, steps and successful optimizer updates, normalization, global validation counts/scores, memory and checkpoint checksum. |
| `source.patch` | Tracked dirty source patch when needed; untracked source must be committed before a run. |
| `run.log`, `timing.json` | Persistent worker output/failures and charged elapsed wall time. |
| `last.pt`, optional `best.pt` | Atomic model/optimizer state and preprocessing/evaluation metadata; at most two checkpoints. Failed writes preserve the preceding checkpoint. |
| `reload.json` | Smoke checkpoint verification, prediction shape/hash, probability-sum check and score delta. |
| `revalidation-*.json`, `verify-timing-*.json`, `verify.log` | Separate manual verification results and budget charges. |

Minibatch steps include AMP-skipped attempts; successful optimizer updates and
skips are recorded separately. Validation is never augmented or used for fitted
statistics. A complete validation pass selects the strictly greater primary score;
ties keep the earlier best. Subset smoke scores cannot produce an eligible
reference. `is_reference` remains false until a later task deliberately accepts a
frozen recipe and its complete-validation/reload evidence; the runner does not
silently declare a baseline. Checkpoint verification checks predicted class/mask and probability shapes on a
permitted sample; full probability maps are not persisted by default.

## Budget and failure behavior

The parent reserves wall time before starting the GPU worker, holds a single-job
lock and runs a hard process-group watchdog. Worker checks leave the agreed
validation/saving reserve and stop at epoch/step/time/resource ceilings. Storage
headroom is checked before checkpoint writes. Final elapsed time refunds unused
reservation; failed jobs also consume time. The durable `artifacts/m1-budget.json`
starts with the 1.3 calibration charge and the explicit earlier-access accounting
allowance. It enforces shared/category caps and the submission buffer.

One explicitly linked retry (`--retry-of <failed-run-id>`) is allowed for recorded
transient/OOM failures within the failure allocation. An OOM retry must halve the
batch and use a new run ID. There are no automatic retry loops. Fatal data,
permission, non-finite and contract errors require diagnosis. An unsettled ledger
reservation blocks new work until the previous job is inspected; no broad restart
or adversarial sandbox guarantee is claimed.

## Evidence and backup

[M1 evidence: foundation](m1-evidence.json) records the SageMaker checks and both smoke
reloads. Exact run directories are in that report; full logs and smoke checkpoints
remain there on SageMaker. Their metrics are explicitly subset diagnostics.
Follow [storage/recovery](storage.md) for snapshots. For 1.4, the independent backup
includes source, test/run/reload/timing records and a settled-ledger copy, **not the
large reproducible random-initialized smoke weights**. Restore the ledger copy to
`artifacts/m1-budget.json` only after confirming there is no active job. All four accepted reference checkpoints now have verified independent backups; see [receipts](RESOURCES.md#recovery-verification).

## Bounded agent (2.1)

The configuration-only controller in `src/gotrain/agent.py` wraps this runner.
Claude has five typed tools: inspect EuroSAT, train a candidate, read its result,
reload/predict, and select by full-validation score. Preparation, validation and
storage stay inside the runner. There is no shell or code/file-edit tool. The
controller registers its own run IDs and starts with the retained M1 reference;
failed/incomplete candidates cannot replace it, and ties keep the prior best.

`configs/m2.json` owns M2 caps. It inherits M1's resource/run guard structure;
legacy keys containing `m1` describe the same guard fields, with M2 values.
`--allocation m2` selects `artifacts/m2-budget.json`, starting at zero. M1's
ledger remains unchanged. Both use the same existing GPU lock and reject an
unsettled reservation from either ledger. The M2 ledger also caps two normal
training attempts and one eligible retry across invocations; restarting the agent
does not reset GPU usage or these allowances. Each invocation separately bounds
LLM/tool calls and wall time. An interrupted reservation requires operator review.

On the canonical SageMaker checkout, using the existing verification Python:

```python
# In JupyterLab's Python console; no terminal/session dependency after launch.
import subprocess
repo = '/home/sagemaker-user/GoTrain'
py = '/home/sagemaker-user/gotrain-access-check/venv/bin/python'
with open(repo + '/artifacts/agent-launch.log', 'a') as log:
    job = subprocess.Popen([py, 'scripts/agent.py'], cwd=repo,
                           stdin=subprocess.DEVNULL, stdout=log,
                           stderr=subprocess.STDOUT, start_new_session=True)
print(job.pid)
```

This command performs the real cycle and belongs to **2.2**. Inspect
`artifacts/agent/<UTC>/session.json` for run lineage, hypotheses, keep/reject
results, request/tool counts and Bedrock usage metadata; `runner.log` preserves
worker errors. `artifacts/agent/agent.log` retains agent output. The outer watchdog
bounds the invocation; GPU admission reserves enough remaining invocation time
for a bounded job to finish. `agent_returned` means Claude returned, not that M2
acceptance passed. Confirm the full cycle, checkpoint reload and backup before
accepting 2.2. No broad restart guarantee or agent code-edit sandbox is claimed.

The first real cycle passed on 2026-10-31: see [M2 results and limitations](milestones/m2-engine.md#results-and-limitations) and [exact evidence](m2-evidence.json). The two normal M2 training attempts are now consumed; the ledger preserves usage across invocations. Do not relaunch or reset it for more search; a later milestone must version its allocation.

## Reusable model choices (3.1)

`candidate_info(id, spec)` lists one of four supported ImageNet-backbone choices:
`resnet18_imagenet`, `mobilenet_small_imagenet`, `fcn_imagenet`, and
`deeplab_mobile_imagenet`. Classification/segmentation compatibility and explicit
RGB mapping are checked first. These choices do not replace the frozen random
M1 recipes. A shared [task/manifest contract](data.md#reusable-image-tasks-31)
provides the input dimensions, channels and classes.

`build_candidate(id, spec, path, receipt, head_only=False)` loads local tensor
weights with `weights_only=True` and strict backbone matching, replaces the output
head, and copies RGB input weights to the verified positions. Extra channels are
explicitly random and must be fine-tuned; head-only mode is restricted to three
channels. Call `set_training_mode` each epoch to preserve the chosen frozen
batch-normalization policy (and disable frozen-backbone dropout in head-only mode).
Use `candidate_normalization` on scaled inputs. Native grids are retained; this
is an explicit fine-tuning geometry choice, not the default ImageNet crop recipe.

The trusted operator supplies a receipt with exact official weight URL/enum,
full SHA-256, reviewed terms, `target_finetuned: false`, and held-out overlap
`none_known` or `unknown_recorded`. Known overlap is rejected; unknown overlap
is a recorded limitation, not a cleanliness guarantee. Receipts must not be
supplied by LLM text. No downloading, Hub code execution or installation happens
inside a model builder. Bounded retrieval and search are described below.

For the SageMaker CPU acceptance run, all four official backbones were cached in
`artifacts/weights/m3/`; `receipts.json` pins their sources/hashes and the reviewed
research-use context. Downstream redistribution terms need review in M4. No new
packages were installed. Run `python -m unittest discover -s tests -v` in the
verification venv. The real-weight integration test reports a skip if this cache
is absent; the remaining task/guard fixtures need no downloads. Restoring cache
weights must use the recorded official URLs, enforce the plan's download caps,
and verify both filename hash prefix and full receipt SHA-256. The four cached
files total 181,806,878 bytes; carry that transfer usage into 3.2's M3 accounting.

CPU checks establish adapter/model compatibility only. Optimizer/search settings,
GPU throughput, real training gains and task-driven controller wiring are still
3.2/3.3 work; do not run the M2 EuroSAT controller expecting the new search yet.

## Bounded M3 search (3.2)

`python scripts/agent.py --task m-eurosat` selects the task-driven M3 controller;
use another registered benchmark ID for the other tasks. The original command
without `--task` keeps the M2 path. Launch detached through the same `Popen` pattern
above, adding `--task`, and capture a separate launch log. Full searches belong
in 3.3; 3.2 verifies guards and short integration probes only.

Each task has one durable session at `artifacts/agent-m3/<task>/session.json`.
`--task <id> --resume` reopens that session, preserving request/tool counters,
shortlist, trial history, prompt/context hashes and elapsed wall time. It recovers
a recorded completed pending request by a session-scoped unique description instead
of launching it again. The resumed agent receives prior trials/selections and is
told to continue from its recorded stage. A pending request blocks new GPU work;
a fatal trial blocks further training until operator diagnosis. Reviewed recovery
notes are included in trusted context, with counters and elapsed time preserved. Changed contracts/prompts/caps, expired/completed sessions,
active/stale GPU reservations or unresolved pending requests block restart. Inspect
the job/ledger before settling a stale reservation; there is no blind refund or
mid-epoch training resume. Failed retries remain new, charged attempts.

The trusted policy allows inspect → shortlist → probe → screen → tune/final →
select → verify → finish. Probes use training subsets, two optimizer updates,
subset validation and a checkpoint reload; they never qualify for promotion.
Screens/tunes use full validation but are provisional. Only primary-seed 2026
final trials with a 600-second cap can replace a retained reference. Ties retain
the earlier best. Two non-improving tuning proposals stop tuning. Confirmation
uses seed 2027 and the exact retained recipe/reference settings, and cannot become
the exported model. A reported finish is rejected until a completed final trial
has an explicit keep/reject decision and the retained checkpoint verifies.

`configs/m3.json` enforces the 7,200-second allocation: 1,500 per task plus a
1,200-second shared pool for probes, verification, confirmations and eligible
failure retries. Both task and shared pools are inside the global total. All
milestones retain the same GPU lock; any unsettled ledger blocks admission.
At most five new training attempts per task, with a single shared retry allowance;
probe calls are separately bounded by session/candidate checks and shared time.
The legacy `m1_total_gpu_job_wall_seconds` config key names the reused guard field;
its M3 value is 7,200. Historical M1/M2 ledgers are never reset.

M3 recipes add optimizer (SGD/AdamW), constant/cosine schedule, CE/train-weighted
CE/CE+Dice loss, head-only mode, lower backbone LR, explicit phase and seed.
Numeric proposals are seeded and limited to two. Changes inherit allowed settings
from their parent screen/tuning recipe; confirmation cannot silently change them.
The runner saves epoch loss/validation curves and full weight receipts. It builds
and normalizes candidates through the 3.1 APIs and freezes pretrained BN statistics
at each training epoch. Full M3 runs reuse M1’s complete train-only normalization
statistics when task/data/partition hashes and training sample counts match. RGB
pretrained candidates use their reviewed fixed statistics without an unnecessary
training-data scan. Extra-channel probes still fit their bounded training subset.
The run records the reused statistics’ source; preprocessing values are unchanged.
Frozen random reference recipes stay separate; an M3
reference confirmation uses SGD, constant LR and its original epoch/step limits.

A connection that closes before returning any Bedrock event is retried once;
both wire requests count against the existing request cap. Partial responses are
never replayed. Retries and returned token receipts stay in the session.

The fixed system prompt, task/config hashes, compact tool arguments/results and
actual model/token usage are saved with the session. Claude sees candidate IDs,
metrics/curves and remaining budgets, not arbitrary files or code. Text from Hub
metadata is untrusted. Scripted boundary tests verify enforcement; they do not
prove that an LLM can never misinterpret text. The live four-task search is
recorded in [3.3 evidence and handoff](milestones/m3-improvement.md).

Cache loading checks the 3.1 receipts/hashes; missing supported enum weights may
be restored only from their recorded official URL, within 120 seconds and a
500 MiB cumulative M3 byte allowance, including the 181,806,878 bytes already
retrieved in 3.1. Transfers reserve bytes before I/O; failed transfers are charged
conservatively. The optional one-per-session Hub query is metadata-only (10-second
request timeout, 64 KiB response, five proposals). Unknown models remain proposals
for operator review; this version never automatically executes/adopts unknown
Hub architectures or weights. Search uses the four reviewed 3.1 candidates.

The M3 CLI currently accepts registered GEO-Bench tasks with retained references.
The local manifest adapter remains a reusable preparation API; autonomous training
of a new local task needs trusted task/reference registration and runner wiring
before it can be advertised as supported. No model gains, broad import support or
unattended recovery from arbitrary instance loss are established by 3.2 checks.

3.2 verification passed 35 SageMaker checks and both bounded GPU probes with reload
delta 0. See [M3 evidence](m3-evidence.json). M3 usage is already 41.27 seconds
(shared), including 6.25 seconds for two failed base-interpreter launches. Always
launch from the verification venv. These are historical 3.2 costs, not the current
ledger total. Full autonomous comparisons belong to [3.3 evidence](m3-evidence.json).
Smoke checkpoints stay on SageMaker; their reproducible weights are excluded from
the independent source/record/reload/ledger snapshot, following the M1 smoke policy.
