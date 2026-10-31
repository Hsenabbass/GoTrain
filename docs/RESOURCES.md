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

| Independent recovery copies | Backup custodian Mac: `/Users/hsen/Desktop/GoTrain-backups/`; `datasets/` for sealed ZIPs, `snapshots/` for timestamped recovery packages. | Recovery snapshot and all four original dataset ZIPs independently stored and verified 2026-10-31. See the verification record below. See [backup/restore procedures](storage.md). No shared S3 destination configured. |

## Recovery verification

- **Snapshot:** `snapshots/20261031T131902980457Z-recovery.tar.gz`, 5,949,722 bytes,
  24 files; source commit `f124b41d58e0d3d8bb17d32566c794f99d064c1b`.
  Archive SHA-256: `5488ed4c1f3e57d87ccae92f9aa2e53a49c764f6e1dce04cfd83c459a1dfb2a4`.
  Sender/receiver checksum and every member's size/hash matched on 2026-10-31.
  Inspection `status.json` was restored into a temporary directory and its hash
  matched. This verifies file recovery, not model reload or environment recreation.
  Source, current inspection logs/manifests/previews and the inspection summary are
  included; credentials, live kernel state and raw datasets are excluded.
- **Local index:** `snapshots/index.json` records the snapshot checksum and source
  revision; its `.sha256` sidecar travels with the archive. SageMaker retains its
  staging copy under `artifacts/backups/`.
- **Dataset cache:** all four original ZIPs verified 2026-10-31: 3,409,938,495 bytes,
  pinned revision `1e5754337032f097396db62cc15a5ff88f4618e8`. Every complete-file
  SHA-256 matched the [versioned inspection record](data-inspection.json).
  `datasets/manifest.json` records paths, sizes and checksums; external `index.json`
  records its checksum and verification time. No partial files remain. ZIPs were
  copied as opaque bytes; no local sample inspection, extraction or training ran.
- **Coverage:** current inspection evidence has an independent local recovery copy.
  No model checkpoints exist yet. The source snapshot predates the later resumable
  cache enhancement; current source remains versioned in GitHub/local Git.
  The custodian's Mac is not itself backed up by this procedure.

Add a row only when useful. For a verified resource, record a stable safe link/path,
what was checked and when, and a link to the setup instructions or milestone
evidence. Keep credential values in private storage; record only the retrieval
method or environment variable name. Replace outdated references and explain
material location changes in the active milestone's decisions.
