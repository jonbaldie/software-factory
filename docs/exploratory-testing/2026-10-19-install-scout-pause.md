# Exploratory pass: install, scout, and issue pause (2026-10-19)

An unattended pass through three user journeys using the public installer, GitHub issue labels and assignment, and workflow dispatch. Two bugs were confirmed, replayed and filed after checking existing open and closed issues. Product fixes are left for subsequent tasks.

## Setup and evidence

- Factory: local `main`, `88c7a5c4eb3bd3d7eb7d2f0cb955351e9541e976`; installed directly with `bash /path/to/software-factory/install.sh`. The public `v1` tag was still `683a2e8752bc7b0f86f2a1e2176c48483dad17bc`; this pass tested `main`, not that release.
- Instance: new private `jonbaldie/sf-explore-2026-10-19`, now deleted. No existing sandbox settings or issues were changed.
- Configuration: minimal Node project with `scripts.test=node --test`; initially no lockfile or setup command. Later added a lockfile and configured custom commands. `FACTORY_MERGE` unset; no model key or GitHub App installed.
- Readiness: installer succeeded, installed 13 files, created its labels, enabled Actions PR permission, and saved `npm test`. It correctly reported the missing model key. GitHub Actions successfully ran all four scout dispatches and the pause/closed-issue checks.
- Instance commits: `599af70605c929630a87e219483f8350010905a0` initial fixture; `9d6df79abf8ad13565f97365d7dfdf4849a63786` added literal examples, uppercase docs and lockfile; `733a87f` added the independent literal replay.
- Evidence: [captured transcripts, issue snapshots and fixtures](2026-10-19-evidence/). Trailing whitespace was trimmed from captured Actions logs; their messages and timestamps were retained. Links in saved GitHub output point to the deleted instance; the local evidence is preserved here so reproduction does not depend on that repository.
- Duplicate check: all 33 existing issues returned by the open-and-closed query were reviewed before filing; [title inventory](2026-10-19-evidence/00-duplicate-check.txt). Related #38/#52 concern real comment closers; #62 concerns failed variable reads.

## Confirmed bugs

### Scout treats string literals as work requests: [#78](https://github.com/jonbaldie/software-factory/issues/78)

**Impact:** ordinary test data can create unsolicited tickets and dispatch model-backed triage. With normal model configuration, that can spend credit and lead to implementation of a change nobody requested.

**Starting conditions:** install the tested factory, then commit a passing JavaScript test containing a literal example:

```js
import assert from "node:assert/strict";
import test from "node:test";
test("documentation example remains literal data", () => {
  const example = "// TODO(factory): Render a documentation preview 20261019";
  assert.ok(example.startsWith("//"));
});
```

**Replay:** run `npm test`, dispatch **Factory 4 · Scout**, and inspect the issues and triage runs. The README promises tickets from code comments; this file contains literal data and no TODO comment.

**Actual:** the scout created `Render a documentation preview 20261019";`, linked the string assignment and instructed the implementer to delete the TODO comment. It dispatched triage. An assertion containing `example.includes("TODO(factory):")` also produced an issue titled `"));`.

**Repeat observations:** scout run `39313190731` filed three false tickets from two passing test files. Independent run `39313315550` filed one more from the smaller example above. The latter added only that one issue, leaving earlier tickets unduplicated. Both runs succeeded. Triage dispatch occurred; actual model work was blocked by the deliberately absent key.

**Evidence:** [first literal observations](2026-10-19-evidence/05-second-issues.json), [first scout log](2026-10-19-evidence/05-scout-second.log), [independent replay observations](2026-10-19-evidence/10-third-issues.json), [replay log](2026-10-19-evidence/10-scout-third.log), [minimal fixture](2026-10-19-evidence/fixtures/literal-replay.test.js), and [3/3 consuming-project tests passing](2026-10-19-evidence/07-fixture-tests.txt).

### Reinstall forgets an explicitly disabled setup command: [#79](https://github.com/jonbaldie/software-factory/issues/79)

**Impact:** upgrading can silently restore `npm ci` after the owner explicitly disabled setup. This matters when the default command fails or performs unwanted work in the runner.

**Starting conditions:** an installed Node project with `package-lock.json`, `FACTORY_TEST_COMMAND=node --test` and `FACTORY_SETUP_COMMAND=npm ci`.

**Replay:** from the consuming clone, run the installer with `--setup-command ''`. Check GitHub variables, then rerun the installer without arguments and check them again.

**Expected:** the help's `Pass '' to clear it` choice should survive a routine reinstall, just as a nonempty saved command does.

**Actual:** clearing succeeded and removed `FACTORY_SETUP_COMMAND`. The next successful reinstall detected the lockfile and restored `npm ci`. The explicit empty choice was lost. `FACTORY_TEST_COMMAND=node --test` remained intact and no variable read failed.

**Repeat observations:** 2/2 clear-and-reinstall sequences against real GitHub variables, starting each sequence with `npm ci` set. These sequences ran without overlapping variable writes. Earlier ordinary reinstall preserved the nonempty custom commands correctly.

