# Resource index

Reusable operational references live here. See the
[project plan](PROJECT_PLAN.md#tools-and-external-resources) for required tools,
model/region requirements, and research references. See the
[workflow](WORKFLOW.md#naming-resources-and-evidence) for credentials and storage rules.

| Resource | Stable reference or access route | Verification / details |
| --- | --- | --- |
| GitHub repository | [Hsenabbass/GoTrain](https://github.com/Hsenabbass/GoTrain) | Local clone push and GitHub issue read/write observed 2026-10-31; SageMaker clone and disposable-branch push verified 2026-10-31 using explicitly approved GoTrain-only access expiring 2026-11-01; other teammates' access unverified. See [setup evidence](setup.md). |
| Milestones and tasks | [Milestones](https://github.com/Hsenabbass/GoTrain/milestones); [milestone index](PROJECT_PLAN.md#five-milestones) | Five milestones established; redundant overview issues deleted with user approval; [M1 breakdown](milestones/m1-foundation.md#work-sequence) created; tasks 1.1/1.2 complete; task 1.3 next. |
| SageMaker / JupyterLab | Obtain the organizer's temporary access link privately. | Existing Safari session verified 2026-10-31; GPU execution passed. See [setup evidence](setup.md). Keep the current session open; organizers can renew access as needed. Do not store access links here. |
| Bedrock / Strands | Provided SageMaker role; requirements in the project plan. | Required model response and one tool call verified 2026-10-31; quota lookup denied by role; organizer limits pending. See [setup evidence](setup.md). |
| GEO-Bench / Hugging Face | Selected tasks in the project plan. | GEO-Bench 1.1.0; four selected archives SHA-256 verified at pinned revision, train/valid inspection complete 2026-10-31. SageMaker `/home/sagemaker-user/GoTrain/data/geo-bench/`; test payloads sealed. See [data contracts/evidence](data.md). |
| Persistent data and artifacts | SageMaker `/home/sagemaker-user`; check artifacts in `gotrain-access-check/`. | Data inspection logs/previews at `/home/sagemaker-user/GoTrain/artifacts/data-inspection/`. Capacity/writes and browser-reload continuity verified 2026-10-31; restart/expiry persistence and S3 permissions unverified. See [setup evidence](setup.md). |

| Independent recovery copies | Backup custodian Mac: `/Users/hsen/Desktop/GoTrain-backups/`; `datasets/` for sealed ZIPs, `snapshots/` for timestamped recovery packages. | Implementation/initial transfers in progress; do not assume coverage until the verification record below is complete. See [backup/restore procedures](storage.md). No shared S3 destination configured. |

## Recovery verification

Initial cache and snapshot verification pending implementation.

Add a row only when useful. For a verified resource, record a stable safe link/path,
what was checked and when, and a link to the setup instructions or milestone
evidence. Keep credential values in private storage; record only the retrieval
method or environment variable name. Replace outdated references and explain
material location changes in the active milestone's decisions.
