# GoTrain

An AI agent that turns a geospatial dataset and a task description into a trained, evaluated, usable model.

Built for the AUB ACM × RASID hackathon, 31 October–1 November 2026.

## Start here

- **[Project plan](docs/PROJECT_PLAN.md):** our goals, approach, five milestones, dependencies, and when to use each tool.
- **[Repository workflow](docs/WORKFLOW.md):** folder conventions and how plans, code, evidence, and documentation stay consistent.
- **[Manual training](docs/training.md):** verified run commands, guardrails and record format.
- **[Storage and recovery](docs/storage.md):** teammate data access, verified backups, and restore steps.
- **[GitHub milestones](https://github.com/Hsenabbass/GoTrain/milestones):** milestone progress and implementation tasks.
- **[Challenge brief](GoTrain%20Challenge.pdf):** the source of the hackathon requirements.

## What we are building

GoTrain will inspect and prepare data, compare training approaches, improve promising models, and deliver a model package with results and experiment history. Claude will direct experiments through Strands tools, within enforced limits on time, compute, retries, and permitted changes.

Our four benchmark tasks are **EuroSAT**, **Brick-Kiln**, **PV4GER-Seg**, and **Chesapeake**: two classification tasks and two segmentation tasks.

The agent comes first. A chat-style interface will later support dataset imports, task descriptions, live progress, predictions, model versions, and exports.

## Roadmap

| Milestone | Outcome |
| --- | --- |
| [1. Establish the foundation](https://github.com/Hsenabbass/GoTrain/milestone/1) | Verified tools, understood data, and working reference recipes. |
| [2. Build the autonomous engine](https://github.com/Hsenabbass/GoTrain/milestone/2) | Claude completes a measured improvement cycle through reliable tools. |
| [3. Demonstrate reliable improvement](https://github.com/Hsenabbass/GoTrain/milestone/3) | The agent works across all four tasks with trustworthy comparisons. |
| [4. Make results usable](https://github.com/Hsenabbass/GoTrain/milestone/4) | Versioned model packages and an interface for running and using them. |
| [5. Finalize the submission](https://github.com/Hsenabbass/GoTrain/milestone/5) | One final test evaluation per task, complete evidence, and a rehearsed demo. |

## Rules we build around

- Build and run on the provided **SageMaker GPU instance**, using **Strands** and **Claude Sonnet through Bedrock**.
- Train on training data; select and improve models using validation data. Access each test split **once, at the end**, with its final pipeline.
- Preserve official splits and labels. Keep logs explaining every score.
- Submit the GitHub repository, four final test scores with logs, and a presentation.

## Current status and team workflow

A simplified [conversation UI](ui/README.md) provides timestamped user/agent messages, dataset attachment, durable progress, prediction, history and package download. The [service](docs/service.md) is live on SageMaker with verified imports, clarification, bounded training, reconnect/stop and package publication.

**M1 is complete (tasks 1.1–1.7).** All four [reference recipes/results](docs/references.md) passed complete validation and fresh-process checkpoint revalidation, with verified independent model backups. See the [M1 evidence and handoff](docs/milestones/m1-foundation.md).

**[M2 is complete (2.1–2.2)](docs/milestones/m2-engine.md).** Claude completed one bounded EuroSAT cycle, rejected a lower-scoring change and retained the 87.00% reference checkpoint. Reload/prediction and independent backups are verified; [test payloads remain sealed](docs/data.md). [M3 is complete (3.1–3.3)](docs/milestones/m3-improvement.md): all four bounded searches retained better validation models, with checkpoint reload/prediction and independent backups verified. Gains remain single-seed/provisional; test payloads remain sealed. The minimal message UI is implemented.

[M4 is complete](docs/milestones/m4-product.md): versioned standalone models, supported imports, bounded durable jobs, and a minimal conversation workspace with prediction, history and downloads. SageMaker request checks, deterministic UI recovery/error checks, live clarification/attachment/chat-switching workflows and independent package/recovery checks passed. Synthetic fixtures prove integration, not real-world accuracy. Validation remains provisional and public weight redistribution is unresolved, so packages stay private research artifacts. [M5 is planned](docs/milestones/m5-submission.md) for parallel UI polish and results summaries/tiny checks, followed by a 3–5 minute presentation with a 1–2 minute demo video; implementation has not started. Required official held-out test scores remain a separate pending submission gate.

Use the project plan as the shared direction and GitHub milestones to track delivery. We will break down **one milestone at a time** into implementation issues, with clear completion checks. Keep setup instructions, decisions, experiment evidence, and progress current as the project develops. Do not commit credentials, downloaded datasets, or large model files; store artifacts separately and record their locations.

Reusable access routes and storage references belong in the [resource index](docs/RESOURCES.md). Codex follows [AGENTS.md](AGENTS.md); detailed milestone plans live in `docs/milestones/` as each milestone is planned.
