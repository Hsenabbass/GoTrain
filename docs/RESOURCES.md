# Resource index

Reusable operational references live here. See the
[project plan](PROJECT_PLAN.md#tools-and-external-resources) for required tools,
model/region requirements, and research references. See the
[workflow](WORKFLOW.md#naming-resources-and-evidence) for credentials and storage rules.

| Resource | Stable reference or access route | Verification / details |
| --- | --- | --- |
| GitHub repository | [Hsenabbass/GoTrain](https://github.com/Hsenabbass/GoTrain) | Local clone push and GitHub issue read/write observed 2026-10-31; SageMaker clone and disposable-branch push verified 2026-10-31 using explicitly approved GoTrain-only access expiring 2026-11-01; other teammates' access unverified. See [setup evidence](setup.md). |
| Milestones and tasks | [Milestones](https://github.com/Hsenabbass/GoTrain/milestones); [milestone index](PROJECT_PLAN.md#five-milestones) | Five milestones established; redundant overview issues deleted with user approval; [M1 breakdown](milestones/m1-foundation.md#work-sequence) created; tasks 1.1–1.5 complete; task 1.6 next. |
| SageMaker / JupyterLab | Obtain the organizer's temporary access link privately. | Existing Safari session verified 2026-10-31; GPU execution passed. See [setup evidence](setup.md). Keep the current session open; organizers can renew access as needed. Do not store access links here. |
| Bedrock / Strands | Provided SageMaker role; requirements in the project plan. | Required model response and one tool call verified 2026-10-31; quota lookup denied by role; organizer limits pending. See [setup evidence](setup.md). |
| GEO-Bench / Hugging Face | Selected tasks in the project plan. | GEO-Bench 1.1.0; four selected archives SHA-256 verified at pinned revision, train/valid inspection complete 2026-10-31. SageMaker `/home/sagemaker-user/GoTrain/data/geo-bench/`; test payloads sealed. See [data contracts/evidence](data.md). |
| Persistent data and artifacts | SageMaker `/home/sagemaker-user`; check artifacts in `gotrain-access-check/`. | Data inspection logs/previews at `/home/sagemaker-user/GoTrain/artifacts/data-inspection/`. Capacity/writes and browser-reload continuity verified 2026-10-31; restart/expiry persistence and S3 permissions unverified. See [setup evidence](setup.md). |

| M1 contracts and capacity | [Task settings](../configs/tasks.json); [numeric caps](../configs/m1.json); [capacity record](setup.md#capacity-calibration-and-m1-budgets). | Four-task bounded GPU calibration passed; raw evidence in [calibration.json](calibration.json), full logs on SageMaker at `artifacts/calibration/`. No reference scores; the [manual foundation](training.md) now enforces these contracts. |
| Manual foundation | [Run guide](training.md); [verification report](foundation.json); [direct dependencies](../requirements.txt). | 12 checks and two bounded smoke/reload jobs passed on SageMaker. Run paths are in the report; `artifacts/m1-budget.json` owns live usage/reservations. Two accepted [classification references](references.md) now have full-validation/revalidation evidence in [classification.json](classification.json). |
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
- **Task 1.3 snapshot:** `snapshots/20261031T135330089736Z-recovery.tar.gz`, 4,530,692 bytes,
  23 files; source commit `4aff5c8f96d280caef6691ebadf97e0f30398bc3`. Archive SHA-256:
  `f2d8f5f5074794efa47c02ac0881ffcb51698644132a01382fd19e48174ae50e`. Sender/receiver and all member checksums matched
  2026-10-31; the calibration report was restored into a temporary directory and
  its hash/completion flag matched. Includes current tracked source/contracts,
  full calibration log/report and the executed probe; no model checkpoint existed at that snapshot.
- **Task 1.4 snapshot:** `snapshots/20261031T141633806095Z-recovery.tar.gz`, 4,558,619 bytes,
  48 files; source commit `6acf45e424827d050f0163b50236f6c330f9f19e`. Archive SHA-256:
  `8425c4badb068fae4737bf26f1a2e9ed7755583cdf251e3948b910f4a5b3a274`. Sender/receiver and all member checksums matched
  2026-10-31; the foundation report was restored and hash-checked, and the ledger
  copy has no active reservation. Includes source, check logs, smoke run/reload/timing
  records and settled-ledger evidence. Reproducible random smoke weights remain on
  SageMaker and are deliberately excluded; no reference model existed at that snapshot.
- **Task 1.5 EuroSAT snapshot:** `snapshots/20261031T143326712207Z-recovery.tar.gz`, 88,251,680 bytes,
  43 files; frozen source commit `828cbf0d2a95df69ceae18e2883ce0c7fd9d3812`.
  Archive SHA-256: `07d2e0e782af2046f737b59bb0ef7c9a417c6c6d11b417e7da3f92514a3fa087`.
  Sender/receiver and every member checksum matched 2026-10-31; selected
  `best.pt` (including optimizer state) restored as opaque bytes and matched the
  accepted run checksum. Model reload/full validation ran only on SageMaker.
- **Task 1.5 Brick-Kiln snapshot:** `snapshots/20261031T144121071482Z-recovery.tar.gz`, 88,215,385 bytes,
  53 files; frozen source commit `828cbf0d2a95df69ceae18e2883ce0c7fd9d3812`.
  Archive SHA-256: `efe1f1557a6721ba46cc3102ecf24f933f3e73ca6ccdc570423729032f507f48`.
  Sender/receiver and every member checksum matched 2026-10-31; selected
  `best.pt` (including optimizer state) restored as opaque bytes and matched the
  accepted run checksum. Model reload/full validation ran only on SageMaker.
- **Local index:** `snapshots/index.json` records the snapshot checksum and source
  revision; its `.sha256` sidecar travels with the archive. SageMaker retains its
  staging copy under `artifacts/backups/`.
- **Dataset cache:** all four original ZIPs verified 2026-10-31: 3,409,938,495 bytes,
  pinned revision `1e5754337032f097396db62cc15a5ff88f4618e8`. Every complete-file
  SHA-256 matched the [versioned inspection record](data-inspection.json).
  `datasets/manifest.json` records paths, sizes and checksums; external `index.json`
  records its checksum and verification time. No partial files remain. ZIPs were
  copied as opaque bytes; no local sample inspection, extraction or training ran.
- **Coverage:** current inspection, calibration and foundation evidence have independent local recovery copies.
  Both accepted classification model/optimizer checkpoints, run records and revalidation evidence have independent verified copies. Reproducible smoke weights remain excluded; their records are backed up. The initial snapshot predates the resumable cache enhancement; the task 1.3
  snapshot contains the updated source. Current source is also versioned in GitHub/local Git.
  The custodian's Mac is not itself backed up by this procedure.

Add a row only when useful. For a verified resource, record a stable safe link/path,
what was checked and when, and a link to the setup instructions or milestone
evidence. Keep credential values in private storage; record only the retrieval
method or environment variable name. Replace outdated references and explain
material location changes in the active milestone's decisions.
