# GoTrain message interface

One message composer for the desired model and constraints, plus Upload dataset
and Send. No sidebar, dataset grid, game or simulated training/results.

## Connected service

Run the Python service on SageMaker as documented in [service setup](../docs/service.md).
It serves these same UI files and their relative API routes behind the existing
authenticated Studio proxy. A message and optional manifest ZIP are submitted
only when Send is pressed. A named prepared benchmark is also supported.

Preflight asks necessary questions and keeps the same attachment, limits and
charged model requests when replying. A compact summary shows the understood
request. Refresh/service restart restores persisted records without reissuing a
model call. New request clears only the browser's current draft reference; it
does not delete server history. File references and conversation IDs are opaque.

Training is not enabled yet: Start training remains disabled. The implemented
job protocol adds inline persisted progress and Stop after current experiment,
with read-only reconnect and a stable start key. These controls follow the health
flag and saved real job records. Package integration and live GPU acceptance
remain pending; no fake progress or scores appear.

Message drafts use gotrain-message-draft-v1; the current conversation, validated
dataset ID and safe-retry key use gotrain-request-session-v1 in localStorage.
Selected files are not persisted, but a successfully validated import can be
reused by the same draft after refresh. Browser storage is optional.

## Disconnected design preview

With Node.js 18 or later, run from the repository root:

```powershell
node ui/server.mjs
```

Open http://localhost:5173. This static server has no API. The UI explicitly
reports a disconnected preview and does not transmit messages or files. No install
is needed for this design-only mode.

Run npm run check from ui/, or node --check on src/app.js and server.mjs.
Backend verification and current restrictions are recorded in [M4 evidence](../docs/m4-evidence.json).
All agent and ML execution stays on the provided SageMaker instance.
