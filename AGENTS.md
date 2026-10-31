# Working in GoTrain

Read [README.md](README.md), [the project plan](docs/PROJECT_PLAN.md), and
[the workflow](docs/WORKFLOW.md) before changing the project. Read the active
milestone document, when one exists, and its linked GitHub issues.

- Be direct and efficient. Choose the simplest approach that satisfies the task;
  avoid speculative abstractions, extra services, redundant checks and excessive
  documentation. Time-box investigation, surface concrete blockers early, and stop
  when acceptance checks pass. Expand only when evidence justifies the extra work.
- Plan for fast delivery: use a few outcome-sized issues (normally 2–3), group
  complementary work, and include documentation/verification in those issues.
  Reuse verified work; do not repeat checks without a changed behavior or failure.
  Cut optional work before adding scope. Stop when the milestone outcome passes.
- Detail one milestone at a time. Use `docs/milestones/TEMPLATE.md`; do not
  prefill future milestones or create speculative code, dependencies, or folders.
  Name actionable issues `<milestone>.<task>: <action>` (such as `1.1`, `2.1`).
  Use milestones and their documents for outcomes; do not create overview issues.
  Refer to tasks by their current numbered titles in prose and link labels; keep
  GitHub numeric IDs only in link destinations and API arguments.
- Work directly on `main` per the user’s instruction; do not create new branches
  unless explicitly requested. Preserve concurrent teammate changes.
- Follow the workflow's source-of-truth table. Update affected documentation
  alongside code/configuration changes; link shared facts instead of copying them.
- Separate proposed, implemented, and verified work. Record checks and evidence;
  never imply cloud access or training results from local repository access.
- Keep a short handoff in the active milestone document: current state, blockers,
  and next action. Record material decisions there; use Git history for edits.
- Keep evaluation, test access, budgets, and experiment records outside editable
  experiment code. Preserve official splits; test each final pipeline once at the end.
- Keep secrets, datasets, and large artifacts out of Git. Follow the resource and
  storage conventions in `docs/WORKFLOW.md`.
- After valuable evidence or important completed runs, follow [storage and recovery](docs/storage.md): create a snapshot, transfer it outside SageMaker, verify checksums, and update the resource record. Never call a staging archive a completed backup.
- Run checks appropriate to the change and report what was actually verified.
  All agent/training execution belongs on the provided SageMaker environment.

This file guides Codex's repository work; it is not the runtime agent's prompt.
