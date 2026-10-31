# Repository workflow

Keep the repository easy to enter: start at the [README](../README.md), then use
the [project plan](PROJECT_PLAN.md) for direction. This guide defines where work
belongs and how it stays consistent. Create folders and extra documents only
when they hold real work.

## Where things belong

| Location | Purpose |
| --- | --- |
| `README.md` | Short introduction, navigation, and truthful high-level status. |
| `docs/PROJECT_PLAN.md` | Shared goals, constraints, approach, and five milestone outcomes. |
| `docs/WORKFLOW.md` | Repository conventions and update rules. |
| `docs/RESOURCES.md` | Reusable operational links, access instructions, and data/artifact locations. |
| `docs/milestones/m<N>-<short-name>.md` | One milestone's detailed plan, evidence, decisions, and handoff. |
| `docs/milestones/TEMPLATE.md` | Reusable starting point for a milestone document. |
| `docs/setup.md`, `docs/architecture.md`, `docs/data.md` | Add when verified setup, shared interfaces, or dataset contracts need their own home. |
| `src/gotrain/` | Reusable application and ML code; group by responsibility as it develops. |
| `configs/` | Versioned, non-secret task recipes and run settings. |
| `scripts/` | Thin setup/run utilities that call reusable code. |
| `tests/` | Checks for meaningful behavior, especially splits, metrics, limits, and recovery. |
| `notebooks/` | Optional exploration; move reusable logic into `src/gotrain/`. Commit without sensitive or bulky outputs. |
| `data/` | Ignored local datasets and caches, or an external location documented in the resource index. |
| `artifacts/` | Ignored run records, logs, checkpoints, predictions, and exports, or verified external storage. |

The code, configuration, test, and runtime folders above are reserved conventions,
not implemented components. Add package/dependency metadata when implementation
begins; pin verified versions then. Add UI or other top-level folders only when
their scope is known. Do not create empty directory trees or duplicate utilities
per milestone. Promote shared logic to `src/gotrain/` when reuse is demonstrated.

## One home for each fact

| Information | Authoritative home | Update rule |
| --- | --- | --- |
| Hackathon requirements | Original challenge PDF | Keep the source intact; record organizer clarifications with date and source in the relevant milestone. |
| Agreed project direction and milestone boundaries | `PROJECT_PLAN.md` | Revise when an agreed decision changes scope or constraints; link detailed plans. |
| Detailed milestone scope, sequence, decisions, evidence | Milestone document | Keep current during work; link implementation issues and durable shared docs. |
| Task state, discussion, acceptance, milestone completion | GitHub issues and milestones | Use milestone documents for broad outcomes and acceptance evidence; numbered implementation issues for individual tasks. Close with evidence. |
| Working setup, interfaces, data contracts | Focused shared docs, once created | Update in the same change as behavior; move reusable instructions out of milestone notes and leave links. |
| Reusable operational references and storage locations | `RESOURCES.md` | Update when a location or verification state changes; keep research references in the project plan. |
| Exact run settings and measurements | Versioned configs and durable run records | Link records from milestone evidence; do not hand-maintain duplicate score tables across docs. |

README status is a summary. A milestone's handoff is a brief working snapshot,
not a second task checklist. When sources disagree, resolve against the brief,
agreed decisions, and verification evidence; update affected summaries together.
Preserve uncertainty explicitly instead of silently choosing a convenient value.

## The milestone cycle

1. **Plan:** read the preceding milestone's evidence and current constraints.
   Copy the template to `m<N>-<short-name>.md`, link it from the project plan,
   and detail only this milestone. Resolve or label unknowns. When authorized to
   track work on GitHub, create small issues with prerequisites, tools/data,
   completion checks, and links to the plan; assign them to the existing milestone.
   Title tasks `<milestone>.<task>: <action>`: `1.1`, `1.2`, then `2.1`, `2.2`,
   and so on. Keep assigned task numbers stable; append the next number for new
   work. GitHub `#` numbers remain link identifiers. Do not create overview issues.
2. **Implement:** work in small changes tied to an issue. Use `codex/<short-name>`
   branches by default. Put reusable code and configuration in the shared folders.
   Update affected instructions and contracts alongside behavior. Record material
   decisions with their reason and any decision they replace.
3. **Verify:** run the relevant checks in the required environment. Record the
   command/check, environment, outcome, and evidence location. Distinguish a local
   check from a SageMaker/GPU/Bedrock check. An unchecked result stays unverified.
4. **Handoff:** update the milestone's short current-state/blocker/next-action
   section before ending substantial work. Update GitHub issue state when connected
   and authorized; if synchronization is pending, say exactly what remains to sync.
5. **Complete:** check each outcome against evidence in the milestone document,
   close the completed task issues and milestone, and promote lasting instructions into shared docs. Update README
   status and the project plan where needed. Keep the milestone document as the
   completion record, then plan the next milestone.

For a later modification, reopen or create a focused issue, change the authoritative
document/code/config, verify it, and update affected links and summaries. Record
scope changes and superseded decisions; preserve original experiment evidence.
Use Git history for ordinary edits rather than maintaining a second changelog.
Update this guide and `AGENTS.md` together if repository conventions change.

Before finishing a change, check: **behavior and docs agree; links resolve; claims
have evidence; the handoff is current; no secrets or large runtime files are staged.**
No generator, documentation service, or extra tracking database is needed.

## Naming, resources, and evidence

- Use lowercase descriptive names: `m1-foundation.md`, `data-inspection.md`,
  `inspect_data.py`. Python modules use `snake_case`; keep existing entry documents.
- Use relative repository links in docs and stable GitHub issue URLs. Store a shared
  fact once and link it. Use ISO dates (`YYYY-MM-DD`) for decisions and verification.
- Record safe model IDs, regions, dataset versions, and paths in their relevant
  config or contract. The resource index points there instead of repeating values.
- Never store keys, tokens, passwords, signed URLs, or temporary JupyterLab access
  links in tracked documents, issues, notebooks, or configs. Use the provided IAM
  role or private environment/credential storage. If needed, `.env.example` contains
  variable names and placeholders only; document how to obtain access, not secrets.
- Keep downloaded data under an ignored `data/` location or verified external
  storage. Record source/version, official splits, channel/label mappings, and
  preprocessing rules in `docs/data.md` when verified. Do not inspect test samples
  during development. A folder convention does not enforce test protection.
- Use one unique run ID, such as `<UTC timestamp>-<task>-<short-label>`, for each
  `artifacts/runs/<run-id>/` directory. Retain the hypothesis, parent run, code revision
  (and patch if dirty), config, data version, seed, split/metric definition, runtime,
  resource use, failures, logs, and checkpoint location. Define the concrete record
  format when runs are implemented. Keep evaluation records protected from the
  experiment code that they evaluate.
- Commit small sanitized evidence summaries when useful; keep full records and
  model files in persistent storage. Link the run ID and durable path from the
  milestone. Verify persistence before trusting it; ignored local files are not a
  backup. Model packages should reference their originating run and version.
