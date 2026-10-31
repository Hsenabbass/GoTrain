# GoTrain UI preview

A single message composer for explaining a model goal and constraints, with an
Upload dataset control and Send button. Local-only design preview; no dependencies.

Run from the repository root with Node.js 18 or later:

```powershell
node ui/server.mjs
```

Open http://localhost:5173. The neutral design has no sidebar, dataset selector,
view tabs, game, experiment dashboard or mock model results.

Message drafts persist in browser localStorage under gotrain-message-draft-v1.
Selecting a dataset displays its filename and allows removal. Files are only
selected locally, never read or uploaded. After reload a file must be selected
again. Send requires a nonempty message and reports that the agent is not yet
connected; it does not claim successful transmission or start a simulated run.

Backend integration will translate task descriptions and constraints into the
trusted runner's allowed settings. The current autonomous runner supports four
registered benchmark tasks. New uploaded datasets still need supported format
validation, trusted task/reference registration and runner integration. The
existing local manifest preparation API alone does not establish this support.

Run npm run check from ui/, or node --check on src/app.js and server.mjs.
Local browser verification covers desktop/mobile layout, empty-message gating,
draft persistence, dataset selection/removal and the disconnected Send state.
No training, inference, cloud execution or package installation is performed.

See [M4 handoff](../docs/milestones/m4-workspace.md). User design confirmation
precedes backend work. Each following step receives a detailed plan and user
confirmation before implementation.
