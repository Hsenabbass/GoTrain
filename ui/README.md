# GoTrain message interface

A compact chat timeline for the desired model and constraints, plus Upload
dataset and Send. User and GoTrain messages remain in chronological order with
timestamps. Persisted training updates report the current stage, elapsed time,
attempts and model-request usage in the same timeline. A simple history sidebar
lists saved conversations and reopens them from the service. There is no dataset
grid, game or simulated training/results.

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
