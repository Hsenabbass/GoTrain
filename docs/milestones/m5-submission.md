# M5: Polish the experience and prepare the presentation

**Status:** Planned; implementation not started.
**GitHub:** [M5](https://github.com/Hsenabbass/GoTrain/milestone/5)
**Direction:** [Project plan](../PROJECT_PLAN.md#m5-finalize-the-submission)

## Outcome and scope

Improve the existing interface and turn completed experiments into a professional,
visual presentation. The user handles UI polish; their friend prepares rehearsal content and results.
These tasks run independently. Presentation and video use both completed handoffs.
No new model search, backend features or benchmark training is planned.

## Work sequence

| Task | Owner / dependency | Scope and handoff |
| --- | --- | --- |
| [5.1: Polish the existing interface for the demo](https://github.com/Hsenabbass/GoTrain/issues/23) | User; independent of 5.2 | Refine existing typography, spacing, composer/attachments, limit displays, progress/results, history and responsive/keyboard behavior. Preserve the current visual direction, features, API and request/metric/budget contracts. Own focused checks of changed UI. Hand off final UI revision and clean compose/progress/result screenshots with brief factual captions; 5.3 selects images. |
| [5.2: Prepare the presentation brief, results and checks](https://github.com/Hsenabbass/GoTrain/issues/24) | Friend; independent of 5.1 | Reuse M1–M4 evidence against the completed M4 backend/model contracts. Produce a concise presentation rehearsal brief, organizer-tool role map, draft pipeline schema and practice Q&As, alongside the results document, comparisons, figures and reliability summary. Run only justified tiny saved-model checks; no dependency on polished UI. |
| [5.3: Create the presentation and demo video](https://github.com/Hsenabbass/GoTrain/issues/25) | After both handoffs | Use final UI/screenshots from 5.1 and rehearsal content/evidence/figures from 5.2. Select the final story and slide content here; deliver a short professional deck, a 1–2 minute real demo video and a short speaking script. Briefly check the final integrated demo, then rehearse once. |

### Keep parallel work independent

- 5.1 owns UI files and directly affected UI documentation; 5.2 owns rehearsal content, results and
  chart/evidence work. Coordinate shared-document edits and preserve teammate work
  on main; never change another person's active checkout.
- 5.2 uses the stable [completed M4](m4-product.md#handoff) baseline (`88b5bf9`),
  not 5.1's pending interface changes. Record actual code/model revisions.
- UI-specific verification belongs to 5.1; the final demo integration check belongs
  to 5.3. Do not make 5.2 wait for or retest UI polish.
- Keep service contracts unchanged. A backend/new-feature proposal is outside 5.1
  and must not silently expand the parallel results task.

### Prepare simple technical practice material

5.2 creates `docs/m5-presentation-brief.md` during execution: roughly 2–3 pages of
clear practice material, not a slide deck. Use short sections and a few sentences
per topic, with internal source links:

- Brief introduction, the problem and the agent's goal.
- Inputs (instruction, supported labeled data, limits) and outputs (model package,
  validation results, prediction, experiment history and download).
- Generality: image classification versus semantic segmentation, the shared data
  adapter, four benchmarks/custom fixtures, and supported-format/metadata limits.
- Pipeline: inspect/clarify → freeze task/limits → prepare/shortlist → bounded
  experiments → validate/select → package/predict. Supply a simple draft schema.
- Operation: Claude reasons and chooses; Strands connects typed tools; trusted
  software trains, scores, records decisions and enforces limits. Explain one real
  keep/reject example and the user-facing workflow.
- A few technical details in plain language: pretrained recipes/checkpoints,
  consistent preprocessing, accuracy versus macro IoU, split isolation, budgets
  and durable jobs. Avoid implementation trivia and unimplemented capabilities.
- Organizer-tool mapping: tool, purpose, actual use and evidence for SageMaker,
  Claude Sonnet through Bedrock, Strands, the four GEO-Bench datasets and GitHub.
  Label supporting tools such as PyTorch/service/UI separately from requirements.
- Key results and honest limitations, plus 4–6 short practice Q&As. Link detailed
  numbers/plots to `docs/m5-results.md` rather than duplicating source records.

Reuse the project plan, setup/service/training docs and existing evidence; inspect
focused code only to resolve a claim. The brief helps the team rehearse now;
**5.3 decides what enters the final presentation**. It must not wait for UI polish.

### Reuse the existing results; keep new checks tiny

The work is already largely done: [M1 references](../references.md) and
[M1 evidence](../m1-evidence.json) contain the four baselines;
[M3 evidence](../m3-evidence.json), under `searches.results`, contains selected
full-validation scores, trials, decisions, resource use, run IDs and successful
checkpoint reloads for all four datasets. [M4 evidence](../m4-evidence.json)
contains live custom-data workflows, package/prediction checks and recovery.

Keep the results/checks portion short by summarizing these records, not rerunning
them. The rehearsal brief adds content preparation, not new engineering. Create `docs/m5-results.md` during execution with one comparison
row per dataset: metric, baseline, selected score, percentage-point gain, sample
count and source run links. Add short experiment/keep-reject/failure explanations
and chart-ready assets. Separate accuracy and macro-IoU panels; do not average
unlike metrics. Disclose single-seed results, pretraining/recipe differences,
actual training progress, failed trials and unmeasured alternatives.

Reuse existing verified checks by default. If a concrete gap remains, use at most
four allowed validation images per task type with retained models on SageMaker.
Record sample counts/source/output/cost. No new training, large downloads, full
validation reruns or official test-split access. Label tiny/synthetic smoke checks
separately from existing full-validation benchmark comparisons.

### Presentation and video

Target **3–5 minutes total, including video**, with presenters doing most of the
explanation. In 5.3, review the practice brief and choose what best fits the slot;
do not try to include every topic. Five visual-first slides are a starting option:
problem/product image; hybrid agent/tool schema; results/experiment insight;
demo video; takeaways/limits. Keep unused explanations and Q&As in backup notes.
Use actual polished UI images, legible charts, consistent typography and restrained
color. Keep text short and supporting details/source links in speaker notes.

The video is **1–2 minutes**, preferably 60–90 seconds to leave speaking time:
instruction/data → clarification/limits → real progress → prediction → history/export.
Reuse existing completed runs, clearly mark cuts/resumed results and avoid new
training solely for footage. Hide private access URLs and credentials. Save an
editable deck, PDF, MP4, figure/screenshot assets and a timed speaking script;
include a still-image fallback and verify playback/legibility once.

## Decisions and open questions

- **2026-11-01, revised user direction:** supersedes the sequential UI→release-check
  plan. UI polish and results work are parallel; only presentation depends on both.
  The video is now 1–2 minutes, within the total 3–5 minute presentation slot.
- **2026-11-01, expanded content handoff:** 5.2 also prepares a simple technical
  rehearsal brief and required-tool explanations. Final narrative/slide selection
  stays in 5.3; 5.1 supplies factual screenshot captions independently.
- **Submission gate:** the challenge's four final held-out test scores remain
  required unless organizers waive them. They have not been produced. The user's
  small-data-only scope does not authorize replacing them with subset/synthetic
  scores or accessing the full test splits in 5.2. Record this pending requirement
  in the readiness note; presentation readiness is not submission completion.
- Preserve budgets, protected splits and private research export restrictions.
  All agent/training/inference runs stay on SageMaker; coordinate its shared GPU
  lock and never reset completed milestone ledgers.
- Confirm organizer media requirements before final export; the
  [submission deadline](../setup.md#operating-agreements-and-follow-ups) takes
  priority. Cut optional polish before evidence integrity or deliverable clarity.

## Verification and evidence

Planning review confirmed the existing four M1→M3 comparisons and M4 reliability
receipts. No experiments, UI changes or media production were run. During work,
link each task's screenshots, results/figures and final media; back up valuable
artifacts using [storage and recovery](../storage.md) and record actual locations.

## Handoff

**Last updated:** 2026-11-01.
**Current state:** Three open implementation issues created in M5; plan only.
**Blockers:** None for parallel 5.1/5.2. Final official test scores and organizer
media requirements remain submission-readiness items, separate from tiny smoke checks.
**Next action:** User starts 5.1 and friend starts 5.2 independently; 5.3 follows both.
**Synchronization:** Plan and GitHub issues agree; no implementation started.

## Completion

Pending task deliverables and saved/synchronized evidence. Do not mark the overall
submission complete while required official test scores or other brief items are
missing; record any organizer-approved change explicitly.
