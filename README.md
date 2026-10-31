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

**M1 is complete (tasks 1.1–1.7).** All four [reference recipes/results](docs/references.md) passed complete validation and fresh-process checkpoint revalidation, with verified independent model backups. See the [M1 evidence and handoff](docs/milestones/m1-foundation.md).

The four selected datasets and evaluation/resource contracts are verified; [test payloads remain sealed](docs/data.md). The shared [manual runner](docs/training.md) is ready for M2. **[M2 is in progress](docs/milestones/m2-engine.md)**: 2.1’s bounded Claude/Strands tools are implemented and pass SageMaker checks. The autonomous cycle (2.2) and UI remain unverified/unimplemented respectively.

Use the project plan as the shared direction and GitHub milestones to track delivery. We will break down **one milestone at a time** into implementation issues, with clear completion checks. Keep setup instructions, decisions, experiment evidence, and progress current as the project develops. Do not commit credentials, downloaded datasets, or large model files; store artifacts separately and record their locations.

Reusable access routes and storage references belong in the [resource index](docs/RESOURCES.md). Codex follows [AGENTS.md](AGENTS.md); detailed milestone plans live in `docs/milestones/` as each milestone is planned.
