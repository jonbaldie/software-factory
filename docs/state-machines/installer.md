# Installer machine (C)

`install.sh` is a rerun-safe, side-effect-ordered procedure; its implicit
machines are resolution chains. Every value is resolved **before** anything
is changed, so a missing required command fails cleanly.

## C1. Test-command resolution

| Priority | Source | Condition |
|---|---|---|
| 1 | `--test-command` | Explicit argument given. |
| 2 | `FACTORY_TEST_COMMAND` (existing variable) | Already set. |
| 3 | `npm test` | `package.json` has a `"test":` script. |
| 4 | error | Otherwise `die` (nothing changed yet). |

Reruns keep the current value (priority 2 wins over 3).

## C2. Setup-command resolution (three-state: set / unset / disabled)

| Priority | Source | Condition |
|---|---|---|
| 1 | `--setup-command` | Explicit argument given (`setup_given` distinguishes "cleared with ''" from "not given"). |
| 2 | `FACTORY_SETUP_COMMAND` (existing) | Already set. |
| 3 | `FACTORY_SETUP_DISABLED` marker value | Records an explicit clear across reruns (`install.sh:72, 91, 192-201`). |
| 4 | `npm ci` | `package-lock.json` exists. |
| 5 | none | If the variable was set but resolves empty, it is **deleted**. |

## C3. Source selection

| Condition | Action |
|---|---|
| `--ref` absent, local `template/` present | `template/` next to the script (`BASH_SOURCE`) — clone-like local source. |
| `--ref` absent, no local `template/` (the `curl \| bash` case) | Download the `v1` tarball — there is no local tree to copy. |
| `--ref` given | Download `jonbaldie/software-factory@<ref>` tarball to a temp dir (removed by an `EXIT` trap). |

Before any copying, the installer refuses symlinks in the target tree
(`install.sh:109-118`) — a factory file must never be written through one.

## C4. File install + report

`template/.github` files are copied in sorted order; each is reported as
`added` / `unchanged` (byte-compare) / `updated`, then copied.

## C5. Label provisioning

| Labels | Behaviour |
|---|---|
| 11 factory labels (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`, `agent:working`, `agent:review`, `agent:changes-requested`, `agent:approved`, `agent:failed`, `agent:wip`) | Force-created with a fixed colour/description table. |
| `bug`, `enhancement` | Created **only when missing** (case-insensitive) to preserve repo customisation. |

The 12-label force table is the label universe used by the validator
(`tests/state_machines.py`).

## C6. Permissions attempt

Read `can_approve_pull_request_reviews`; if false, PUT with the current
`default_workflow_permissions` plus the flag; any failure ⇒
`permissions_ok=false` and a manual step. Never fatal.

## C7. Secret check

Harness `claude` ⇒ needs `ANTHROPIC_API_KEY` **or**
`CLAUDE_CODE_OAUTH_TOKEN`; otherwise `OPENROUTER_API_KEY`. Reported, not
fixed.

## C8. Next-steps list

Built by an incrementing counter (secret → admin → commit → first label)
so it always reflects the failing preconditions, and everything runs from
`main()` because under `curl | bash` the script itself is still on stdin
(reading to EOF first is unsafe).
