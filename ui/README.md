# GoTrain UI preview

Local, dependency-free design preview for the four registered benchmark datasets.
Run from the repository root with Node.js 18 or later:

```powershell
node ui/server.mjs
```

Open http://localhost:5173. No package install or account is needed.

## Scope

The neutral workspace has four dataset choices (EuroSAT, Brick-Kiln, PV4GER-Seg,
Chesapeake) and three views: Task, Experiments and Predictions. Each task shows
its input channels, task type and validation metric. Suggested task text can be
edited; drafts persist per dataset in browser localStorage when available.

Training and image selection are disabled until backend integration. Experiment
and prediction views show honest empty states and dataset-specific input
requirements. This preview contains no scores or recorded experiment data and
makes no backend requests. It does not run training, inference or export models.
There is no game, arbitrary project creation, custom training-dataset upload,
simulated progress or fake download. Budget controls await enforced launch limits.

All UI files live under ui/. src/data/tasks.js contains static dataset descriptors
from configs/tasks.json and docs/data.md, not selected-model metadata. Integration
must obtain exact preprocessing and input requirements from the model package.
The former gotrain-projects localStorage key is ignored; only task drafts use the
new gotrain-workspace-drafts-v1 key. Existing browser data is not deleted.

## Verification

Run npm run check from ui/, or node --check on the four files named in package.json.
Local browser review covers desktop/mobile layout, all four dataset views,
keyboard navigation, suggested text, draft persistence and disabled actions.
No SageMaker/GPU/Bedrock execution is part of this UI-only change.

See [M4 handoff](../docs/milestones/m4-workspace.md). User design confirmation
precedes backend work; each following step receives its own detailed plan and
confirmation before implementation.
