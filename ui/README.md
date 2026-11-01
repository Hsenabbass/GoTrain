# GoTrain message interface

A conversation workspace for task instructions and clarification, with a left
workflow rail and a compact right task panel. Overview, Experiments and Use model
are persistent tabs. Run updates change in place; experiment records expose
candidate configurations, validation metrics, failures and selection decisions.
Model inputs and predictions survive tab switches. The panel uses a neutral slate
palette with indigo accents and is capped at 480px on wide screens.

Saved conversations reopen from the service. The disconnected preview offers an
explicitly labelled UI simulation only; it does not train or predict.

## Connected service

From the repository root on SageMaker, run `python start.py`. It selects the
verified service environment and port automatically. See [service setup](../docs/service.md)
for the explicit troubleshooting command.
It serves these same UI files and their relative API routes behind the existing
authenticated Studio proxy. A message and optional manifest ZIP are submitted
only when Send is pressed. A named prepared benchmark is also supported.

Preflight asks necessary questions and keeps the same attachment, limits and
charged model requests when replying. A compact summary shows the understood
request. Refresh/service restart restores persisted records without reissuing a
model call. New request clears only the browser's current draft reference; it
does not delete server history. File references and conversation IDs are opaque.

Start training follows the service health flag. The job protocol adds persisted
chat-style progress and Stop after current experiment, with read-only reconnect
and a stable start key. Completed jobs expose only their verified package,
validation result, history and prediction controls; no fake progress or scores
appear.

Message drafts use gotrain-message-draft-v1; the current conversation, validated
dataset ID and safe-retry key use gotrain-request-session-v1 in localStorage.
Selected files are not persisted, but a successfully validated import can be
reused by the same draft after refresh. Browser storage is optional.

## Disconnected design preview

With Node.js 18 or later, run from the repository root:

```powershell
python start.py
```

Open http://localhost:5173. This static server has no API. The UI explicitly
reports a disconnected preview and does not transmit messages or files. No install
is needed for this design-only mode.

Run npm run check from ui/, or node --check on src/app.js and server.mjs.
Backend verification and current restrictions are recorded in [M4 evidence](../docs/m4-evidence.json).
All agent and ML execution stays on the provided SageMaker instance.

## Follow-up implementation and verification

Unresolved chats without a dataset can attach one in a reply. Existing attachments
and frozen requests remain protected. Transient progress-read failures retry with
backoff without sending Start again. Training-start request IDs use the separate
`gotrain-start-requests-v1` browser storage map, keyed by conversation; history
navigation clears another chat's file/pending state before restoring the selection.
A subsequently authorized six-image SageMaker demo passed late ZIP attachment,
training, refresh/reconnect, prediction, history and download at d60b46b.
Six deterministic UI checks now cover retries, stale responses, per-chat start IDs,
history state restoration, connection errors and busy navigation. Live Safari
verified chat switching and saved-data clarification. Network failures were
simulated in fixtures; no production network fault was induced. See the current
[M4 handoff](../docs/milestones/m4-product.md#handoff) before final sign-off.

## M5 UI review (in progress)

The local UI now separates conversation from a right-hand proposal/run/model
workspace, with a left workflow rail, consistent actions, stable run counters,
ranked classification probabilities and a larger segmentation viewer. Only
observed stages receive completion marks; missing historical stages are labelled
not recorded. Existing request, prediction, metric and budget contracts remain.

JavaScript syntax and ten deterministic UI checks pass locally (six recovery checks plus four workspace/navigation checks).
User visual review, live-service verification, responsive/keyboard review and
5.3 screenshots/captions remain pending. No new training or inference was run.
SageMaker still serves the previous UI; this revision is available locally at
http://localhost:5173 for design review only. No screenshots captured and 5.1
is not complete.

The disconnected preview includes a replayable 30-second UI simulation for visual
review. Its stages, counters and decision text are explicitly illustrative; it
makes no training/prediction requests and produces no package or score. Changing
conversation cancels playback. This is not live-service verification.

### Rework review

Experiments is available during and after runs via the existing read-only history
API. It is a snapshot: Refresh retrieves subsequent results without collapsing
open candidates on every poll. A selected model's history uses the active task's
full history when applicable, or its package history when opened independently.
Missing records/metrics are labelled, never inferred. The preview includes two
illustrative candidates with no scores and an example decision explanation.

Verified locally: stale history responses are discarded after chat changes;
model inputs survive tab changes and background updates; delayed model loads do
not change the selected tab; offline history/model views make no API calls.
Safari accessibility inspection confirmed the persistent tabs and preview flow.
Visual approval, live SageMaker verification and screenshot handoff remain pending.
