# Storage, recovery and team access

Approved 2026-10-31. Keep source in Git, working data on SageMaker, and independent
recovery copies outside the repository. This guide owns backup/restore procedures;
[data contracts](data.md) own dataset versions and split rules;
[resources](RESOURCES.md) own the actual locations and latest verification status.

## What goes where

| Material | Working home | Recovery copy |
| --- | --- | --- |
| Code, configs, docs, small sanitized evidence | GitHub and each teammate's clone | Tracked source is also included in recovery snapshots. |
| Original dataset ZIPs | SageMaker `data/geo-bench/archives/` | One checksum-verified local cache of the four unchanged ZIPs. |
| Extracted train/valid samples | SageMaker `data/geo-bench/datasets/` | Rebuild from original archives; no duplicate extracted-data backup. |
| Inspection evidence and completed run outputs | SageMaker `artifacts/data-inspection/` and `artifacts/runs/<run-id>/` | Timestamped snapshots transferred to the backup custodian's machine. |
| Useful notebooks | Saved under `notebooks/saved/` | Commit clean source without outputs; include reviewed saved notebooks in snapshots if needed. |
| Credentials, temporary access links and live console history | Private environment only | Excluded; obtain fresh authorized access after a loss. |

A live console is scratch work, not a durable notebook. Put reusable operations in
scripts and save useful notebooks before backing them up. Snapshots contain files,
not kernel memory, installed environments or AWS permissions. All agent/training
execution remains on the provided SageMaker environment. Local caching and backup
verification only copy/hash files; they do not run training or inspect samples.

## Teammates: obtaining code and data

1. Clone the repository using your own GitHub access; work on a separate branch.
2. Obtain organizer-approved SageMaker access privately. Reuse the existing verified
   data if working in the same environment. Do not circulate another user's token
   or assume GitHub access grants AWS access.
3. On a fresh approved environment, follow [setup](setup.md), then the exact
   [download and inspection commands](data.md#storage-and-reproducible-inspection).
   The script allowlists four archives, pins the source revision and verifies
   their SHA-256 values. No teammate needs a dataset download on their laptop.
4. Preserve the published partitions and labels. Test payloads stay inside the ZIPs;
   do not unzip archives manually. Fit preprocessing on training only.
5. Share source through Git; refer to run IDs and storage paths for large outputs.
   Use separate run directories and initially schedule GPU jobs sequentially.
   Coordinate Git updates; do not change branches in another teammate's active
   working checkout. Separate clones can share the verified dataset read-only.

## Creating a recovery snapshot

Use the standard-library [backup utility](../scripts/backup.py). Commit source
first, stop writers to the selected completed outputs, and review included files
for private information. By default it includes tracked source plus inspection
evidence; select completed runs explicitly rather than recursively copying home
or the entire artifacts directory.

On SageMaker, from the repository root:

```bash
timeout 900 python scripts/backup.py create
# Later, add only the completed run(s) or saved notebook(s) required:
timeout 900 python scripts/backup.py create \
  --include artifacts/data-inspection --include artifacts/runs/<run-id>
python scripts/backup.py verify artifacts/backups/<UTC>-recovery.tar.gz
```

The utility refuses dirty tracked source, private/hidden paths except `.gitignore`/`.gitattributes`,
symlinks and paths outside the repo. It screens text for common credentials/access
URLs; this is a guard, not a substitute for reviewing logs and notebook outputs.
It reserves 5 GiB of free disk, records the Git commit and every file's size/SHA-256,
then verifies the archive before finalizing it. The manifest is inside the package;
a separate `.sha256` file records its complete archive checksum. Partial outputs
are not backups. Nothing is automatically pruned or overwritten.

Download the completed `.tar.gz` through JupyterLab's file browser (right-click →
Download). Copy the archive checksum from the creation result or download its
`.sha256` sidecar. Move both to the external snapshot location in the resource
index. On the receiving machine:

```bash
python3 /path/to/GoTrain/scripts/backup.py verify /path/to/<UTC>-recovery.tar.gz
```

Confirm both the per-file verification and the complete archive SHA-256 against
the sender's value. Only then record the snapshot as independently backed up.
The SageMaker `artifacts/backups/` directory is a staging area, not an independent
backup. Keep the local cache/snapshots private; share reviewed copies with teammates
through an agreed private channel when needed. No shared cloud backup is configured.

## One-time local dataset cache

Run on the backup custodian's Mac, using any Python 3.9+ with the standard library:

```bash
python3 scripts/backup.py cache-data \
  --destination /Users/hsen/Desktop/GoTrain-backups/datasets
```

This retrieves the exact four public archives named by the committed inspection
record and verifies their recorded SHA-256 values. It copies opaque bytes without
opening ZIP contents, inspecting test samples or installing ML dependencies. It
reuses matching files, writes a cache manifest, reserves 5 GiB and caps transfer at
900 seconds with a 30-second network read timeout. Checksum failures stop the copy.
Other custodians can choose their own external directory; do not put it inside Git.

## Restore after session or environment loss

1. Obtain fresh organizer-approved SageMaker access and your own GitHub credentials.
   Clone the repository; use the snapshot's Git revision when reproducing an old run.
2. Verify the snapshot and its sender-provided checksum before extracting. On a
   supported SageMaker Python, extract to a **new empty recovery directory**:

   ```bash
   python scripts/backup.py verify /path/to/<UTC>-recovery.tar.gz
   python -m tarfile -e /path/to/<UTC>-recovery.tar.gz /path/to/empty-recovery
   ```

   The verifier rejects traversal, duplicate names and non-regular archive members.
   `payload/` contains repository-relative files; `manifest.json` identifies the
   source commit. Copy reviewed artifacts into the new checkout without overwriting
   newer runs. If GitHub is unavailable, `payload/` also holds the tracked source
   snapshot (without Git history).
3. Recreate the verified environment from [setup](setup.md); the original environment
   inherits package conflicts, and task 1.4 still owns the application dependency set.
4. Copy the cached ZIPs to the matching `data/geo-bench/archives/<benchmark>/` paths,
   or retrieve them from the pinned public source using the data instructions.
   Run the documented download/inspection stages: metadata and checksums are
   verified and only train/valid samples are extracted. Never extract test payloads.
5. Verify run/config/data references before resuming. Do not restart training simply
   to validate a backup; initially check files and restore a small artifact in a
   temporary directory. Checkpoint reload/prediction is verified when models exist.

## Update rule

Create and transfer a snapshot after a completed milestone task that generates
valuable untracked evidence, after each important completed training run, and
before a planned environment change. Refresh the dataset cache only if an approved
source revision changes; preserve old caches needed by recorded runs. Keep the
snapshot Git revision, filename, checksum and verification result in the resource
record. Codex performs this during active work; there is no background scheduler
or guarantee of capturing an unexpected expiry mid-run. Do not delete older copies
until a newer verified copy is safely stored and retention is agreed.

The backup custodian's Mac is the current independent recovery location. This is
not protection against loss of that Mac; a second shared destination can be added
when available. S3 permissions and expiry/restart persistence remain unverified.
