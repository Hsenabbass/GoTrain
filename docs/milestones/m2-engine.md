# M2: Build the autonomous engine

**Status:** complete 2026-10-31; 2.1 and 2.2 verified.
**GitHub:** [M2](https://github.com/Hsenabbass/GoTrain/milestone/2)
**Direction:** [Agreed M2 outcome](../PROJECT_PLAN.md#m2-build-the-autonomous-engine)

## Outcome and scope

One Claude/Strands agent independently inspects EuroSAT, trains a starting recipe,
reads full-validation evidence, proposes and runs one configuration change, and
records whether to keep it. Retain the best valid checkpoint, including the M1
reference if neither new run improves it. A measured rejection is a valid outcome;
a score gain is not required to prove the loop works.

Reuse the [manual runner](../training.md), [M1 references](../references.md),
[data/evaluation contracts](../data.md), and verified SageMaker environment.
Implement the shortest working path, then run it once. Two issues include their
own checks and documentation; no separate setup, audit or handoff issue.

## Work sequence

| Step / issue | Prerequisites | Tools, inputs, outputs | Completion check |
| --- | --- | --- | --- |
| [2.1: Connect Claude to bounded experiment tools](https://github.com/Hsenabbass/GoTrain/issues/13) | Completed M1 | Existing Python runner + Strands/Bedrock → one detached CLI agent, small typed tools and persistent decisions | Tools inspect registered task evidence, train/prepare, read validation, predict from a retained checkpoint and record selection. Invalid inputs cannot widen limits, access test or overwrite protected records. Bounds, failure handling and prior-best preservation pass focused SageMaker checks. |
| [2.2: Demonstrate one autonomous improvement cycle](https://github.com/Hsenabbass/GoTrain/issues/14) | 2.1 | EuroSAT + frozen reference + bounded tools → two linked runs, decision and selected checkpoint | One invocation completes inspection → training → evidence → justified change → full validation → keep/reject without routine human decisions. Record actual LLM/GPU usage, verify selected-checkpoint reload/prediction, and independently back up new evidence/models. Stop after acceptance. |

## Decisions and open questions

- **2026-10-31, user direction:** prioritize simple, useful steps and fast delivery.
  This narrows M2 to configuration-only experiments on one task. Controlled code
  editing remains a later option only when evidence justifies it; no shell,
  arbitrary file-write or code-execution tool is exposed to Claude.
- Wrap existing operations; preparation/validation/checkpoint storage can stay
  inside the training tool. Do not invent a separate service for each operation.
  Inspection may reuse verified task metadata and train/validation diagnostics.
- Accept only registered task/run IDs and allowlisted recipe fields. The trusted
  controller owns splits, evaluator, budgets, run records and best selection.
  Claude supplies the hypothesis/change and interprets results; software compares
  eligible full-validation scores using the frozen contract. References stay intact.
- Use the verified model/region in the [project plan](../PROJECT_PLAN.md#tools-and-external-resources).
  Reuse the working environment; pin the observed Strands/Bedrock dependencies
  when adding the agent. Do not repair unrelated inherited package conflicts.
- **Enforced caps:** two normal training runs,
  at most one eligible failure retry; 1,500 seconds total GPU-job wall time,
  including verification/retries; existing 600-second/10-epoch/5,000-step run caps
  and memory/disk/validation reserves. Keep M1 usage unchanged and charge M2 in a
  separate versioned allocation under the same single-GPU lock. Bound the whole
  agent invocation to 1,800 seconds, 12 model requests, 2,048 output tokens per
  request and 20 tool calls. Retries count toward these caps. Retain the submission
  reserve in the existing deadline guard. These are project limits, not organizer quotas.
- Launch the agent as a detached SageMaker process with durable logs and decisions;
  a browser/chat disconnect must not terminate it. Record ordinary failures and
  either take the one permitted retry or stop with the prior best available.
- Verify only new boundaries and failure/selection behavior, then the real cycle.
  Do not repeat M1 training, data inspection, backups or cloud access probes just
  to reconfirm completed work. The new starting run is part of the agent's cycle.
- M3 covers all four tasks, wider search and broad restart/recovery exercises.
  UI, imports and packaging remain M4; test evaluation remains M5. No extra
  services, database, multi-agent system, tuner or new model family in M2.
- Carry forward [operating limitations](../setup.md#operating-agreements-and-follow-ups).
  No known M1 blocker prevents implementation; check session/GPU availability when
  starting. Surface an actual access or budget failure promptly rather than expanding scope.

## Verification and evidence

| Outcome / issue | Check and environment | Result | Evidence |
| --- | --- | --- | --- |
| Bounded tools and controller (2.1) | 7 new boundary/controller tests + 12 runner regression checks on SageMaker | Pass, 2026-10-31; 19 tests in 1.428 s | Source `747ac9f`; `artifacts/runs/m2-tool-checks/checks.log`; [independent recovery receipt](../RESOURCES.md#recovery-verification) |
| Autonomous cycle (2.2) | One detached EuroSAT cycle on SageMaker; trusted record/hash audit, retained-checkpoint reload/prediction and independent backup | Pass, 2026-10-31; baseline 87.00%, candidate 86.20%; prior best retained, reload delta 0 | [Cycle evidence](../m2-evidence.json); `artifacts/runs/m2-cycle/`; [recovery receipt](../RESOURCES.md#recovery-verification) |

## Results and limitations

Claude inspected the registered task, reproduced the starting recipe, then chose
to lower learning rate from 0.01 to 0.003. Both runs completed 10 epochs and full
validation on all 1,000 images. The starting run tied M1 at 87.00%; the change
scored 86.20%. Trusted selection rejected both promotions and retained M1's best.
The agent reloaded that checkpoint in a fresh process: full-validation delta 0,
prediction shape `[1]`, probability shape `[1, 10]`, probability-sum error < 1.2e-7.

The run used 350.45 / 1,500 GPU-job wall seconds (341.02 training + 9.43 verification),
9 / 12 model requests and 10 / 20 tool calls. Bedrock reported 99,624 input and
2,762 output tokens. Zero GPU retries; no active reservation. M1's ledger hash
remained unchanged. No routine human experiment decisions or test access occurred.
The tool rejected a 30-epoch proposal and an invalid retry request before training.

This is one single-seed configuration comparison, not a performance improvement
or statistical significance result. Claude's response inaccurately suggested the
invalid retry consumed retry allowance; the durable counter and GPU ledger show
zero retries. Its suggestion that the score gap is noise is not established by
this run. Use trusted records for scores, selection and usage. All-task search and
broader restart/recovery behavior remain M3.

## Handoff

**Last updated:** 2026-10-31.
**Current state:** M2 complete. Bounded tools passed SageMaker checks; the real autonomous cycle, protected keep/reject decision, retained checkpoint reload and independent recovery copies are verified. Exact records live in [M2 evidence](../m2-evidence.json).
**Blockers:** none for M2. Organizer quotas and judging/presentation details remain pending; existing operating limitations still apply.
**Next action:** plan M3 when requested. Reuse the retained references, tools and recorded M2 usage; do not reset historical budgets or reopen test access.
**Synchronization:** completion evidence/docs are published with GitHub task closure; fast-forward SageMaker to the completion commit before further work.

## Completion

Both issues meet M2 acceptance. No measured score gain was found; the demonstrated
outcome is a complete autonomous comparison that safely retained the prior best.
Both new candidate checkpoints and cycle evidence have independent checksum-verified
recovery copies. The selected M1 checkpoint retains its existing verified backup.
