# SageMaker access and setup

## Verification record: 2026-10-31

Task [1.1: Verify SageMaker, Bedrock, storage and development access](https://github.com/Hsenabbass/GoTrain/issues/6) is **complete** as of 2026-10-31.
Publication of this sanitized record and task closure were explicitly approved by
the user. Remaining unknowns below are carried into the relevant later tasks.
Checks ran through the existing authenticated Safari JupyterLab session and its
Python 3 console. A separate browser session could not authenticate from the
bookmarked URL alone. Reuse an authenticated session or obtain a fresh organizer
link privately; never commit access URLs or credentials.

| Check | Observed result |
| --- | --- |
| GPU | Tesla T4, 15360 MiB VRAM; NVIDIA driver 595.91.07. |
| Python | 3.12.15. |
| PyTorch / CUDA | torch 2.8.0, CUDA 12.9; CUDA available; an 8×8 ones matrix multiplication returned sum 512.0. |
| Vision library | torchvision 0.24.0 imports passed at access check; relevant training/operator paths subsequently passed the foundation checks and [four reference runs](references.md). |
| Agent SDK | strands-agents 0.3.0; boto3 1.43.106. These are observed versions, not a complete project dependency lock. |
| Memory | MemTotal 16164852 kB; available memory varies. |
| Working volume | `/home/sagemaker-user`: about 99.9 GiB total, 99.2 GiB free at initial check. |
| Git | 2.43.0. |
| GEO-Bench | Installed geobench 1.1.0 in a separate verification venv with inherited system packages. Imports passed with rasterio 1.4.3, NumPy 1.26.4, torch 2.8.0 and torchvision 0.24.0. No dataset samples downloaded during 1.1; [1.2 subsequently completed selected-task inspection](data.md). |
| Bedrock response | Required model `eu.anthropic.claude-sonnet-5-5`, region `eu-central-1`, through Strands returned `GOTRAIN_ACCESS_OK`. No new key configured. |
| Tool execution | A fixed-marker `access_probe` tool returned `GOTRAIN_TOOL_OK`: two model calls, one tool call. |
| Weight endpoint | The installed torchvision ResNet18 default weight URL returned HTTP 206 and 1024 sampled bytes. Only endpoint access was checked; [M1 references](references.md) use random initialization and imported no weight files. |
| Storage / browser reload | Marker file and existing kernel state survived a page reload. Detached 60-second heartbeat started at 11:39:12 UTC and read `20` after reconnect at 11:39:32 UTC, demonstrating progress across browser reconnection. This does not verify instance restart or session expiry. |
| Dataset metadata access | The installed package points to `recursix/geo-bench-1.0` on Hugging Face; metadata retrieval passed, reporting public/ungated access and `cc-by-sa-4.0`. Actual selected-task downloads and per-task terms remain for dataset inspection. |
| Dependency health | Provided environment has 17 pre-existing `pip check` conflicts. Verification venv inherits those packages; imports passed, but this is not a clean project dependency lock. No attempt made to repair unrelated preinstalled software. |
| Package licenses | Installed metadata reports GEO-Bench Apache-2.0, Strands Apache-2.0 and torchvision BSD. Weight/data-specific terms require separate verification after selection. |
| Quota lookup | The provided role returned `AccessDeniedException` for Bedrock Service Quotas listing. No permission changes attempted; organizer clarification needed. |
| Heartbeat completion | The bounded detached probe subsequently reached `COMPLETE`. |
| SageMaker GitHub clone/push | Initial unauthenticated clone failed. After explicit user approval of a GoTrain-only token, authenticated clone passed into `/home/sagemaker-user/GoTrain`. Push to `codex/m1-access-check-20261031` passed and its remote ref matched the cloned HEAD. Main was untouched. The branch remains as verification evidence. |

Sanitized machine-readable evidence is on SageMaker at
`/home/sagemaker-user/gotrain-access-check/evidence.json`, alongside `marker.txt`
and `heartbeat.txt`. This directory contains verification artifacts, not datasets
or model results. The local Git repository remains separate from SageMaker.
The initial terminal was blank/unresponsive; the verified alternative is the Python
console, using bounded subprocess calls for shell commands. Terminal repair is not
required to use that alternative.

## Verified check commands

In the SageMaker Python console, use Shift+Enter to execute. These reproduce the
basic inventory and CUDA checks without downloading data:

```python
import sys, shutil, subprocess, importlib.metadata as metadata
print(sys.version)
print(shutil.disk_usage('/home/sagemaker-user'))
print(subprocess.run(
    ['nvidia-smi', '--query-gpu=name,memory.total,driver_version', '--format=csv'],
    capture_output=True, text=True, timeout=10,
).stdout)
for name in ['torch', 'torchvision', 'strands-agents', 'boto3']:
    print(name, metadata.version(name))
import torch, torchvision
x = torch.ones((8, 8), device='cuda')
print(torch.version.cuda, (x @ x).sum().item())
del x
```

The response smoke check used `BedrockModel` with explicit model/region,
`max_tokens=128`, and `botocore.config.Config` with a 5-second connection timeout,
30-second read timeout, and `retries={'total_max_attempts': 1}`. The tool probe also
capped model requests at two, tool execution at one, and wall time at 60 seconds.
These caps cover access checks only, not future training budgets or the M2 engine.

## Verification environment

The separate environment is `/home/sagemaker-user/gotrain-access-check/venv`, created
with `python -m venv --system-site-packages`. Installation previews and constraints
preserved the provided NumPy 1.26.4 and Click 8.2.1 rather than upgrading them.
The installed additions are `geobench==1.1.0`, `affine==2.4.0`, `rasterio==1.4.3`,
`cligj==0.7.2`, and `click-plugins==1.1.1.2`. Use its `bin/python` for these checks.
Logs, constraints, an environment snapshot, base dependency-conflict report and
metadata-access evidence are saved beside `evidence.json`. The snapshot records
the inherited environment; a minimal application lock belongs with implementation.

## Capacity calibration and M1 budgets

Task [1.3](https://github.com/Hsenabbass/GoTrain/issues/8), 2026-10-31: one bounded
four-task probe completed on the provided T4 in **12.98 seconds** (240-second
internal cap, 300-second watchdog). [Raw evidence](calibration.json) records code
hash, environment, memory and sample-load counts; [probe script](../scripts/calibrate.py)
reproduces it. No pretrained weights or Bedrock calls were used, no checkpoint or
reference score was produced, and no test dataset was instantiated.

| Task | Proxy, batch | Train seconds/batch | Valid seconds/batch | Estimated full train epoch / validation (s) | Peak CUDA reserved MiB |
| --- | --- | --- | --- | --- | --- |
| `m-eurosat` | resnet18_random, 32 | 0.131 | 0.156 | 8.23 / 4.98 | 176 |
| `m-brick-kiln` | resnet18_random, 32 | 0.140 | 0.180 | 65.70 / 5.76 | 164 |
| `m-pv4ger-seg` | fcn_resnet50_random, 4 | 0.113 | 0.049 | 84.55 / 4.94 | 1230 |
| `m-chesapeake` | fcn_resnet50_random, 4 | 0.084 | 0.031 | 62.98 / 7.80 | 862 |

The probe used synchronous loading (zero workers), two CPU threads, fixed input
scales, float16 autocast/GradScaler, eight train steps (three warmup) and four valid
steps (one warmup) per task. Finite losses and output shapes passed. Samples cycle
within the first 64 train/valid items, so estimates reflect a small warm-cache
probe and exclude metric/checkpoint overhead; they are not guarantees of full-data
or other-model throughput. No preprocessing statistics were fitted. Free working
volume space was **81.73 GiB**.

[Numeric M1 caps](../configs/m1.json) allocate one GPU job at a time, 3,600 seconds
of total M1 GPU-job wall time and 600 seconds/10 epochs/5,000 train steps per
reference. Validation/saving reserves (30 seconds classification, 60 segmentation)
exceed these measured full-validation estimates by at least fourfold. Memory limits
(10 GiB allocated/12 GiB reserved) and a 15 GiB disk reserve leave substantial
headroom over the measured probes. The defaults fit four reference jobs plus smoke,
revalidation and failure allowance; the [manual foundation](training.md) implements and verifies enforcement.
Actual job durations, including this probe, must be charged; caps are project
allocations, not a claim of verified organizer quotas. Recalibrate changed recipes
within the remaining allocation and stop if complete validation cannot fit.

## Manual foundation verification (1.4)

On 2026-10-31, **12 focused checks passed** on the provided verification venv:
split rejection before I/O, fixed scaling/label checks, paired transforms,
train-only fitted moments, analytical global metrics including ignored/absent
classes, caps/lock/accounting/retry checks, a real watchdog termination and
preservation of an existing checkpoint after a simulated failed write.

Two bounded smoke runs then completed training, subset validation and automatic
fresh-process checkpoint reloads: EuroSAT in **10.15 seconds**, PV4GER-Seg in
**12.35 seconds**, with two successful optimizer updates each. Both reload primary
score deltas were **0**; prediction hashes matched and probability sums passed.
These are smoke diagnostics, not reference scores. [Raw foundation evidence](m1-evidence.json)
owns run IDs, configs, versions, normalization, memory, checksums and settled budget
charges. [Training guide](training.md) owns verified commands/record format.

[requirements.txt](../requirements.txt) records all ten observed direct versions.
No packages were installed or upgraded for 1.4. The provided GPU image and overlay
venv remain in use; inherited conflicts were not repaired. These checks establish
the used ResNet18/FCN-ResNet50 paths, not every installed vision operator or a
universal clean environment. No pretrained weight or Bedrock request was made.

## Recovery

Follow [storage and recovery](storage.md) for independent snapshots, dataset
caches and fresh-environment restoration. Browser expiry/restart persistence is
still unverified; saved scripts and files, rather than console memory, are the
recovery source. Recreate credentials privately; they are excluded from backups.

## Operating agreements and follow-ups

User clarification on 2026-10-31 is the current operational agreement:

- **Submission:** 2026-11-01 at 15:00 Asia/Beirut. Reserve time for final evaluation,
  evidence and submission; this deadline takes precedence over generic event dates.
- **Session:** no specific expiry time is known; the organizers can renew access on
  request. Keep the existing JupyterLab session open, avoid unnecessary reloads and
  never close/restart the application or instance to test expiry. The brief's
  up-to-12-hour description is context, not a verified countdown for this session.
- **Judging metrics and presentation requirements:** not announced yet. The user
  will relay them. Record updates when available; do not invent requirements.
- **Quotas:** exact GPU/runtime and Bedrock limits remain unknown because the role
  cannot read quotas. This is an accepted recorded limitation of access verification.
  Task 1.3 has set [conservative explicit caps](../configs/m1.json); the manual runner now enforces them before reference runs;
  do not treat unknown quotas as unlimited resources.

Technical access acceptance is satisfied. Follow-up work belongs to its planned
scope: task 1.2 has verified selected-task downloads/versions and recorded source terms in [data contracts](data.md);
task 1.3 has frozen [metrics/budgets](data.md#evaluation-and-checkpoint-rules-13); reconcile organizer updates when received; task 1.4 has recorded the [tested direct dependency set](../requirements.txt)
and verified the manual runner. Recipe-specific weight downloads and
licenses are checked when models are selected in tasks 1.5/1.6. Imports and endpoint
access alone do not establish full training compatibility. Task 1.7 reviews all
required evidence; M5 checks the eventual submission/presentation requirements.

GitHub authentication was completed after the user privately confirmed their
password and explicitly approved token creation and private SageMaker use.
The fine-grained token is limited to GoTrain contents read/write and required
metadata read, with no account permissions, expiring 2026-11-01. It was entered
through hidden input and stored outside the repository with owner-only file
permissions (0600, parent directory 0700). No token value belongs in this document,
notebooks, Git remotes or history. The repository-local Git configuration points
to private credential storage and uses the repository path when matching access.
Renewal will require a new authorized credential after expiry; do not widen scope.
Git verification results are recorded in `gotrain-access-check/git-verification.json`.

Update this record, the resource index, milestone evidence and task 1.1 together
if access behavior changes. Task completion covers the observed checks and agreed
operating constraints; it does not claim instance-restart or session-expiry testing.

## M4 request-service verification (2026-11-01)

The existing Opera JupyterLab session, verified venv and loopback Studio proxy were
reused. Observed FastAPI 0.142.4, Uvicorn 0.54.0, Starlette 1.8.0, Pydantic 2.14.1
and HTTPX 0.28.1; no SageMaker dependency changes were made. Request/import and
real preflight checks passed; [service setup](service.md) owns commands and exact
limitations, and [M4 evidence](m4-evidence.json) owns results/independent recovery.
GitHub credential expiry prevented authenticated pulls; checksum-verified source
bundles fast-forwarded main without creating or modifying credentials. The request
service remains on source 25ce624. No historical GPU ledger or test data changed.


## M4 standalone prediction verification (2026-11-01)

Reused the renewed Opera JupyterLab session and existing Python 3.12 venv.
No dependency installs or GPU jobs. Four extracted packages passed CPU float32
comparison/CLI checks outside the checkout with network/cache/checkout reads
denied. [Prediction contract](prediction.md) owns commands; [M4 evidence](m4-evidence.json)
owns measurements and independent recovery receipt. Request-service process
remains on its earlier verified source; the canonical checkout includes the
package implementation.


## M4 supervisor service update (2026-11-01)

The idle loopback service was restarted at source dd3d152 using its existing private
origin environment and proxy route. No access/dependency changes. Health retained
training disabled, a saved conversation was byte-identical, the new job route was
present, and Start returned 409 without creating a real M4 reservation.
Supervisor recovery/stop checks used isolated CPU processes; live GPU/agent
acceptance remains pending. [M4 evidence](m4-evidence.json) owns test and recovery receipts.
