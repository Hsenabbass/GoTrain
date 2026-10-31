# Resource index

Reusable operational references live here. See the
[project plan](PROJECT_PLAN.md#tools-and-external-resources) for required tools,
model/region requirements, and research references. See the
[workflow](WORKFLOW.md#naming-resources-and-evidence) for credentials and storage rules.

| Resource | Stable reference or access route | Verification / details |
| --- | --- | --- |
| GitHub repository | [Hsenabbass/GoTrain](https://github.com/Hsenabbass/GoTrain) | Local clone push and GitHub issue read/write observed 2026-10-31; SageMaker clone and disposable-branch push verified 2026-10-31 using explicitly approved GoTrain-only access expiring 2026-11-01; other teammates' access unverified. See [setup evidence](setup.md). |
| Milestones and tasks | [Milestones](https://github.com/Hsenabbass/GoTrain/milestones); [milestone index](PROJECT_PLAN.md#five-milestones) | Five milestones established; redundant overview issues deleted with user approval; [M1 breakdown](milestones/m1-foundation.md#work-sequence) created; task 1.1 complete; task 1.2 next. |
| SageMaker / JupyterLab | Obtain the organizer's temporary access link privately. | Existing Safari session verified 2026-10-31; GPU execution passed. See [setup evidence](setup.md). Keep the current session open; organizers can renew access as needed. Do not store access links here. |
| Bedrock / Strands | Provided SageMaker role; requirements in the project plan. | Required model response and one tool call verified 2026-10-31; quota lookup denied by role; organizer limits pending. See [setup evidence](setup.md). |
| GEO-Bench / Hugging Face | Selected tasks in the project plan. | GEO-Bench 1.1.0 imports and package-linked public dataset metadata access verified; selected-task downloads, exact data versions and data locations unverified. See [setup evidence](setup.md). |
| Persistent data and artifacts | SageMaker `/home/sagemaker-user`; check artifacts in `gotrain-access-check/`. | Capacity/writes and browser-reload continuity verified 2026-10-31; restart/expiry persistence and S3 permissions unverified. See [setup evidence](setup.md). |

Add a row only when useful. For a verified resource, record a stable safe link/path,
what was checked and when, and a link to the setup instructions or milestone
evidence. Keep credential values in private storage; record only the retrieval
method or environment variable name. Replace outdated references and explain
material location changes in the active milestone's decisions.
