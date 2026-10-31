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
