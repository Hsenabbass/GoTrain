# Request, dataset and durable-job service (4.2)

The composer can submit a message and supported manifest ZIP to a loopback-only
FastAPI service. The service validates data, runs bounded Claude/Strands semantic
preflight, and retains the conversation and proposed job summary across refresh.
It admits only frozen, feasible requests through the shared M4 ledger and lock.
Live classification and segmentation fixtures completed bounded train-to-package
acceptance. Training stays on SageMaker; test data remains sealed.

The visible demo verified late ZIP attachment and refresh/reconnect at d60b46b;
17 SageMaker request checks and six deterministic UI recovery/history checks now
pass, alongside live saved-data/history verification; see the [M4 handoff](milestones/m4-product.md#handoff). The dated step
records below describe earlier configurations, not the current training flag or
verification of the follow-up code. M5 has not started.

## Run

On the canonical SageMaker checkout, reuse the verified environment. Do not upgrade
the supplied ML environment blindly. `requirements-service.txt` records observed
FastAPI/Uvicorn versions; existing Strands/Bedrock and image dependencies come
from the verified M1/M3 environment.

```bash
cd /home/sagemaker-user/GoTrain
/home/sagemaker-user/gotrain-access-check/venv/bin/python scripts/serve.py --port 8766
```

Launch detached through the existing subprocess/log pattern when retaining the
service. Bind remains `127.0.0.1`; use the existing authenticated Studio route
`/jupyterlab/default/proxy/8766/` in the existing browser session. Do not publish
the instance hostname, access URLs, cookies or credentials in Git. No public tunnel,
new AWS resource or separate authentication session is needed.

Assets and API fetches use relative URLs so the proxy prefix is preserved. Set
`GOTRAIN_ORIGIN` to the exact browser origin if the verified proxy rewrites Host.
It is an origin, not an access URL. Mutations require `X-GoTrain-Request: 1`, reject
cross-site fetches and enforce matching Origin; no permissive CORS is configured.
This is a shared authenticated workspace, not a multi-user authorization system.

For non-ML laptop preview only, an isolated environment may install the service
dependencies and run `python scripts/serve.py --local-preview --port 8766`.
Local mode has no model calls and rejects dataset validation; it never substitutes
for SageMaker agent/training checks. The Node-only UI remains a disconnected design
preview. All inference and agent/training execution stays on SageMaker.

## Dataset contract

Upload one ZIP with `manifest.json` at its root and exactly its referenced files.
Browser limits: 32 MiB compressed, 2 GiB expanded, 25,000 members, 2 MiB manifest,
120 seconds expansion/validation allowance and a 15 GiB free-space reserve. Full image
decoding runs in a separate process capped at 90 seconds. One import runs at a time;
a second receives a busy response. Exactly 33,554,432 bytes passed authenticated
proxy upload and full validation; this verifies the application boundary, not the
proxy's unknown maximum.

Only PNG/JPEG/GeoTIFF inputs and lossless PNG/TIFF class-ID masks are supported.
Reject links, special files, traversal, hidden paths, nested archives, executables,
duplicate/case-colliding paths and unreferenced files. Original benchmark archives
are not this format; name the prepared benchmark in the message instead of
uploading its ZIP, which contains sealed test data.

The existing M3 adapter checks every train/valid image and target: dimensions,
channel count, finite pixels, integer class IDs, image/mask alignment and available
GeoTIFF geometry. This validates the explicit contract, not annotation quality or
absence of all possible geographic/content leakage. There is no automatic split,
tiling, reprojection, label repair or guessed spectral order.

Example manifest:

```json
{
  "task": {
    "kind": "classification", "classes": 2,
    "class_names": ["background", "solar_panel"],
    "channels": 3, "height": 64, "width": 64,
    "band_names": ["R", "G", "B"], "rgb_indices": [0, 1, 2],
    "input_divisors": [255, 255, 255],
    "primary_metric": "accuracy", "ignore_index": null
  },
  "splits": {
    "train": [{"image": "train/image.png", "label": 1}],
    "valid": [{"image": "valid/image.png", "label": 0}]
  }
}
```

Segmentation uses `kind: segmentation`, `primary_metric: macro_iou` and a `mask`
path instead of `label` per row. Class names are explicit in integer-ID order.
The reviewed pretrained catalog requires verified RGB positions. Initial dimensions
are bounded to 4096 per axis, channels to 64, classes to 256 and decoded float32
samples to 128 MiB. Headers are checked before image allocation. These are import
ceilings, not a promise that a GPU training recipe can fit them.

`api/examples/classification.zip` and `api/examples/segmentation.zip` download
schema templates. Add actual images/masks and remove their README before upload;
the templates intentionally do not pretend to be a usable training dataset.

## Request lifecycle and limits

`POST api/conversations` accepts a message, unique `request_<uuidhex>` idempotency
key, optional opaque dataset ID, optional conversation ID and typed limits. Naming
EuroSAT, Brick-Kiln, PV4GER-Seg or Chesapeake lets preflight choose that registered
reference. Other URLs and arbitrary server paths are unsupported.

The agent checks intent against labels/metadata and asks necessary questions.
Replies retain the same conversation, attachment and limits. A draft/needs-input
conversation that has no dataset can bind a validated upload or saved-data ID
on its next reply; an attached dataset cannot be replaced and frozen requests
remain immutable. The late ZIP attachment path passed the visible demo; remaining rejection/idempotency checks are tracked in M4. Up to four wire
requests are charged before invocation, including failed calls, against the same
overall model allowance. Prompt/context hashes and returned usage receipts are
retained. Receipts may be incomplete after interrupted responses; no billing or
token-cost guarantee is made. All structural guards and permitted actions live in
software; the preflight agent has only one decision-submission tool.

Request defaults and ceilings are versioned in `configs/service.json`: 20-minute
runtime (max 40), 15-minute GPU allowance (max 25), five attempts and 24 model
requests. Text may propose lower limits; it cannot increase them. The proposed
workflow needs at least 780 seconds runtime, 660 GPU seconds and six remaining
model calls; smaller requests remain blocked. Global M4 admission/accounting is implemented; a preflight summary itself does
not reserve resources. Earlier live acceptance is recorded in M4 evidence.

States implemented here: draft, checking, needs_input and ready_for_review.
`GET api/conversations/<id>` reconnects without model calls or usage resets.
Identical duplicate request IDs return the same record; different content under
the same ID is rejected. Stale store locks and interrupted checking records block
automatic replay. After confirming no old service/request worker is active, an
operator may call `Requests.reconcile_interrupted_preflights()` to mark interrupted
records needs_input without refunding model calls. Never silently delete a lock
or reset counters. Interrupted GPU jobs are never relaunched automatically; see the step 3 contract below.

`POST api/conversations/<id>/start` returns 409 while the training flag is false.
The implemented launch protocol is described under step 3 below. The UI enables Start training only when service health permits it. No M1/M2/M3
ledger/config or completed session is modified, and no test samples are accessed.

## Durable state and verification

State is stored under ignored `artifacts/service/`: validated datasets, streamed
temporary uploads, atomic conversation JSON and an idempotency index. Only opaque
IDs leave the API; no client filesystem path is accepted. Drafts and task metadata
may contain private user data: do not commit raw state, logs or access links.

```bash
python -m unittest discover -s tests -p test_requests.py -v
```

Fourteen non-ML boundary/API checks run independently with explicit semantic and
image-decoder doubles. A separate SageMaker-only check uses real classification
and segmentation PNGs through the existing full-sample adapter and rejects actual
shape mismatches. These checks do not establish train-to-package acceptance.
Record live proxy, upload/download, model-preflight and recovery evidence in the
M4 handoff before claiming them verified. Apply the existing independent backup
procedure to valuable retained evidence; staging on SageMaker is not a backup.

## Verified request slice, 2026-11-01

At source 25ce624, 15 SageMaker CPU checks passed in 1.705 seconds. The existing
Opera session loaded the relative UI/assets through the authenticated proxy; a
1,695-byte synthetic classification ZIP uploaded/validated and a 626-byte format
template downloaded. This establishes small transfers, not the proxy's maximum.
The proxy rewrites the backend origin: set GOTRAIN_ORIGIN privately to the exact
address-bar origin (scheme + host, no path/token). No wildcard or origin bypass.

A real EuroSAT request produced a 20-minute runtime/15-minute GPU proposal in two
model calls. Conflicting building-segmentation intent on red/blue classification
labels produced specific clarification; a meaningful reply resolved the same
dataset/conversation with four total calls. Refresh and an idle service restart
retained the records/counters. The initial free-form decision rejection remains
accounted; the final tool uses explicit typed fields. All 10 verification wire
requests and returned token receipts are in the [sanitized evidence](m4-evidence.json).

No GPU job, inference package or test access occurred. Full 4.2 is still open.
Source/evidence have a verified independent 71-file recovery snapshot; this is not
a claim of full live-service state or uploaded-dataset recovery. SageMaker's Git
credential expired; source reached it through checksum-verified Git bundles in the
existing JupyterLab session. No new credentials or cloud packages were created.


## Shared package handoff (4.1)

The [CPU package/prediction contract](prediction.md) is implemented and verified
for the four retained models. No prediction/download HTTP endpoint is added here;
that UI integration belongs to 4.3. The remaining 4.2 runner can call the operator
export interface after selecting an eligible fully validated checkpoint. Training
admission remains disabled until durable-job/ledger integration and acceptance pass.


## 4.2 step 1: admission/accounting foundation

Verified on SageMaker CPU at e96e01b: 67 tests passed (11 new admission
checks), using isolated fixture ledgers and no real M4 reservation. Independent
snapshot/member verification and evidence restoration passed. No worker launches or enabled Start
action in this step. `configs/service.json` retains `training_enabled: false`.
`configs/m4.json` owns the separate 3,600-second M4 GPU-job pool, inherited
submission deadline/buffer, 600-second maximum trial and 15 GiB disk reserve.
M1–M3 configs and ledgers remain frozen.

`gotrain.admission.Admission` is a trusted supervisor API, not a browser path or
usage-counter interface. Its Linux lease holds the existing shared `m1.lock` for
the entire job. Admission freezes the resolved request/data/version/limits and
preflight usage in one atomic `artifacts/m4-budget.json` transaction. Ready-state,
data identity, current remaining shared allowance, runtime, model-call headroom,
disk and submission reserves are checked before reservation. Effective GPU time
may be below the requested ceiling if the pool has less remaining; infeasible
requests are rejected. Duplicate keys/conversations return the existing job ID
in a conflict, never a new reservation.

Trial and model-call reservations persist before work. Optional trials preserve
a final training attempt, 600 GPU seconds for final training, 60 for verification
and runtime for packaging. Verification consumes GPU-job time but not a training
attempt. Normal trial settlement uses measured monotonic elapsed time; interrupted
work keeps its reservation, and overruns retain the actual charge and fail closed.
The supervisor must ensure child termination before settlement; watchdog and worker
integration belong to the next steps. Closing an unsettled lease never refunds it.
M1–M3 admission also checks unsettled M4 reservations, so an orphan blocks legacy
work even after the OS lock is released. Changed policy requires an operator audit,
not an automatic allowance reset.

The later M4 runner must use this supervisor-owned lease/accounting instead of
opening a second legacy Budget reservation. Durable worker identity, reconnect,
stop behavior, real model-call wiring and live GPU verification are not implemented
by these primitives. No GPU work is authorized by a test fixture enabling admission
in an isolated temporary directory.


## 4.2 step 2: shared worker routing

Source 9397fa4 passed 75 SageMaker CPU checks (eight new M4 runner cases) in
3.472 s. Independent snapshot verification/restored evidence passed. No GPU
execution: the actual training path remains for live acceptance. `M4Runner`
resolves only registered frozen
data, builds reviewed M3-compatible numerical recipes, and launches the existing
training worker through its watchdog using the supervisor-owned M4 reservation.
The worker checks parent/trial/job identity, frozen-request hash, dataset contract
and policy before data/GPU use. No second legacy budget is opened. Training stays
disabled in the live configuration; no new HTTP endpoints or UI are added.

Custom data uses ManifestData for train/valid only; benchmark data uses the
existing official adapter. Normalization and optional class weights use training
only. Custom checkpoints bind the manifest hash and accepted archive version;
benchmark checkpoints retain the original contract/revision. A custom dataset
has no borrowed reference. Only eligible primary-seed final/full-validation
checkpoints can establish or improve its best; ties preserve the prior best and
cross-dataset/metric comparisons are rejected. Benchmarks start from selected M3
models without reopening their completed sessions.

The existing training loop, evaluator, checkpoint writer, resource guards and
reviewed initialization-weight receipts are reused. No new downloads or models.
The wrapper exposes the frozen goal and limits as agent context; actual agent
invocation, durable selection/progress/reconnect and stop wiring belong to step 3.
Package export integration and real GPU acceptance remain later steps.


## 4.2 step 3: detached supervisor and reconnect

Runtime ed46b8c passed all 89 SageMaker CPU checks in 4.139 s. The 14 supervisor
checks passed again in 1.245 s at dd3d152 after test-pipe cleanup; real agent tool
schemas constructed without inference. Independent recovery/restoration passed.
The idle service was updated to dd3d152 on the same loopback/proxy route; saved
conversation bytes were unchanged and Start rejected without a real reservation.
Process recovery/stop used CPU fixtures, not live GPU/Bedrock execution.
Training remains disabled until
package integration and live acceptance. Start takes a persistent `request_id` at
`POST /api/conversations/{id}/start`; read state at `GET .../{id}/job` and request
stop at `POST .../{id}/stop`. Same-origin/header checks apply to mutations; IDs are
opaque. The existing composer gets inline polling/stop only, no new view.

One immutable launch intent is written before spawning `python -m gotrain.jobs`.
One exclusive owner claim prevents duplicate supervisors, even if launch or HTTP
responses are interrupted. The detached supervisor owns the existing M4 lease and
shared lock. Reconnect never starts work. PID/start ticks/boot identity distinguish
live owners from reused PIDs. Missing/dead/uncertain owners require operator audit;
reservations are never guessed, reset or automatically retried. A terminal UI
state cannot hide an active ledger reservation.

The existing Strands/Bedrock agent factory wraps only M4's bounded inspection,
trial, result, selection and finish tools. Frozen goal/data/limits reach the agent
as context. Wire calls charge the M4 ledger before use, including connection retry;
returned usage receipts remain partial. Tool/model/runtime caps and fatal-worker
stops apply. Committed source must match launch provenance before new training.

Stop writes a durable flag. It prevents the next tool/model/trial launch while
the current bounded worker saves/validates and settles; the best eligible final
checkpoint is retained without another model call. Selection is persisted, not
M5 finalization. Status `selected` explicitly does not mean a package is ready.
Standalone verification/export is step 4.

A supervisor process timer enforces the job runtime; M4 workers set Linux parent-
death SIGKILL before GPU use. A hard supervisor death therefore kills its child
and leaves charges reserved for audit. The existing watchdog also kills/waits
for workers on timeout or interrupted waiting. Supervisor state, trials, returned
usage and selection live under `artifacts/service/jobs/<conversation>/`; the GPU
ledger remains the authoritative charge record. No database or queue.


## M4 delivery/workspace

The user authorized all remaining M4 work. Selection now enters trusted CPU
verification/export before Ready. Published versions reuse the 4.1 package
contract; extracted output is compared against the originating checkpoint in a
fresh process outside the checkout with network/cache access denied. Failure
preserves selection/history and never publishes a ready package.

The model registry contains only checksum-verified publications and the four
retained 4.1 receipts. Download and prediction accept version IDs, never client
paths. Read-only history exposes linked experiments, validation, settings and
decisions. CPU image prediction has a 32 MiB upload / 128 MiB decoded sample /
60-second worker limit, explicit band/unit declaration and native-shape checks.
Classification returns uncalibrated probabilities; segmentation returns masks,
aligned overlays/legend and geographic metadata where supplied. Every model has
a validation-only example, without test access. One image operation runs at a time.

Browser dataset import is deliberately capped at a verified operational 32 MiB,
superseding the initial proposed 512 MiB ceiling. Larger prepared ZIPs already on SageMaker can use the operator-only
`python scripts/register_dataset.py data/imports/<prepared>.zip` route (2 GiB
compressed/expanded ceiling), which reuses the same import validation and protected
registry. No cloud URL/path instruction from chat is executed.

The UI keeps saved data, existing models, prediction and verified downloads in the
conversation, with a simple sidebar for saved chats. There is no dashboard. Models remain private research artifacts;
public weight redistribution permission is unresolved. The live gates passed with
62.74250063000363 total GPU-job seconds across the accepted M4 runs.
