## Tests

`uv run tests/labels.py` runs the triage, scout, implement, review and fix jobs against a fake `gh` and checks the labels they leave. Run it after changing any of those workflows or `ticket.jq`, and add a scenario for each new label change. CI runs it on every PR.

`uv run tests/smoke.py` pushes to a factory PR in the sandbox and checks what real GitHub Actions do with each push. See `tests/smoke.md`. Run it after changing how review, fix or the push handler are triggered or queued, and add its report to `tests/smoke.md`. It spends model credit, so CI doesn't run it.

## Agent skills

### Issue tracker

Issues live in GitHub Issues on jonbaldie/software-factory. See `docs/agents/issue-tracker.md`.

### Triage labels

The five default triage labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
