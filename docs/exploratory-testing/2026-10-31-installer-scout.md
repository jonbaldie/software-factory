# Exploratory pass: installer and scout (2026-10-31)

The installer journey used the real `install.sh` with a simulated GitHub CLI. The scout was investigated with the project's local workflow driver, not dispatched on GitHub. The shared live sandbox was busy. This report does not claim a live end-to-end pass.

## Starting state

- Factory source: [`ecfd93c`](https://github.com/jonbaldie/software-factory/commit/ecfd93c7ad9e17cdd06bde5fedd381c73c59f432), checked out from `origin/main` in a separate worktree.
- Installer data: a fresh local Git repository with a minimal npm project and a lockfile. `npm ci --ignore-scripts` installed the locked, dependency-free fixture. A stateful fake `gh` recorded variables and labels without changing a GitHub repository.
- Scout data: fresh fixture repositories created by `tests/labels.py`. The driver ran the production workflow's shell steps and scout helper with a fake `gh`. URLs under `o/sandbox` in the logs are simulated and are not GitHub evidence.
- The sandbox had no open PRs or running jobs at the first read. Before dispatch, [two implementation runs](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/41155791343) and [41155789432](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/41155789432) were in progress. Later, [PR #150](https://github.com/jonbaldie/software-factory-sandbox/pull/150), [PR #151](https://github.com/jonbaldie/software-factory-sandbox/pull/151), and [a fix run](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/41156292781) were active. The exclusive-use preflight stopped the planned branch creation and dispatch. The cleanup trap's possible effect on a pre-existing branch is described below. The [preflight observations](2026-10-31-evidence/sandbox-preflight.txt) are transcribed from the session.

## Install and update the factory

Goal: install into a repository, preserve the setup choice across updates, and recover safely from an unsafe destination.

1. Installed into the fresh fixture. The installer exited 0, saved `npm test` and `npm ci`, and copied a workflow byte-for-byte from the tested template.
2. Disabled setup with `--setup-command ''`, then reinstalled. Both commands exited 0. The fake GitHub state retained `FACTORY_SETUP_DISABLED=true` and no setup command.
3. Re-enabled setup with `--setup-command 'npm ci'`, then reinstalled. Both commands exited 0. The fake state retained `FACTORY_SETUP_COMMAND=npm ci` and no disabled marker.
4. Replaced an installed prompt with a symlink to a shared file. The installer exited 1 without changing the shared file, another installed prompt, or the saved variables. Removing the symlink and retrying restored the template prompt.

The [replay script](2026-10-31-evidence/installer-journey.py) and [output](2026-10-31-evidence/installer-journey.log) contain the commands and state checks. They exercise the public installer, but the fake cannot validate GitHub permissions, network failures, or GitHub's persistence semantics. No installer bug was confirmed in this journey.

To replay both local drivers from the repository root, use Python with PyYAML, Node, npm, Git, and jq installed:

```sh
scratch=$(mktemp -d "$PWD/.explore-replay.XXXXXXXX")
trap 'rm -rf -- "$scratch"' EXIT
TMPDIR="$scratch" PYTHONDONTWRITEBYTECODE=1 python3 docs/exploratory-testing/2026-10-31-evidence/installer-journey.py
TMPDIR="$scratch" PYTHONDONTWRITEBYTECODE=1 python3 docs/exploratory-testing/2026-10-31-evidence/scout-diagnostic.py
```

## Scout comments into issues

Goal: create a work request for a real comment, while leaving JavaScript string data alone. The supported live workflow journey was blocked by the sandbox activity described above. No live scout run was started.

As a diagnostic, the [local driver](2026-10-31-evidence/scout-diagnostic.py) ran the production workflow steps twice from fresh repositories. In each run a real line comment created one issue, and a same-line string created none. A marker on a later line of a template literal created an issue titled `Literal data` and dispatched triage. The [recorded output](2026-10-31-evidence/scout-diagnostic.log) includes the generated issue body, the dispatch, and the control cases. This confirms the defect in the local workflow with simulated GitHub, but does not establish a live GitHub outcome.

[Issue #97](https://github.com/jonbaldie/software-factory/issues/97) records the impact and reproduction. Closed [#78](https://github.com/jonbaldie/software-factory/issues/78) addressed same-line strings, and the [earlier report](2026-10-25-scout-string-literals.md#limitations) already noted the multiline limitation. The issue search found no separate issue for that limitation. No product fix is included here.

## Other checks and limits

- [Installer regression suite](2026-10-31-evidence/installer-suite.log) passed. The [pi parser suite](2026-10-31-evidence/pi-suite.log) passed. The [workflow suite](2026-10-31-evidence/labels-suite.log) passed 164 scenarios. These use test doubles and are not live agent or Actions runs.
- The first workflow-suite invocation hit a three-minute command timeout. A separate rerun completed with 0 failures. The interrupted run is not counted as a pass.
- Issue-to-PR implementation, live triage, review, and fix were not exercised because the sandbox was in use. No model credentials or other shared settings were changed.
- The local installer emitted no confusing behavior in the paths tested. The scout's simulated issue body requests deletion of a comment that does not exist, which would mislead the recipient.

## Cleanup

The live driver registered a trap before any planned sandbox mutation and stopped at the exclusive-use preflight. Its cleanup would have deleted a pre-existing branch with the planned name, even though the driver had not created it. A fresh remote check showed that branch was absent, but the run did not check whether it existed before the trap. Whether the trap deleted a pre-existing branch is therefore unknown. The unsafe driver was discarded. The run created no sandbox resources. The local fixture clone, npm cache, test temporary files, and Python bytecode were removed before the report commit. No server, browser, container, image, or volume was started by this pass. The report and evidence remain in this directory.

The [decision trail](2026-10-31-evidence/decisions.tsv) was written retrospectively. Its timestamps record when each row was entered, not when the decision occurred.
