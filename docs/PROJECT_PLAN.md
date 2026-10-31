# GoTrain: initial project plan

**Status:** [M1](milestones/m1-foundation.md) and [M2](milestones/m2-engine.md) are complete. Four verified references are retained; one autonomous EuroSAT cycle rejected a lower-scoring change and preserved the prior best, with checkpoint reload and independent backups verified. [M3 is in progress](milestones/m3-improvement.md): 3.1 task/model preparation is CPU-verified; search/training remains 3.2–3.3; later milestones remain unplanned in detail. Test payloads remain sealed; final submission models and the UI framework remain unselected.

[Repository home](../README.md) · [GitHub milestones](https://github.com/Hsenabbass/GoTrain/milestones) · [Challenge brief](../GoTrain%20Challenge.pdf)

## Goals and direction

Build an agent that automates the practical work of a data scientist and machine learning engineer for geospatial classification and segmentation.

Given a supported dataset, a task description, and a resource budget, GoTrain should:

1. Understand the task and inspect the data.
2. Prepare suitable inputs and identify data problems.
3. Compare a small set of justified training approaches.
4. Improve promising solutions using measured validation results.
5. Select a final pipeline and evaluate it once on the test split.
6. Deliver a usable model package, results, and an understandable experiment history.

The core goal is **useful autonomous decisions backed by evidence**. Strong scores matter, but we must also show how the agent reached them. We aim to improve our reference recipes; improvement is measured, not assumed.

The product direction is a chat-style interface: import a dataset, explain the task, watch progress, inspect results, use the trained model, and export it. The agent and prediction tools must work independently of this interface so they can later integrate with GoPilot.

## Our approach

Use a **hybrid agent**: Claude chooses what to try and interprets the results; tested software performs data operations, training, scoring, and storage.

- Begin with reliable recipes and configuration changes. Allow controlled training-code changes where justified.
- Keep evaluation, test access, resource limits, and experiment records outside the agent's editable experiment code. Enforce restrictions in software, not only in prompts.
- Compare several plausible approaches, then invest in promising candidates. The agent may revisit an earlier decision when evidence supports it.
- Give experiments explicit budgets. Screen weak candidates cheaply, while allowing enough training to avoid rejecting slow starters unfairly.
- Record the hypothesis, change, parent experiment, configuration/code version, data version, score, runtime, failure details, and checkpoint location. Keep a short decision summary explaining the next action.
- Retain the best validated pipeline, preserve alternatives, recover from ordinary failures, and stop at the budget or when further experiments offer little value.
- Start with one orchestrating agent and separate tools. Add complexity only when it solves a demonstrated problem.

Example: “The model misses small solar panels. Test a foreground-aware loss against the current recipe; retain it only if validation evidence supports the change.”

## Data and evaluation boundaries

| Selected task | Type and purpose | Input to verify |
| --- | --- | --- |
| `m-eurosat` | Classify 10 land-cover classes. | Sentinel-2, 13 channels; verify band mapping and normalization. |
| `m-brick-kiln` | Classify brick kiln present/absent. | 13 channels; verify band mapping and mixed reflectance/true-colour scales. |
| `m-pv4ger-seg` | Map solar-panel pixels. | Aerial RGB; inspect small foreground regions and image–mask alignment. |
| `m-chesapeake` | Map 7 land-cover classes. | RGB plus near-infrared; verify class IDs, valid pixels, and channel handling. |

These cover binary and multiclass classification and segmentation, with several input types. Download only these tasks from Hugging Face through the GEO-Bench workflow. Verify actual task identifiers and dataset versions rather than assuming the brief's shorthand matches loader names.

The official GEO-Bench repository documents incorrect band metadata in EuroSAT and Brick-Kiln. Pixel values are unaffected, but channel selection and preprocessing must use the documented mapping. Brick-Kiln includes true-colour composite channels that must not be treated as reflectance bands.

For the benchmark runs:

- Preserve official train/validation/test membership and ground truth. Report suspected problems rather than silently rewriting the benchmark.
- Fit learned preprocessing statistics on training data only. Use validation for selection, tuning, thresholds, and stopping.
- Keep test data out of exploration, training, previews, and iterative decisions. Evaluate each selected final pipeline on its test split once, at the end.
- Define the primary metric, ignored labels, and aggregation before comparing candidates. Use the relevant benchmark conventions; supplementary per-class metrics help diagnosis.
- Compare against fixed starting recipes under comparable resource budgets. Published results provide context, not guaranteed targets or automatically fair comparisons.
- Confirm meaningful gains where budget permits; report random seeds and limits on repeatability. Never compare validation scores with published test scores as equivalent evidence.

## Tools and external resources

**Required by the brief:** Strands, Claude Sonnet through Bedrock, the provided SageMaker GPU environment, four GEO-Bench tasks, GitHub submission, logs, and a presentation.

| Resource | First introduced | How and why we use it | Check before relying on it |
| --- | --- | --- | --- |
| **SageMaker + JupyterLab** | M1; all later work | Required place to build and run the project; hosts GPU jobs and persistent files. | Open the organizer link within 5 minutes, bookmark JupyterLab, verify GPU/VRAM, disk, packages, runtime limits, and job persistence. The brief describes sessions up to 12 hours; the user confirms no specific expiry is known and organizers can renew access. Keep the active session open; see the setup operating agreement. |
| **Claude Sonnet on Bedrock** | M1 access check; M2 agent | Reasons about experiments and calls tools. The brief specifies `eu.anthropic.claude-sonnet-5-5` in `eu-central-1`. | Verify the provided role can invoke that exact model; no separate Anthropic API key is expected. Confirm quotas. Explicitly set model/region instead of using SDK defaults. |
| **Strands (`strands-agents`)** | M1 smoke test; M2 core loop | Required framework connecting Claude to our Python tools through a ReAct loop: reason, act, observe, repeat. | Verify a minimal agent responds, then test tool calls and runtime controls. Pin the working package version. |
| **GEO-Bench (`geobench`) + Hugging Face** | M1; M3 evaluation | Load the four selected datasets, metadata, and official splits. | Confirm download access, exact versions/identifiers, channel order, labels, metrics, and storage needs. Do not download the whole benchmark. |
| **PyTorch + suitable vision-model libraries** | M1 recipes; M2–M4 training/inference | Train classifiers and segmenters and reuse pretrained models. Exact supporting libraries remain open. | Verify CUDA compatibility, GPU memory, pretrained-weight availability, input channels, and model licenses. Record versions and weight sources. |
| **Filesystem storage; optionally S3/Boto3** | M1 locations; M2 records; M4 exports | Save datasets, resumable runs, checkpoints, model versions, and downloads. Agent upload/download tools plus version tracking support extra credit. | Verify persistence, capacity, permissions, and artifact access. S3 access is not yet confirmed; do not assume permission to create cloud resources. |
| **Git + GitHub** | M1 onward | Keep code/docs reproducible, track work through milestones/issues, and deliver the submission. | Verify team access and the SageMaker clone/push workflow. Keep secrets and large artifacts out of Git. |
| **Optuna or another numerical tuner** | Optional in M3 | Search numeric parameters or stop weak trials while Claude directs the strategy. | Add only if it improves our bounded search; select budgets and stopping rules first. |
| **Experiment tracking** | M1 reference results; M2 onward | Preserve the evidence behind each score and make runs comparable. Structured files are enough initially; MLflow is optional. | Verify records survive restarts and connect every score to the exact data, code, recipe, and checkpoint. |
| **UI, backend, and import adapters** | M4 | Connect chat, progress, prediction, results, versions, and exports to the existing engine. | Choose the stack later. Check hosting/access on SageMaker, upload limits, supported file formats, and permissions for cloud links. |
| **Presentation tooling** | Evidence from M1; final assembly M5 | Explain decisions, architecture, results, limitations, and the production direction. | Confirm submission format and presentation length with organizers. |

Initial SageMaker GPU and Bedrock/Strands checks have passed; [the setup record](setup.md) distinguishes verified results from remaining permissions and quota checks. Local repository access and assistant integrations do not establish cloud runtime access. No additional hosted database, paid API, or tracking service is required by this plan.

## Submission and current operating constraints

The user confirmed submission for **2026-11-01 at 15:00 Asia/Beirut**. The
[setup operating agreement](setup.md#operating-agreements-and-follow-ups) owns
session handling and outstanding quota/judging/presentation details. Preserve
time for M5 within this deadline; unknown quotas do not imply unlimited use.

## Five milestones

The delivery sequence is **M1 → M2 → M3 → M4 → M5**. Small independent preparation can overlap, but each completion check depends on evidence from the preceding milestone. Capture documentation and demo evidence throughout.

| GitHub milestone | Depends on |
| --- | --- |
| [M1. Establish the foundation](https://github.com/Hsenabbass/GoTrain/milestone/1) | Organizer access and team access. |
| [M2. Build the autonomous engine](https://github.com/Hsenabbass/GoTrain/milestone/2) | M1. |
| [M3. Demonstrate reliable improvement](https://github.com/Hsenabbass/GoTrain/milestone/3) | M2. |
| [M4. Make results usable](https://github.com/Hsenabbass/GoTrain/milestone/4) | M3; design may start after M2 interfaces stabilize. |
| [M5. Finalize the submission](https://github.com/Hsenabbass/GoTrain/milestone/5) | M3 evidence and M4 packages/demo. |

### M1. Establish the foundation

**Detailed plan:** [M1 foundation plan](milestones/m1-foundation.md), including implementation issues, decision gates, evidence requirements, and current handoff.

**Prerequisites:** organizer JupyterLab link and provided permissions; challenge brief; GitHub team access.

**Cover:** define supported task/input/output contracts and budgets; verify all required infrastructure; inspect the four datasets; complete a manual classification and segmentation workflow; establish initial validation reference results on all four tasks.

**Tools and external checks:** introduce SageMaker/JupyterLab, the exact Bedrock model/region, Strands, GEO-Bench/Hugging Face, PyTorch/pretrained weights, GitHub, and persistent storage. Resolve band mappings and evaluation definitions before trusting scores. Ask organizers about GPU quotas, submission time, and judging metrics where unspecified.

**Done when:** required access works; a minimal Strands agent responds; repeatable training/validation recipes work; the four starting results and their settings are recorded. Detailed task contracts and budgets are documented.

### M2. Build the autonomous engine

**Detailed plan:** [M2 engine plan](milestones/m2-engine.md). Two outcome-sized issues; reuse M1 and demonstrate one configuration-only cycle on EuroSAT before expanding.

**Depends on:** M1's task contract, working recipes, evaluation definitions, and verified runtime.

**Cover:** turn inspection, preparation, training, validation, prediction, and storage into tools. Connect Claude through Strands. Add bounded experiments, protected evaluation, persistent records, checkpointing, and basic failure recovery. Complete one autonomous improvement cycle without routine human decisions.

**Tools and external checks:** use Strands/Bedrock for decisions, PyTorch for execution, and filesystem storage for records/artifacts. Confirm tool permissions and enforce time, retry, compute, and editable-file limits. Long-running training must not depend on a chat or browser staying open.

**Done when:** the agent independently inspects one task, trains, reads validation evidence, proposes and runs a change, and records whether to keep it. A rejected change leaves the best prior pipeline available.

### M3. Demonstrate reliable improvement

**Detailed plan:** [M3 improvement plan](milestones/m3-improvement.md). Three issues cover reusable image-task preparation/model choices, bounded search/tuning, and four-task verification. Add a local manifest adapter in M3 to avoid benchmark-only logic; broad import UX stays in M4.

**Depends on:** M2's functioning loop, trusted evaluator, and complete experiment records.

**Cover:** apply the same engine across all four tasks; compare plausible recipes fairly; improve promising candidates; verify rollback, ordinary failure recovery, stopping, and restart behavior. Compare agent results with the M1 reference recipes and explain both improvements and failures.

**Tools and external checks:** reuse GEO-Bench splits and metrics, PyTorch, Strands/Bedrock, and experiment records. Introduce a numerical tuner only if useful. Track both GPU use and LLM calls so experiments stay within budget. Keep test access disabled.

**Done when:** all four tasks have reproducible validation results and retained model candidates; logs explain decisions and resource use; the engine respects its restrictions. Gains are reported honestly, including tasks where no gain was found.

### M4. Make results usable

**Depends on:** M3's stable engine, saved candidates, prediction tools, and artifact records. UI design can begin earlier once M2's interfaces are stable.

**Cover:** package models with weights, architecture/configuration, preprocessing, channel order, class mapping, dependencies, and prediction entry point. Add versions and export/download tools. Build the chat-style interface around the engine: supported dataset import, task description, live progress, results/decision summaries, prediction previews, comparisons, and export.

**Tools and external checks:** choose UI/backend tools when planning this milestone. Begin with supported local uploads and dataset references; add S3 or other cloud imports only after checking permissions and formats. Use filesystem storage or verified S3 for artifacts. Interactive predictions use compatible user data or allowed validation examples, never the protected test split during development.

**Done when:** a teammate can follow a run, load a compatible input for prediction, inspect results/versions, and export a complete usable package. Refreshing the UI does not lose training progress. Clearly distinguish models still being selected from finalized models.

**Optional polish:** waiting-time game, advanced visuals, more import providers, additional datasets, or richer production infrastructure. Keep these behind agent reliability and required deliverables.

### M5. Finalize the submission

**Depends on:** M3's validated model selection and evidence; M4's usable packages/demo. Optional UI polish must not delay required submission work.

**Cover:** freeze one pipeline per task using validation evidence, run each test split once, and store final scores with complete logs. Finish reproducible setup/run instructions, clean the repository, assemble the presentation, and rehearse the demo. Describe the route to production/GoPilot and any unfinished extras.

**Tools and external checks:** use the protected GEO-Bench test evaluator on SageMaker, final artifact storage, GitHub, and presentation tooling. Confirm the exact deadline and submission/presentation format. After seeing test results, do not tune and test again.

**Done when:** the GitHub repository, four final test scores with their logs, and presentation are ready for submission; a teammate can follow the instructions and use the exported models. Limitations and resource budgets are explicit.

## How we track progress

The [repository workflow](WORKFLOW.md) defines file locations, authoritative sources, and the planning-to-completion update cycle. Use the [milestone template](milestones/TEMPLATE.md) for each detailed plan and the [resource index](RESOURCES.md) for reusable access and storage references.

- Use one GitHub milestone per milestone and actionable issues titled `<milestone>.<task>: <action>` (for example, `1.1: Verify access`). Keep milestone outcomes and acceptance evidence in the project plan and detailed milestone document; do not create milestone overview issues. GitHub issue numbers remain stable link identifiers.
- Before starting a milestone, expand only that milestone into small implementation issues with prerequisites, needed tools/data, and a clear completion check.
- Close issues using evidence, not just code being written. Update this document when an agreed decision changes.
- Keep detailed setup and experiment instructions in linked documentation as they become real. Do not invent commands for components that are not implemented yet.
- Do not assign speculative dates or owners. Agree on them with the team once access and training speeds are known.

## Research behind the direction

| Reference | Idea we borrow |
| --- | --- |
| [Karpathy autoresearch](https://github.com/karpathy/autoresearch) | Bounded experiment loop, measured keep/revert decisions, fixed evaluation. |
| [Solar-panel autoresearch](https://arxiv.org/abs/2610.10491) | Training-recipe improvements depend on hardware and the existing configuration; verify rather than assume. |
| [AIDE](https://arxiv.org/abs/2502.13138) | Explore alternatives, debug failed candidates, and refine promising experiments with remembered history. |
| [RSI4EO](https://arxiv.org/abs/2610.18845) | Define available resources and success clearly; evaluate complete prediction pipelines separately from editable experiments. |
| [GEO-Bench](https://arxiv.org/abs/2306.03831) and [known issues](https://github.com/ServiceNow/geo-bench#known-issues) | Standard tasks, correct data handling, and trustworthy comparisons. |
| [nnU-Net](https://github.com/MIC-DKFZ/nnUNet/blob/master/documentation/explanation/how-nnunet-works.md) | Inspect dataset properties before choosing preparation and training settings. |
| [Optuna](https://optuna.readthedocs.io/en/stable/tutorial/10_key_features/003_efficient_optimization_algorithms.html) | Spend more resources on promising experiments and stop weak trials sensibly. |

Research protocols are inspiration, not extra hackathon rules. The challenge brief remains the source for required tools, evaluation restrictions, and deliverables.
