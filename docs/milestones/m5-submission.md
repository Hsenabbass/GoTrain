# M5: Polish the experience and prepare the submission

**Status:** Planned; implementation not started.
**GitHub:** [M5](https://github.com/Hsenabbass/GoTrain/milestone/5)
**Direction:** [Project plan](../PROJECT_PLAN.md#m5-finalize-the-submission)

## Outcome and scope

Polish the working M4 product, check the release briefly, and deliver a concise
presentation plus a real demo video. Reuse [M4's verified workflows and models](m4-product.md#handoff).
Most effort goes to UI and presentation; no new model search, providers or services.

## Work sequence

| Task | Work and inputs | Done when |
| --- | --- | --- |
| 5.1: Polish the minimal interface | Keep the accepted neutral chat layout. Improve spacing, typography, composer and narrow-screen usability. Add a compact runtime control with other existing limits tucked into options; make supported-data guidance easy to find. Simplify progress/results, dataset labels and model/history actions. Fix demonstrated friction; avoid decorative additions. | Import → clarify → run → prediction/history/download is clear and consistent, with usable keyboard focus and readable empty/error/running/completed states. |
| 5.2: Check and freeze the release | Run existing relevant checks once after UI changes and one short live smoke check. Reuse M4 training/package evidence rather than retraining. Freeze the four retained benchmark pipelines from validation evidence, then evaluate each official test split exactly once on SageMaker. Save scores, logs, hashes and verified backups. | Changed UI passes its checks; four final test scores have traceable logs; code/docs/packages agree. No tuning or repeated test evaluation after results. |
| 5.3: Create slides and record the demo | Make a short six-slide deck: problem; product workflow; hybrid Claude/Strands + trusted tools; measured results; live product walkthrough; limitations and next steps. Record a clean 2–3 minute real screen demo: instruction/data → clarification/limits → progress → prediction → history/export. Reuse recorded runs where suitable and clearly label time cuts. | Editable slides plus PDF, playable MP4 and a brief speaking/demo script are saved; claims match evidence and no private access URLs or credentials appear. |

## Decisions and open questions

- **2026-11-01, user direction:** focus M5 on UI enhancements, brief testing and
  slides/demo video. Preserve the original submission requirement for four final
  test scores; UI work does not replace that evaluation.
- Preserve existing data contracts, budgets, authenticated hosting and private
  weight restrictions. All agent/training/inference execution stays on SageMaker.
- Do not repeat M4 acceptance or add training solely for video footage. Label
  synthetic examples as workflow demonstrations and distinguish validation/test results.
- Six slides and a 2–3 minute video are working defaults; verify organizer format
  requirements before export. The [submission deadline](../setup.md#operating-agreements-and-follow-ups)
  takes priority; cut optional polish first.

## Verification and evidence

Not started. Record changed-UI checks, final evaluation logs, slide/video locations
and independent recovery receipts here during execution. Follow [storage and recovery](../storage.md).

## Handoff

**Last updated:** 2026-11-01.
**Current state:** Plan only; M4 is complete. No UI changes, evaluation or media production started.
**Blockers:** None to begin UI work; organizer media requirements remain to be confirmed.
**Next action:** Implement 5.1, then run 5.2 and finalize 5.3 using verified results.
**Tracking:** Numbered implementation issues have not been created yet.

## Completion

Pending the three task outcomes, saved deliverables and synchronized GitHub/docs.
