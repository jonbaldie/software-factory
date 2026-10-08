## Definition of Done

For implementation work, finish the job. Unless the user explicitly asks for a draft or an earlier stopping point, all of these must be true before you say "done":

- The requested behaviour works. The diff contains only changes needed for the task.
- The tests required below pass. Required live checks have run, and their results are recorded with evidence links.
- The final diff has been reviewed and the findings resolved.
- The PR is merged into the target branch. Required checks passed on the exact PR head that was merged. Verify the merge on GitHub.
- Any requested release or sandbox upgrade is complete and verified.
- Temporary test issues, PRs and branches are cleaned up. Fixtures needed for future tests are preserved.
- Local `main` is synced with `origin/main`. The task's changes are committed, and unrelated local work is preserved.

A pushed branch, an open PR or a handoff is unfinished work. If a required step is blocked, say what remains and why. The final reply must state what changed, what passed and the merged PR link.

## Tests

`uv run tests/labels.py` runs the triage, scout, implement, review and fix jobs against a fake `gh` and checks the labels they leave. Run it after changing any of those workflows or `ticket.jq`, and add a scenario for each new label change. CI runs it on every PR.

`uv run tests/pi.py` runs `run-agent/pi.mjs` against a fake `pi` and checks how it reads the agent's final JSON answer. Run it after changing `pi.mjs`. CI runs it on every PR.

`uv run tests/smoke.py` pushes to a factory PR in the sandbox and checks what real GitHub Actions do with each push. See `tests/smoke.md`. Run it after changing how review, fix or the push handler are triggered or queued, and add its report to `tests/smoke.md`. It spends model credit, so CI doesn't run it.

Exploratory test reports, with their evidence and filed issues, are in `docs/exploratory-testing/`. Read the latest one before changing the installer, the scout or the issue-to-PR pipeline.

## Agent skills

### Issue tracker

Issues live in GitHub Issues on jonbaldie/software-factory. See `docs/agents/issue-tracker.md`.

### Triage labels

The five default triage labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
