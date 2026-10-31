# Working in GoTrain

Read [README.md](README.md), [the project plan](docs/PROJECT_PLAN.md), and
[the workflow](docs/WORKFLOW.md) before changing the project. Read the active
milestone document, when one exists, and its linked GitHub issues.

- Detail one milestone at a time. Use `docs/milestones/TEMPLATE.md`; do not
  prefill future milestones or create speculative code, dependencies, or folders.
  Name actionable issues `<milestone>.<task>: <action>` (such as `1.1`, `2.1`).
  Use milestones and their documents for outcomes; do not create overview issues.
  Refer to tasks by their current numbered titles in prose and link labels; keep
  GitHub numeric IDs only in link destinations and API arguments.
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
- Run checks appropriate to the change and report what was actually verified.
  All agent/training execution belongs on the provided SageMaker environment.

This file guides Codex's repository work; it is not the runtime agent's prompt.
