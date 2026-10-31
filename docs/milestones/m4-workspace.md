# M4: Make results usable

**Status:** UI preparation implemented; user design confirmation pending.
**GitHub:** [M4](https://github.com/Hsenabbass/GoTrain/milestone/4)
**Direction:** [Project plan](../PROJECT_PLAN.md#m4-make-results-usable)

## Outcome and scope

Make the M3 engine and selected models usable through a minimal message interface,
model packages, predictions and exports. Final test evaluation stays in M5.

User direction, 2026-10-31: simplify the UI first, show it for confirmation, then
present a detailed plan and obtain confirmation before each implementation step.
Update GitHub issues and shared documentation after completed work.

## Work sequence

| Step / issue | Scope | Completion check |
| --- | --- | --- |
| [4.1: Simplify the UI for the agreed workspace scope](https://github.com/Hsenabbass/GoTrain/issues/18) | One message composer, dataset selection and Send; no extra navigation or dashboards | Local syntax/browser checks and reviewable preview. Design acceptance pending. |

Next backend step remains unapproved; present its detailed plan after UI review.

## Decisions and boundaries

The latest user request supersedes the earlier four-dataset sidebar and three-view
UI proposal: users should describe their goal and constraints in one message and
attach a dataset. Preserve the neutral visual style. Remove dataset cards, view
tabs, game, artificial results, progress simulation and fake exports.

The file chooser currently selects a local file only. Send displays an explicit
not-connected status; no message or file is transmitted. Draft text persists
locally; file selections do not persist. No arbitrary file formats are advertised
as trainable. No cloud jobs, package installations or backend changes occur here.

The engine still supports four registered benchmark tasks; new dataset autonomous
training requires format validation, trusted registration/reference setup and
runner wiring. M3's manifest preparation API is not a complete upload-to-training
path. Plan this gap explicitly before activating upload/send integration. Natural
language constraints must be translated to allowed typed settings and enforced
by the existing trusted controller, not treated as new permissions or budget caps.

Model packaging still needs architecture/preprocessing/provenance preservation,
weight-term review and removal or packaging of cached initialization dependencies.
M1/M2/M3 usage stays intact; completed M3 sessions must not be restarted.

## Verification and evidence

Local Node syntax and whitespace checks; desktop/mobile browser review of message
entry, disabled empty Send, explicit disconnected submission, draft persistence,
file selection/removal and layout. See the issue and [UI instructions](../../ui/README.md).
No SageMaker/GPU/Bedrock results are claimed for this design change.

## Handoff

**Last updated:** 2026-10-31.
**Current state:** message-only local preview on codex/m4-ui-simplification; PR 19.
**Blockers:** none for design review; backend and custom dataset runner integration
remain unimplemented.
**Next action:** user confirms UI, then review a detailed plan for the next step.
**Synchronization:** source, instructions and GitHub tracking updated together.

## Completion

M4 is not complete. UI implementation awaits user design confirmation. Do not
start backend steps or final-test evaluation without the agreed next-step gate.
