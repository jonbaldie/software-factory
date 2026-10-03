## Tests

`uv run tests/labels.py` runs the review and fix jobs against a fake `gh` and checks the PR's labels. Run it after changing either workflow, and add a scenario for each new label change. CI runs it on every PR.

## Agent skills

### Issue tracker

Issues live in GitHub Issues on jonbaldie/software-factory. See `docs/agents/issue-tracker.md`.

### Triage labels

The five default triage labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
