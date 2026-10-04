# Database pilot

This trial installs software-factory v1.8.5 in
[`jonbaldie/database`](https://github.com/jonbaldie/database), a Go database
server with an existing CI pipeline and a separate local agent fleet.
The trial is limited to one real bug:
[#498](https://github.com/jonbaldie/database/issues/498), where `database init`
prints a JSON error by default and shows obsolete usage text.

The factory completed the trial and automatically merged
[PR #514](https://github.com/jonbaldie/database/pull/514) after two fix rounds.
Independent CLI checks passed. The trial also exposed an existing mutation
gate defect that must be fixed before a wider rollout; see the follow-up below.

## Installation

The installation is merged in
[database PR #513](https://github.com/jonbaldie/database/pull/513).
Its head was `9a7b155b241f277304ff8355d85821f2ee9016b1`; the merge commit is
`aa9b21cb8029c8752e4bfda32dd9f68aa287b0df`.

The installer used `--ref v1.8.5`, `--test-command 'make quality'`, and
`--setup-command 'go mod download'`. The installed workflows have these
repository-specific changes:

- Install the Go version from `go.mod` in implement, review, and fix jobs.
- Pin the shared agent action to `v1.8.5`.
- Use merge commits, which are the only merge method allowed by the
  repository's ruleset.
- Give the reviewer up to 15 minutes to wait for CI, within a 30-minute job.
- Restrict triage and implement jobs to `FACTORY_PILOT_ISSUE=498`, including
  manual starts. Omit the scheduled scout during the trial.

The local fleet queue excludes issues with `factory:pilot` from both its REST
query results and GraphQL fallback results. Thus the factory can add
`ready-for-agent` without giving the same issue to the fleet.

The `quality` job was running in CI but was not a required merge check. It is
now required, along with `govulncheck` and `Enforce A+ grade`. The job runs race
tests, the build, static checks, a vulnerability scan, and the changed-code
mutation threshold. No existing check was removed or weakened.

The publishing App has Contents and Pull requests write permissions. Adding
the repository to its installation required the owner's fresh GitHub sign-in
confirmation. `FACTORY_MERGE=true` enables automatic merging after review and
the required checks. Per-run model budget caps remain the upstream defaults.

## Setup evidence

- Local `GOMAXPROCS=2 GOFLAGS=-p=2 make quality`: passed.
- Upstream `uv run tests/labels.py`: 89 scenarios passed.
- The same harness against the installed workflows: 97 scenarios passed.
  The harness was given a `format` expression function and a pilot variable
  for its existing fixture issue. Eight added scenarios checked that both
  issue workflows skip another issue or an empty pilot variable, for label
  events and manual starts. The harness copy was temporary; it did not change
  the upstream test suite.
- Fixture checks confirmed that both fleet queue paths exclude the pilot and
  keep a normal ready issue. The live queue also excluded #498.
- The installation's exact PR head passed
  [quality](https://github.com/jonbaldie/database/actions/runs/37192910037),
  [security](https://github.com/jonbaldie/database/actions/runs/37192910017), and
  [Go Report Card](https://github.com/jonbaldie/database/actions/runs/37192910019).
- Real manual requests for issue #1 skipped all job steps:
  [triage](https://github.com/jonbaldie/database/actions/runs/37193090989) and
  [implement](https://github.com/jonbaldie/database/actions/runs/37193092408).

## Product baseline

At database commit `80f7e9775c69b9a750a7456e1ed8d88d48ab2561`, a real binary
was run against a fresh temporary path with no password option:

```sh
bin/database init --data-directory=<fresh-path> --initial-account admin
```

The command exited 2, created no data directory, and wrote a
`database.operator.result/v1` JSON object to stdout. Its diagnostic was:

```text
usage: database init DIRECTORY (--password-file FILE | --password-stdin) [--format=human|json]
```

The same command with `--result=human` used text output, but kept the same
usage text. `--result=json` retained the JSON envelope and exit code 2.

## Live result

After the owner added `database` to the App installation, a short-lived token
restricted to this repository confirmed access. Adding `needs-triage` to #498
started the trial on 4 October 2026 at 10:32 UTC.

| Stage | Run | Result | Reported model cost |
| --- | --- | --- | --- |
| Triage | [37195673210](https://github.com/jonbaldie/database/actions/runs/37195673210) | Passed; 5 turns | $0.0070 |
| Implement | [37195751862](https://github.com/jonbaldie/database/actions/runs/37195751862) | Passed; 30 turns | $0.0368 |
| Review 1 | [37196183361](https://github.com/jonbaldie/database/actions/runs/37196183361) | Requested cleanup evidence in the description; 7 turns | $0.0109 |
| Fix 1 | [37196415803](https://github.com/jonbaldie/database/actions/runs/37196415803) | Added the missing description evidence without a commit; 12 turns | $0.0121 |
| Review 2 | [37196686700](https://github.com/jonbaldie/database/actions/runs/37196686700) | Requested that the docs describe the existing default account; 9 turns | $0.0133 |
| Fix 2 | [37196962746](https://github.com/jonbaldie/database/actions/runs/37196962746) | Corrected the documentation; 8 turns | $0.0045 |
| Review 3 | [37197142934](https://github.com/jonbaldie/database/actions/runs/37197142934) | Approved and merged; 6 turns | $0.0109 |

The seven agent runs reported a total model cost of **$0.0955**, excluding
GitHub Actions and the independent operator's work. From the first triage
start to merge, the trial took **30 minutes 48 seconds**. After setup, the
factory needed no operator edits, manual workflow retries, or manual merge.

The App opened [database PR #514](https://github.com/jonbaldie/database/pull/514)
at 10:41 UTC with head `5f8aaa6d51acc3a2ad6b82d319169f0619911148`.
The change removes the forced JSON format from initialization failures,
updates the usage text, and adds regression coverage. The first commit changed
only the initialization command and its policy tests: 75 added lines and
9 removed lines.

An independent review of that diff found no change outside the issue's scope.
The first factory review accepted the code and tests, but asked the fixer to
record the debug-marker search and removal of temporary files in the PR
description. The fixer supplied that evidence without changing the code or
creating a commit. Two debug-marker matches were instructions in the factory
prompt; none appeared outside `.github`.

The second reviewer accepted the code and tests, then found that the operator
documentation calls `--initial-account` required while the CLI defaults it to
`admin`. The second fix corrected the table heading and the account option's
description. It changed only documentation. The final diff has three files,
77 added lines and 11 removed lines, at
`4acf43ef6415b4ce2ddfb74c5cddf6852c19e388`.

The fix transcript confirms one failed `make quality` run:
`TestMySQLLocksResourcesCancellationAndExplanationKeepWireContract` failed at
`test/blackbox/statement_policy_test.go:370` with `lock_ms=0`. Its second run
passed without a source change.
That retry is recorded in the PR description and fix transcript; the trial
was not a run with no test failures.

All required checks passed on the final head:
[quality](https://github.com/jonbaldie/database/actions/runs/37197143303),
[govulncheck](https://github.com/jonbaldie/database/actions/runs/37197143316), and
[Go Report Card](https://github.com/jonbaldie/database/actions/runs/37197143340).
The quality job's mutation result has the limitation described below.

The final approval named that same commit. GitHub confirms that
`github-actions[bot]` merged it at **11:02:55 UTC** as
`8ba5c81c5eb85fc59b975cc1468c0e7b4cd5a039`; the merge's second parent is the
reviewed head. Issue #498 closed at 11:02:57 UTC. Local database `main` was
fast-forwarded to the merge, preserving the pre-existing `report.json`.

### Independent CLI replay

Both PR heads were built locally with `GOMAXPROCS=2 GOFLAGS=-p=2 make build`,
and the same eight cases passed on each. The final replay used
`4acf43ef6415b4ce2ddfb74c5cddf6852c19e388`.
The real binary ran this command in fresh temporary working directories:

```sh
database init --data-directory=x --initial-account admin
```

Stdout now contains human text. This sample is from the first replay:

```text
init: invalid_input (operation_id=op-54345438647f5ab6372269e23acaa0e4)
```

Stderr contains:

```text
init [invalid_input]: usage: database init --data-directory PATH [--initial-account NAME] (--initial-password-file PATH | --initial-password-stdin) [--result=human|json]
```

All eight cases passed:

| Case | Result |
| --- | --- |
| Missing password, default output; absent and existing targets | Human stdout and diagnostic stderr; exit 2 |
| Missing password, `--result=human`; absent and existing targets | Human stdout and diagnostic stderr; exit 2 |
| Missing password, `--result=json`; absent and existing targets | Valid `database.operator.result/v1` envelope, `invalid_input`, exit 2; empty stderr |
| Canonical directory/account/password-file options with JSON output | Success envelope, exit 0, metadata and catalog created |
| Positional directory and legacy `--password-stdin` alias | Original human success text, exit 0, metadata and catalog created |

All six failure cases left the target unchanged. Missing targets stayed absent;
existing targets retained their only file with the same SHA-256 digest. Each
case used an owned temporary directory, and all those directories were removed.

The new `TestInitializeMissingPasswordUsesRequestedResultFormat` regression
was also run against the pre-fix production file from `aa9b21c`: it failed.
Restoring the production file from the first PR head made it pass. The
temporary substitution was removed, and the verification checkout was clean.

The checkout's `verify-database` skill was missing. The implementation recorded
that limit and used an isolated CLI replay. The independent replay also used
the actual CLI; this initialization error needs no running server.

## Follow-up before wider rollout

The pilot exposed an existing defect in the consumer's mutation check,
recorded as [database #515](https://github.com/jonbaldie/database/issues/515).
Its custom executor is `--exec='go test ./...'`. The mutation tool requires
that executor to apply each mutant and translate the test result into its own
exit-code contract. This command does neither: it tests unchanged source and
counts a successful test run as a killed mutant.

A separate disposable module with one function and no tests confirmed this:

```go
func IsPositive(n int) bool { return n > 0 }
```

| Executor | Reported score |
| --- | --- |
| Repository command: `--exec='go test ./...'` | 1.000000; 3 killed, 0 surviving |
| Tool's built-in executor | 0.000000; 0 killed, 3 surviving |

The module used Go 1.26.6 and the same pinned mutation-tool version as CI.
It was removed after the comparison. Thus CI's reported score of 1.00 for
#514 is not evidence that the tests killed those mutants. The real CLI replay,
regression failure/pass comparison, race tests, and other quality checks
provide separate evidence for this fix.

Keep the pilot restricted to #498. Correct and verify the mutation executor
before expanding unattended work. No factory source workflow changed during
this trial, so the sandbox push/queue smoke suite was not rerun.
