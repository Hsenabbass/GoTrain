# M4: Make results usable

**Status:** Core delivery and a six-image visible classification demo passed on SageMaker. Late ZIP attachment and refresh/reconnect are verified at d60b46b; keep 4.2–4.3 open for remaining targeted regressions and the custom segmentation ZIP download checksum. M5 has not started. Packages remain private research artifacts while public redistribution permission is unresolved.
**GitHub:** [M4](https://github.com/Hsenabbass/GoTrain/milestone/4)
**Direction:** [Agreed M4 outcome](../PROJECT_PLAN.md#m4-make-results-usable)

## Outcome and scope

A teammate can attach supported data, describe an image classification or semantic
segmentation task, set limits, follow a real autonomous run, try its selected model
on one compatible image, inspect its history and download a usable model package.
The experience is a minimal conversation workspace, inspired by ChatGPT's
layout and restraint. Packaging, custom-data training integration and durable jobs
are required parts of this milestone, alongside the interface.

Reuse [M3's selected pipelines, evidence and limitations](m3-improvement.md#handoff).
Expose the four existing models immediately without retraining them. Their gains
remain single-seed/provisional; selection on validation is distinct from M5's final
test evaluation. The engine and prediction entry point remain usable without the UI
for later GoPilot integration. Deliver one shared SageMaker workspace, not a public
multi-user service.

### The experience

| Moment | First-version behavior |
| --- | --- |
| Start | One message composer with dataset attachment and Send, plus a simple saved-chat sidebar. No dataset grid, dashboard or extra view navigation. Saved request IDs restore the current draft. |
| Compose | Multiline task instruction, attachment button, compact time-limit control and submit. Attached data appears as a removable filename/dataset chip. Additional limits live in one small options popover. |
| Validate | Import sheet shows task type, sample/split counts, channels and any blocking problem. Check both dataset completeness and instruction clarity/compatibility. Ask only questions needed to resolve the task; never make the user configure an architecture or learning rate. Invalid imports explain the specific fix before training starts. |
| Run | One compact progress block in the conversation: Inspecting → Preparing → Comparing → Refining when used → Verifying → Ready. Show current operation, elapsed time and remaining allowance, with restrained motion. Expand for trials and short evidence-based decisions. Skipped stages are marked honestly; no fabricated percentage or ETA. |
| Use | Completion shows selected model/version, validation metric and three actions: Try model, History, Download. Try model opens an inline single-image tool; no navigation required for the common action. |
| Inspect | History opens a focused detail view with Versions and Experiments. Show parents, hypotheses, settings changed, scores, resource use, failures and keep/reject reasons. Compare only runs with compatible data/metric contracts; label screening and provisional results. Raw records are secondary. |

Preserve the approved neutral visual style, readable text, a system font, fine separators,
consistent spacing and simple icons. One accent is sufficient; status color has
meaning. Avoid ornamental gradients, floating shapes, repeated rounded cards,
gratuitous badges and generic assistant filler. Make keyboard focus, contrast,
attachment errors and reduced-motion behavior work. The composer stays reachable;
the conversation layout collapses cleanly on narrow screens. Review empty, importing, running, failed,
stopped and completed states in the real app, not only the happy-path screenshot.

### Data import: what the attachment button supports

| Route | M4 support and boundaries |
| --- | --- |
| Upload dataset | One ZIP containing `manifest.json` and referenced PNG/JPEG/GeoTIFF images, plus lossless integer masks for segmentation. Reuse the M3 manifest schema; provide downloadable classification and segmentation examples in the import sheet. This is a labeled dataset upload, not an arbitrary ZIP or a lone image to train from. |
| Use existing data | Choose a previously validated import or an operator-registered dataset already on SageMaker. Large datasets can be transferred through JupyterLab and registered under the approved data root, avoiding a browser upload. No arbitrary server path from chat. |
| Prepared benchmarks | Choose EuroSAT, Brick-Kiln, PV4GER-Seg or Chesapeake by name. Reuse verified train/validation data and retained models. These are supported dataset references, not arbitrary Hub URLs. |

For custom training, require explicit nonempty train/validation membership, labels
or aligned class-ID masks, class mapping, fixed image dimensions, channel order and
pixel scaling. Ask for verified RGB positions when using the reviewed pretrained
catalog. Validate compatibility before allocating a job. Do not infer spectral
semantics from channel count or quietly repair labels/splits. Fixed-size, prealigned
examples and no ignored labels remain the initial contract; large rasters must be
pre-windowed. No automatic splitting, reprojection, tiling or unlabeled training.
The import guide should explain these requirements plainly without exposing the
engine's internal record structure in the main conversation.

Use a **32 MiB compressed / 2 GiB expanded / 25,000-file** browser import
ceiling, streaming to disk and preserving the existing free-space reserve. Check
actual expanded bytes, paths and file counts; reject traversal, links, nested
archives and executables. Publish any lower limit imposed by the real proxy after
verification. Existing-data registration is the route for larger prepared inputs;
do not turn upload-limit problems into a cloud storage project.

S3, arbitrary HTTP/Hugging Face links, Drive and other connectors are deferred.
They need verified credentials, download limits and format adapters. Folder-layout
auto-detection is also deferred; a documented manifest ZIP is the first contract.
A separate prediction upload accepts one compatible image without training labels.

### Recognize the task and clarify before training

Read classification/segmentation from the manifest or registered dataset and show
it automatically; no mandatory task-type picker or redundant confirmation. Check
that the actual labels/masks and the user's instruction agree with that declaration.
If the type is absent or ambiguous, keep the import as a draft and ask: "Do you
want one label per image, or to identify regions within each image?" Record the
answer in the validated task contract; do not silently guess or start training.

Preflight checks the **request as well as the files**: is the desired output clear,
does the requested target match the supplied labels, is the task supported, and is
the budget feasible? For example, land-cover labels plus "detect buildings" needs
clarification; an explicit solar-panel segmentation request with compatible masks
does not. Missing labels or channel metadata require a concrete fix, not a guessed
answer. Ask related necessary questions together in the conversation, preserve the
attachment/options, and use the reply to continue the same task. A user reply must
actually resolve the blocker before admission; it cannot be treated as approval
to bypass the data contract. Routine model/optimizer choices remain with the agent.

Use a Claude preflight capped at four model requests to interpret intent and ask
necessary questions; local schema/file checks handle structural errors. Persist
and count these calls against the same conversation's overall request allowance,
including retries. If unresolved at the cap, retain the draft with a clear blocker;
no further model calls or training launch automatically. Show an explicit
"Needs input" state while waiting. Freeze the resolved task, dataset version and
limits before starting the detached job. Training runtime starts at job admission;
the UI must distinguish preflight/waiting time from the running job's allowance.

### Limits, task instructions and stopping

The visible control is **maximum runtime**, default 20 minutes, with an internal
ceiling of 40 minutes. Advanced options lower the GPU-job allowance (default
15 minutes, ceiling 25), training attempts (default/ceiling 5), or model requests
(default/ceiling 24). All are ceilings, not promises to spend the allowance.
Keep architecture, optimizer and other numerical tuning with the agent.

Trusted admission checks the requested runtime against setup/probe, final-training
and validation/saving reserves. Plan fewer candidates for a small budget; reject
an infeasible request with the minimum needed rather than silently exceeding it.
Retain the existing 600-second maximum trial cap, primary seed, reviewed model
catalog, retry/resource guards and deadline buffer. Fix the current hard-coded M3
allocation/session/reference assumptions through reviewed integration; do not reset
or reopen completed M3 sessions to implement user limits.

Task text must actually reach Claude as bounded user intent. The validated dataset,
supported task type, frozen metric and software-enforced limits remain authoritative.
If the request contradicts these, ask for the missing/corrected input before starting.
No general-purpose chat assistant, shell/code-edit tool or unrestricted tool access.

Add **Stop after current experiment**: stop launching new work immediately, let the
current bounded job save/validate and settle its charge, then preserve the prior
best and history. Show the stopping state. Do not claim instant cancellation or
mid-epoch recovery. Runtime/resource watchdogs remain hard upper bounds.

Display elapsed/GPU-job time, attempts and model-call counts. Show returned token
usage only with its known completeness limits. M4 does **not** offer a dollar-budget
guarantee: organizer quotas, pricing/billing visibility and interrupted-call usage
are not fully known. Runtime and request caps are the practical cost controls.

### Prediction, versions and downloads

- **Try model:** upload one image or choose an approved validation example. Enforce
  the package's dimensions, channel order, units and preprocessing; an RGB photo
  cannot stand in for a 13-band input. Classification returns a class and class
  probabilities, without claiming calibration. Segmentation returns an aligned
  mask, a simple overlay/opacity control and a legend. Download class-ID masks;
  retain CRS/transform when the compatible GeoTIFF input supplies them.
- **Versions:** immutable version IDs link to originating runs, checkpoint hashes,
  dataset/contract versions, code/weight provenance and the selection decision.
  Experiments include rejected/failed alternatives; not every trial becomes a
  selected version. Clearly label the current selected version and validation-only
  status. Never silently replace or finalize a model from the browser.
- **Download:** one ZIP, `gotrain-<task>-<version>.zip`, expanding to a clean folder
  with inference weights, architecture/task/preprocessing metadata, class/channel
  mappings, a small prediction entry point, tested dependency requirements, concise
  usage instructions, provenance/terms and checksums. Include a compact experiment
  summary; omit datasets, credentials, optimizer state and unrelated training logs.
  Reconstruct the architecture without cached initialization weights or downloads.
  The package works outside the checkout on the documented compatible environment;
  no claim of universal hardware/runtime compatibility or ONNX support.
- Review redistribution terms before including weights; record attribution and
  remaining restrictions. A blocked redistribution route must be resolved or
  explicitly reported, not hidden behind a working local prediction button.

Useful small additions are saved-data reuse, Stop after current experiment, an
approved example for each retained model, and segmentation overlay/mask download.
They directly shorten the core workflow. A waiting game, extra themes, maps,
leaderboards, notifications and broad cloud imports are outside this first version.

## Work sequence

| Step / issue | Prerequisites | Tools, inputs, outputs | Completion check |
| --- | --- | --- | --- |
| [4.1: Package versioned models and standalone prediction](https://github.com/Hsenabbass/GoTrain/issues/20) | Completed M3 | Retained checkpoints/records + existing PyTorch/Rasterio → shared prediction API/CLI, immutable versions and downloadable ZIPs | All four selected models load and predict in a fresh process outside the checkout, with network and initialization-cache access unavailable. Match checkpoint outputs within declared device-appropriate tolerances; verify labels, shapes, preprocessing, checksums and terms. Reuse M3 full-validation evidence. |
| [4.2: Connect supported imports to durable bounded jobs](https://github.com/Hsenabbass/GoTrain/issues/21) | M3; shared package/prediction contract from 4.1 | Manifest adapter + controller/runner/ledger + thin Python service → validated imports, task recognition/clarification, custom-task registration, user limits, persisted jobs/progress and stop | Non-GEO classification and segmentation imports each complete one bounded live train→validate→select→package path on SageMaker. Focused cases cover declared type, ambiguous intent, instruction/label conflict, missing metadata and infeasible limits: blockers launch no training, replies resolve the same draft, and preflight calls remain charged. Refresh/reconnect and service restart reattach without duplicate work or reset usage. Invalid imports, double-submit and stop preserve records and prior best. |
| [4.3: Deliver and verify the minimal conversation workspace](https://github.com/Hsenabbass/GoTrain/issues/22) | 4.1–4.2 contracts | Real service/data/packages → neutral chat timeline, live stages, inline prediction, history and downloads | Teammate completes import→instruction/limits→run→prediction→history→download through the authenticated SageMaker route. Exercise one clarification→reply→continue interaction with attachment/options preserved and no redundant task picker. Review responsive/error/stopped states, verify download inference, and create/transfer/check independent recovery snapshots. No mock results or test access. |

Each task includes relevant checks and documentation. In 4.2, verify proxy access,
prefix-relative assets/API calls and a bounded upload/download **first**, before
building the full interface. Surface an access blocker early. The 4.3 flow reuses
4.2's live custom-task runs rather than repeating training for a separate demo.

## Decisions and open questions

- **2026-10-31, user direction:** extremely practical, minimal, premium dark UI;
  instructions/import in the composer, configurable limits, real stage progress,
  direct model use, history and clean downloads. First usable version only.
- **2026-10-31, clarified interaction:** recognize the task from declared dataset
  metadata, ask when ambiguous, and validate the instruction as well as the data.
  Necessary follow-up questions continue the same draft before training; no
  obligatory manual task selection. This refines the original metadata-only
  wording in the Validate interaction without expanding supported task types.
- **Proposed implementation:** a small hand-styled HTML/CSS/JavaScript frontend
  served by FastAPI/Uvicorn on SageMaker. Use the existing Python engine and local
  atomic JSON records, one detached job supervisor and one shared GPU lock.
  Poll compact persisted state while a job is active; refresh reconnects by job ID.
  No separate database, task-queue service, frontend build stack or external host.
  Verify/pin only required added packages in the SageMaker environment; no installs
  are part of this planning change.
- Browser closure must not own job lifetime. Service restart reconciles persisted
  jobs with live workers; stale/incomplete reservations block automatic relaunch
  until audited. An instance loss remains a recovery case, not transparent resume.
  Reject a second active training job with a clear busy state; no multi-job queue
  or GPU inference competing with training. Permit history/export while training;
  serialize GPU predictions through the shared lock.
- The backend accepts opaque dataset/job/model IDs and typed operations, not
  client-supplied filesystem paths or shell commands. Keep UI/API behind verified
  authenticated SageMaker access, with same-origin mutation protection. Expose only
  allowlisted app artifacts; do not serve the checkout or bundled benchmark ZIPs.
- **Custom-data gap is required work:** generalize trusted task/reference/budget
  wiring and label diagnostics to the common adapter. Existing benchmarks start
  from retained M3 models. A new dataset has no M1 reference: establish a first
  eligible, fully validated model before claiming improvement; never compare its
  metric to another dataset. Preserve frozen M1–M3 configs, records and ledgers.
- **Proposed M4 execution allocation:** a separate 3,600 GPU-job-wall-second
  ledger covering probes, live custom-data checks, all UI launches, GPU prediction/
  reload and failures. Every new conversation shares this pool; none resets it.
  Keep per-job/resource/deadline guards and the shared lock across allocations.
  This is a new project cap, not leftover M3 time or a cloud entitlement. Reuse
  all four completed benchmark searches. Check actual remaining time/access at
  implementation; preserve the [submission agreement and M5 buffer](../setup.md#operating-agreements-and-follow-ups).
- **Access unknowns:** the actual organizer environment's proxy route, upload
  ceiling and teammate authentication still need verification. Do not create
  AWS resources or a public tunnel as a fallback. Weight terms and compatible
  clean inference dependencies need the 4.1 review. These do not block planning.
- Cut optional providers, visual embellishment and extra settings first if time
  tightens. Do not cut honest limits, usable exports, custom-task wiring or the
  required M5 test/evidence work to claim M4 complete.

Technical references reviewed for this proposal: [AWS's authenticated Studio proxy
example](https://aws.amazon.com/blogs/machine-learning/build-streamlit-apps-in-amazon-sagemaker-studio/)
supports the intended access pattern, not verification of our instance;
[FastAPI proxy support](https://fastapi.tiangolo.com/advanced/behind-a-proxy/) and
[spooled uploads](https://fastapi.tiangolo.com/tutorial/request-files/) support
the small service proposal. Heavy training stays in detached processes rather than
request handlers; see [FastAPI's background-task caveat](https://fastapi.tiangolo.com/tutorial/background-tasks/#caveat).

## Verification and evidence

| Outcome / issue | Check and environment | Result | Evidence |
| --- | --- | --- | --- |
| Plan consistency | Local read-only review of code, M3 evidence/handoff, GitHub M3 tasks and existing M4 issue search; documentation diff/link checks | Planning only; no runtime claim | This document; M3's existing evidence remains authoritative |
| Standalone model use / 4.1 | Four fresh-process CPU package/CLI checks outside checkout, with network/cache denial; independent ZIP restoration | All four passed; zero logit delta; backup verified | [Contract](../prediction.md), [evidence](../m4-evidence.json) |
| Imports and request clarification / 4.2 slice | 15 SageMaker CPU checks; real proxy upload/download, Claude conflict→reply, refresh and service restart | Verified for preflight only; no GPU job | [Evidence](../m4-evidence.json), [service contract](../service.md) |
| Durable GPU jobs and train→package / 4.2 | Recorded live classification/segmentation training, stop and reconnect | Earlier acceptance plus live late-ZIP attachment verified at d60b46b | [Evidence](../m4-evidence.json#final_delivery) |
| Usable workspace / 4.3 | Recorded browser/package acceptance plus current follow-up review | Refresh/reconnect passed; transient-read/cross-chat checks and segmentation ZIP receipt pending | [Evidence](../m4-evidence.json#final_delivery) |
| Follow-up fixes / 4.2–4.3 | Scoped SageMaker demo, 2026-11-01 | 15 request checks and visible classification workflow passed; remaining targeted checks pending | Follow-up section below |

## Handoff

**Last updated:** 2026-11-01 (Asia/Beirut).
**Current state:** earlier core M4 live acceptance and independent recovery are
recorded below and in [M4 evidence](../m4-evidence.json). Follow-up code now allows
an initially missing dataset to be attached to the same unresolved draft, retries
read-only progress requests with backoff, and separates training-start IDs and
attachment state across chats. Attached/frozen datasets and limits remain protected.
**Verification:** the subsequently authorized visible demo deployed d60b46b on
SageMaker. Fifteen existing request checks and the six-image clarification→late ZIP
attachment→training→refresh/reconnect→prediction→history→download path passed.
The synthetic result is integration evidence, not an accuracy benchmark.
**Remaining:** transient progress-read and cross-chat regressions, saved-data late
attachment UI path, and the independent segmentation ZIP checksum receipt.
**Recovery:** the new 89-file snapshot passed cloud and independent receiver
verification: complete SHA-256 and every member matched. Its permanent Mac path
and checksum are recorded in [resources](../RESOURCES.md).
**Next action:** perform the remaining scoped M4 checks when requested. Preserve budgets and test isolation; do not start M5.
**Synchronization:** 4.2–4.3 stay open with the scoped live evidence. Runtime source
is d60b46b; this documentation update records the demo without code changes.

## Completion

Core runtime acceptance is recorded. Final M4 sign-off awaits the deferred checks
and segmentation ZIP receipt above. 4.1 remains complete; 4.2–4.3 remain open.
M5 has not started.

## Implementation history

The following dated implementation notes describe earlier states and are
superseded by the current handoff above; their evidence is preserved.

## 4.2 implementation update

User authorized 4.2 and direct work on main. The latest UI instruction supersedes
the earlier sidebar/dataset-card proposal: retain a single composer and attachment,
with inline necessary questions and a compact review summary. No new dashboard.

The request slice adds bounded manifest ZIP imports, full CPU image validation,
persistent drafts/idempotency, typed Strands preflight, before-call charging and
same-origin FastAPI access. Prompt/context hashes and returned usage are recorded.
Actual browser origin must be set privately in GOTRAIN_ORIGIN because this proxy
rewrites the backend origin. Small upload/download worked; the actual proxy upload
ceiling remains unverified. Training admission stays disabled in software.

Live checks used 10 wire requests (30,816 input and 3,419 output tokens in returned
receipts). An initial unstructured decision was rejected; its two requests remain
charged. Explicit typed fields then passed conflict and reply checks. Historical
ledgers are unchanged; no GPU job, test access or train-to-package result occurred.
A 71-file snapshot at source 25ce624 was independently transferred, archive/member
checksums verified and the evidence JSON restored with a matching hash. It covers
source and verification evidence, not a full live-service/user-dataset restore.


## Remaining 4.2: step 1 handoff

User authorized admission/accounting foundation only before the next detailed
step. Implemented the independent M4 policy/ledger, immutable request admission,
shared-lock exclusion, trial/model-call charging and finalization reserves.
Verification passed on SageMaker CPU at e96e01b: 67 tests, including 11 new
admission checks, in 3.453 s. M1–M3 ledger hashes were unchanged; no real M4
ledger/reservation, GPU job, Bedrock request or test access. The 77-file snapshot
was independently checksum-verified and evidence JSON restored. Training remains
disabled. Next: propose step 2 custom-data runner integration for confirmation. See the [service contract](../service.md).


## Remaining 4.2: step 2 handoff

User authorized focused custom-data runner integration. Added an M4 path to the
existing worker and a small trusted runner wrapper; shared training/evaluation
code is reused. CPU verification passed at 9397fa4: all 75 tests (eight new runner cases),
3.472 s. Real ledger hashes were unchanged, no real M4 reservation was created,
and no GPU/Bedrock/test access occurred. The actual GPU training path remains
unverified until live acceptance. Independent 79-file snapshot/member verification
and evidence restoration passed. No new service or dependency; training stays disabled. Durable agent/supervisor state
and stop/reconnect are step 3, package wiring step 4, live acceptance step 5.


## Remaining 4.2: step 3 handoff

Confirmed by the user; work stays on main. Implemented one detached supervisor,
bounded existing-agent wiring, saved launch/owner/progress/selection, read-only
reconnect and stop-after-current-experiment. Runtime ed46b8c passed 89 SageMaker CPU checks; 14 focused supervisor checks
passed at dd3d152 after test-pipe cleanup. Real detached-process reconnect, stop,
parent-death protection and tool-schema construction passed with CPU fixtures.
An idle service restart preserved the saved conversation and rejected live Start.
Independent 82-file snapshot/member verification and evidence restoration passed.
No live GPU/model calls. UI changes are limited to inline progress/stop, gated by the
still-disabled training flag. Next: confirm step 4 standalone verification/export
integration; live GPU/agent acceptance remains step 5.


## Remaining M4 authorization (2026-11-01)

User authorized all remaining steps and 4.3 without further per-step confirmation.
Work stays on main and reuses the current engine. Delivery, inline use/history/
download and operator import are implemented pending CPU/proxy/live verification.
The browser import operational cap is now 32 MiB pending boundary proof; larger
prepared inputs use the approved operator path. Two explicitly synthetic custom
tasks will establish integration, not real-world accuracy. No M5 test access.

All 95 SageMaker CPU checks passed at 6b01867 (33.802 seconds), including fresh
offline custom-package parity, prediction compatibility, publication failure,
history/download and reserved-final-budget behavior.

## Recorded core acceptance (2026-11-01)

Earlier core acceptance at source `20d88f21a2b51fd6b7cee190191e7551c7507ac6`
passed the recorded CPU and focused stop checks. One synthetic
classification and one synthetic segmentation request each exercised the real
import→clarification→bounded job→full validation→selection→standalone verification
→package path. They used 62.74250063000363 GPU-job seconds total. Segmentation
also exercised service restart/reconnect and stop-after-current-experiment; the
focused real-model stop regression reached terminal state in 2.034 seconds without
launching a GPU attempt. These fixtures prove integration, not accuracy.

The neutral conversation workspace exposes timestamped messages, a saved-chat
sidebar, real durable progress, prediction, history and downloads. The exact 32 MiB browser boundary
passed the authenticated proxy; the proxy's own maximum remains unknown. All
four historical ledgers remained byte-identical and protected test access remained
false. Six packages passed isolated CPU parity; redistribution remains unresolved,
so they stay private research artifacts.

Independent snapshot `20261101T011658427603Z-recovery.tar.gz` (761,801,322 bytes,
SHA-256 `f8f21322ddf71750c5d627ffe8accd6fa974c2037f8802f416e4855401684769`)
passed all 174 member checks at the receiver. Both selected checkpoints and the
acceptance record were restored byte-for-byte. Exact run IDs, hashes, limitations
and backup receipts live in [M4 evidence](../m4-evidence.json).

## Follow-up fixes (2026-11-01)

- A draft/needs-input conversation with no bound dataset can receive one validated
  ZIP or saved-data ID in a reply, preserving messages, limits and charged calls.
  Existing attachments and frozen requests cannot be replaced.
- Failed progress reads retry with backoff up to 30 seconds; reconnect never
  resubmits Start. Switching chats cancels stale polling/response updates.
- Training-start IDs are persisted per conversation. History navigation clears
  the previous chat's attachment/pending state and distinguishes a missing job
  (404) from a connection failure before enabling a new start.
- Initially untested at the user’s request; the subsequent authorized visible demo
  deployed d60b46b and passed 15 existing request tests, late ZIP attachment, live
  training, browser refresh/reconnect, prediction, history and model download.
  Four training/two validation images took one attempt and about 40 seconds; this
  synthetic fixture proves workflow integration only. Exact receipts and remaining
  checks are in [M4 evidence](../m4-evidence.json).
  Transient-read failure injection, cross-chat regressions, saved-data attachment
  and the independent segmentation ZIP receipt remain pending. M5 is untouched.
