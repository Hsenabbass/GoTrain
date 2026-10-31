# M4: Make results usable

**Status:** UI preparation implemented; design confirmation pending. Backend implementation not started.
**GitHub:** [M4](https://github.com/Hsenabbass/GoTrain/milestone/4)
**Direction:** [Project plan](../PROJECT_PLAN.md#m4-make-results-usable)

## Outcome and scope

Turn selected M3 models and their experiment records into usable model packages,
predictions, exports and a simple connected workspace. Reuse the four registered
benchmark tasks. Final test evaluation belongs to M5.

2026-10-31 user direction: simplify the existing UI first and show it for
confirmation. Present a detailed plan for each subsequent step and wait for the
user's confirmation before implementing that step. Update GitHub issues and
shared documentation after completed work. The earlier three-task proposal is
not blanket approval for backend work.

## Work sequence

| Step / issue | Scope | Completion check |
| --- | --- | --- |
| [4.1: Simplify the UI for the agreed workspace scope](https://github.com/Hsenabbass/GoTrain/issues/18) | Preserve neutral design; four datasets; task drafts; experiment/prediction placeholders. Remove extra and simulated features. | Local syntax/browser checks; reviewable preview, docs and source published. User design acceptance remains a separate gate. |

Next proposed step: self-contained model packaging and prediction. Detail and
number it only when presented for agreement. Integration and final UI verification
follow; do not create speculative implementation issues before the step is agreed.

## Decisions and boundaries

- Preserve local UI prototype history and merge completed remote M3 on a feature
  branch. Remote current ML status wins over the prototype's stale README status.
- No game, arbitrary projects, custom training-dataset uploads, fake scores,
  automatic training simulation, fake inference or pretend model downloads.
- Keep dataset navigation, Task/Experiments/Predictions views, per-dataset editable
  task drafts and compatible-input explanations. Unsupported controls are disabled.
- No unapproved launch budget is presented as available. Future launch controls
  must use enforced backend allowances and preserve historical M1/M2/M3 usage.
- Backend training/inference remains on SageMaker. The local static preview is
  design work only. No dependencies installed or cloud jobs launched.
- M3 handoff limits remain: custom-task runner registration is incomplete;
  exported models need weight-term review and removal/packaging of initialization
  cache dependencies. Scores are validation-only and gains remain provisional.

## Verification and evidence

UI checks are recorded in the linked issue and PR. Browser review: desktop
1365×900, mobile 390×844, four task-specific prediction requirements, empty
experiment state, suggestion/draft persistence, navigation and disabled controls.
Node syntax checks and git diff --check pass. No cloud compatibility is claimed.

## Handoff

**Last updated:** 2026-10-31.
**Current state:** simplified local preview implemented on codex/m4-ui-simplification.
**Blockers:** none for design review; model packaging and backend remain unimplemented.
**Next action:** user reviews the UI. After design confirmation, present the detailed
model-package/prediction step for approval before implementation.
**Synchronization:** publish source/docs and completion evidence to GitHub; PR
remains for review. M4 stays open; design approval is pending.

## Completion

M4 is not complete. UI-only preparation does not establish training, inference,
exports, custom-data support or final-test results.
