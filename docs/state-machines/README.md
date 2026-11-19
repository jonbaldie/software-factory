# State machines — explicit specification

This directory makes explicit every implicit state machine in this repository
(the factory pipeline, the agent prompt methods, the installer, the test
mirrors, and the vendored skills). Each machine is specified once here as
states + transitions + guards, and once in [`machines.json`](machines.json)
in a checkable form. The CI job `State machine specs` (`tests/state_machines.py`)
fails if the spec drifts from the artefacts it describes: it checks the
label vocabulary, the cross-workflow dispatch sites, the head-validity guard
and the fix-round cap.

How to read a machine entry:

- **Storage** — where the state lives (labels, comments, branch, files).
- **States** — the declared state vocabulary.
- **Transitions** — `event → from → to`, with the guard that must hold.

Conventions: `*` = any state; `∅` = no clean exit; invariant = a property
true in every state. Where a guard lives in a workflow expression or a `bash`
`if`, the transition says so. This is a specification of existing behaviour,
not a redesign: changing behaviour means changing both the artefact and this
spec in the same PR, and extending the validator.

Index:

| Spec | Machines |
|---|---|
| [`factory-pipeline.md`](factory-pipeline.md) | A1–A16: the factory executable pipeline |
| [`prompt-methods.md`](prompt-methods.md) | B1–B5: agent prompt methods |
| [`installer.md`](installer.md) | C: `install.sh` |
| [`skills.md`](skills.md) | E1–E14: vendored skill processes |
| [`machines.json`](machines.json) | machine-readable index (also D1–D3 test mirrors, F exclusions) |
