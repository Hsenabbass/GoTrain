# Resource index

Reusable operational references live here. See the
[project plan](PROJECT_PLAN.md#tools-and-external-resources) for required tools,
model/region requirements, and research references. See the
[workflow](WORKFLOW.md#naming-resources-and-evidence) for credentials and storage rules.

| Resource | Stable reference or access route | Verification / details |
| --- | --- | --- |
| GitHub repository | [Hsenabbass/GoTrain](https://github.com/Hsenabbass/GoTrain) | Local clone push and GitHub issue read/write observed 2026-10-31; SageMaker clone and disposable-branch push verified 2026-10-31 using explicitly approved GoTrain-only access expiring 2026-11-01; other teammates' access unverified. See [setup evidence](setup.md). |
| Milestones and tasks | [Milestones](https://github.com/Hsenabbass/GoTrain/milestones); [milestone index](PROJECT_PLAN.md#five-milestones) | Five milestones established; redundant overview issues deleted with user approval; [M1 breakdown](milestones/m1-foundation.md#work-sequence) created; M1 and tasks 1.1–1.7 complete; [M2 complete](milestones/m2-engine.md): 2.1–2.2 verified; [M3 planned in three issues](milestones/m3-improvement.md). |
| SageMaker / JupyterLab | Obtain the organizer's temporary access link privately. | Existing Safari session verified 2026-10-31; GPU execution passed. See [setup evidence](setup.md). Keep the current session open; organizers can renew access as needed. Do not store access links here. |
| Bedrock / Strands | Provided SageMaker role; requirements in the project plan. | Required model response and one tool call verified 2026-10-31; M2 autonomous tool cycle verified; quota lookup denied by role; organizer limits pending. See [setup evidence](setup.md). |
| GEO-Bench / Hugging Face | Selected tasks in the project plan. | GEO-Bench 1.1.0; four selected archives SHA-256 verified at pinned revision, train/valid inspection complete 2026-10-31. SageMaker `/home/sagemaker-user/GoTrain/data/geo-bench/`; test payloads sealed. See [data contracts/evidence](data.md). |
| Persistent data and artifacts | SageMaker `/home/sagemaker-user`; check artifacts in `gotrain-access-check/`. | Data inspection logs/previews at `/home/sagemaker-user/GoTrain/artifacts/data-inspection/`. Capacity/writes and browser-reload continuity verified 2026-10-31; restart/expiry persistence and S3 permissions unverified. See [setup evidence](setup.md). |

| M1 contracts and capacity | [Task settings](../configs/tasks.json); [numeric caps](../configs/m1.json); [capacity record](setup.md#capacity-calibration-and-m1-budgets). | Four-task bounded GPU calibration passed; raw evidence in [calibration.json](calibration.json), full logs on SageMaker at `artifacts/calibration/`. No reference scores; the [manual foundation](training.md) now enforces these contracts. |
| Manual foundation | [Run guide](training.md); [verification report](m1-evidence.json); [direct dependencies](../requirements.txt). | 12 checks and two bounded smoke/reload jobs passed on SageMaker. Run paths are in the report; `artifacts/m1-budget.json` owns live usage/reservations. All four accepted [references](references.md) have full-validation and final fresh-process revalidation evidence in [M1 evidence: handoff](m1-evidence.json). |
| Independent recovery copies | Backup custodian Mac: `/Users/hsen/Desktop/GoTrain-backups/`; `datasets/` for sealed ZIPs, `snapshots/` for timestamped recovery packages. | Recovery snapshot and all four original dataset ZIPs independently stored and verified 2026-10-31. See the verification record below. See [backup/restore procedures](storage.md). No shared S3 destination configured. |

## Recovery verification

- **Task 2.2 snapshot:** `snapshots/20261031T155229195121Z-recovery.tar.gz`,
  171,941,539 bytes, 58 files; source `121cf8f46ca96a7e05d7620926ea665f55f69466`.
  Archive SHA-256: `9850720e796fd87a7fc9f46a30933026e70789992b680da5a7d36b574b0d51ca`.
  Sender/receiver and all member hashes matched 2026-10-31. Both new candidate
  `best.pt` files restored as opaque bytes and matched the accepted run hashes;
  archived cycle evidence matches [M2 evidence](m2-evidence.json). Includes both
  run records/logs/checkpoints, session decisions/usage, settled ledger and retained
  reference revalidation. The retained M1 model has its existing independent copy.
  ML execution/revalidation ran only on SageMaker.

- **Task 2.1 snapshot:** `snapshots/20261031T154026364499Z-recovery.tar.gz`,
  4,582,040 bytes, 44 files; source `747ac9fc238c91111b32c50dbe40e6e41f329159`.
  Archive SHA-256: `7d620478cdce946fb6549ab6730bea6f8aacb1b1fdb44c9ce546a5e506e26c39`.
  Sender/receiver and all member checksums matched 2026-10-31; restored
  `artifacts/runs/m2-tool-checks/checks.log` confirms 19 passing SageMaker checks.
  Includes controller source, configs and check log; no M2 training models existed at that snapshot.

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
- **Task 1.6 PV4GER-Seg snapshot:** `snapshots/20261031T145722937133Z-recovery.tar.gz`, 249,623,877 bytes, 47 files; source commit `2786dfc31b4faa00a90a1da0ac22729cf3afc995`. Archive SHA-256: `f9945c919b7f203f5db45ddf97c8142128a1ece37afb351ee1963036a6ad3241`. Sender/receiver and all member checksums matched 2026-10-31; selected `best.pt` including optimizer was restored as opaque bytes and matched its accepted run checksum. ML reload ran only on SageMaker.
- **Task 1.6 Chesapeake snapshot:** `snapshots/20261031T150754515230Z-recovery.tar.gz`, 249,788,696 bytes, 67 files; source commit `2786dfc31b4faa00a90a1da0ac22729cf3afc995`. Archive SHA-256: `2a6fbcad64b5e3f599b244e2cbd39d051c9dda684c4d220362ced0f731d92808`. Sender/receiver and all member checksums matched 2026-10-31; selected `best.pt` including optimizer was restored as opaque bytes and matched its accepted run checksum. ML reload ran only on SageMaker.
- The Chesapeake snapshot also contains final segmentation and 1.7 handoff/check logs, executed audit source, all four fresh-process revalidation results and a settled ledger.
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
  All four accepted model/optimizer checkpoints, run records and revalidation evidence have independent verified copies. Reproducible smoke weights remain excluded; their records are backed up. The initial snapshot predates the resumable cache enhancement; the task 1.3
  snapshot contains the updated source. Current source is also versioned in GitHub/local Git.
  The custodian's Mac is not itself backed up by this procedure.

Add a row only when useful. For a verified resource, record a stable safe link/path,
what was checked and when, and a link to the setup instructions or milestone
evidence. Keep credential values in private storage; record only the retrieval
method or environment variable name. Replace outdated references and explain
material location changes in the active milestone's decisions.
