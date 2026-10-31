# Request and dataset service (4.2, partial)

The composer can submit a message and supported manifest ZIP to a loopback-only
FastAPI service. The service validates data, runs bounded Claude/Strands semantic
preflight, and retains the conversation and proposed job summary across refresh.
It does **not** admit GPU training yet. The published 4.2 remains open until the
4.1 package contract, M4 runner/ledger, durable jobs and train-to-package checks pass.

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
Limits: 512 MiB compressed, 2 GiB expanded, 25,000 members, 2 MiB manifest, 120
seconds expansion/validation allowance and a 15 GiB free-space reserve. Full image
decoding runs in a separate process capped at 90 seconds. One import runs at a time;
a second receives a busy response. The real proxy's lower transfer limit, if any,
must be established separately; these are application ceilings.

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
are bounded to 4096 per axis, channels to 64, classes to 256; these are import
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
Replies retain the same conversation, attachment and limits. Up to four wire
requests are charged before invocation, including failed calls, against the same
overall model allowance. Prompt/context hashes and returned usage receipts are
retained. Receipts may be incomplete after interrupted responses; no billing or
token-cost guarantee is made. All structural guards and permitted actions live in
software; the preflight agent has only one decision-submission tool.

Request defaults and ceilings are versioned in `configs/service.json`: 20-minute
runtime (max 40), 15-minute GPU allowance (max 25), five attempts and 24 model
requests. Text may propose lower limits; it cannot increase them. The proposed
workflow needs at least 780 seconds runtime, 660 GPU seconds and six remaining
model calls; smaller requests remain blocked. Actual cost probes and global M4
admission/usage are still pending; a preflight summary does not reserve resources.

States implemented here: draft, checking, needs_input and ready_for_review.
`GET api/conversations/<id>` reconnects without model calls or usage resets.
Identical duplicate request IDs return the same record; different content under
the same ID is rejected. Stale store locks and interrupted checking records block
automatic replay. After confirming no old service/request worker is active, an
operator may call `Requests.reconcile_interrupted_preflights()` to mark interrupted
records needs_input without refunding model calls. Never silently delete a lock
or reset counters. GPU jobs are not implemented or resumed by this service yet.

`POST api/conversations/<id>/start` always returns 409 with the outstanding
packaging/runner prerequisite. The UI leaves Start training disabled. No M1/M2/M3
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