**Evidence:** [first clear-and-reinstall sequence](2026-10-19-evidence/04-clear-setup.txt), [independent repeat](2026-10-19-evidence/09-clear-setup-replay.txt), and [successful ordinary upgrade](2026-10-19-evidence/02-upgrade.txt).

## Journeys exercised

### 1. Install, retain settings, then disable setup

Goal: install usable workflows and labels, retain saved commands during upgrade, and apply a corrected setup choice.

- Ordinary path passed: the install saved `npm test`, showed setup off, and flagged the missing key. [Install output](2026-10-19-evidence/01-install.txt).
- Nonempty configuration passed: explicit `node --test` and `npm ci` persisted through a plain reinstall. Installed workflow files stayed unchanged. [Upgrade output](2026-10-19-evidence/02-upgrade.txt).
- Correction variation found #79: empty setup applied immediately but was undone by the next plain install, twice.

### 2. Turn actual TODO comments into one ticket each

Goal: scout creates clean, source-linked tickets from comments, excludes documentation, and never refiles the same title on retry.

- First scout succeeded, creating four tickets for ordinary JS, JSX, MDX, and a path containing spaces, `#` and `%`. Repeating the same TODO in one source file created only one ticket. JSX closers and trailing markup were removed. [First issue snapshot](2026-10-19-evidence/03-first-issues.json), [log](2026-10-19-evidence/03-scout-first.log).
- Lowercase `.md`/`.markdown` and independently added `DOCS.MD`/`guide.MARKDOWN` were excluded. MDX was included as documented.
- The special filename became `src/my%20%23client%25.js#L1`; the authenticated contents API resolved that encoded path to the original file. This checked target resolution through the API, not rendered browser behavior. [Resolution evidence](2026-10-19-evidence/08-path-check.json).
- Adding passing marker-parser tests exposed #78; an independent new fixture replayed it.
- Final unchanged rerun succeeded and filed nothing. The issue count stayed nine, including the deliberately closed ordinary TODO ticket, so both open and closed title deduplication worked for this small queue. [Final log](2026-10-19-evidence/11-scout-rerun.log), [final nine issues](2026-10-19-evidence/11-final-issues.json).

### 3. Pause assigned work and avoid implementing a closed issue

Goal: assignment leaves work with its owner; dispatching implementation after closing an issue does not create work.

- Created an issue assigned to the owner with `needs-triage` and `ready-for-agent`. Both stages succeeded, posted their respective pause comments and retained both labels. Neither ran an agent. [Triage log](2026-10-19-evidence/06-assigned-triage.log), [implement log](2026-10-19-evidence/06-assigned-implement.log), [saved comments and labels](2026-10-19-evidence/03-first-issues.json).
- Variation: closed it, removed its assignee, then manually dispatched implement. The run succeeded, logged `Issue #1 is CLOSED; skipping implementation and leaving its labels alone`, skipped every agent step, and produced no branch or PR. [Closed-issue log](2026-10-19-evidence/06-closed-implement.log), [empty PR list](2026-10-19-evidence/11-final-prs.json).

## Candidate classification and limitations

- **Confirmed and filed:** #78 and #79 above.
- **Rejected with evidence:** earlier JSX-title, special-path and Markdown-exclusion failures did not recur on this build. Duplicate TODO text, unchanged reruns and a closed matching issue did not create duplicates. Assignment and closed implementation guards behaved as expected.
- **Expected prerequisite failure:** each of the eight scout-created issues dispatched triage, which failed because `OPENROUTER_API_KEY` was absent. This was not classified as a bug. [Representative diagnostic log](2026-10-19-evidence/06-no-key-triage.log).
- **Unresolved candidates:** none left from this pass. The previously filed >1000-issue deduplication limit (#76) was outside this instance's size.
- **Not exercised:** model-driven triage decisions, issue-to-PR implementation, review/fix, automatic merge, conflicts, Claude Code, outsider permissions and the released `v1` installation. Earlier reports and smoke tests cover some of these, but those results are not claimed as fresh evidence here.
- **Usability observation:** the installer clearly reports the missing key but still permits scout dispatch; scout can therefore succeed while every follow-on triage fails. Both statuses were inspected before classifying outcomes.
- **Environment note:** macOS initially collapsed same-base uppercase/lowercase filenames. Separate names (`DOCS.MD`, `guide.MARKDOWN`) were then committed to verify uppercase exclusions on the Linux Actions runner.

## Cleanup and publication

All 17 instance runs finished before cleanup: four successful scouts, two successful implementation guards, one successful assigned triage, eight expected no-key failures and two skipped label-event runs. No model call completed and no PR was created. The disposable repository and its nine fixture issues were deleted; its local clone was removed after preserving source fixtures and logs. The existing sandbox and pre-existing `.bugrun/` and `tests/__pycache__/` were left untouched. [Final run inventory](2026-10-19-evidence/11-final-runs.json), [cleanup record](2026-10-19-evidence/12-cleanup.txt).

Only this report, its evidence and a README pointer are being published. No product code was changed.

Publication validation: the label suite passed 130/130, and the pi and installer suites passed. Report links and recorded counts were checked, and the final staged diff was reviewed with no unresolved findings. [Validation record](2026-10-19-evidence/13-validation.txt).
