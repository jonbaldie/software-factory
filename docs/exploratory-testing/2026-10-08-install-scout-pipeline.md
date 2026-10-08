# Exploratory pass: install, scout, and issue-to-PR pipeline (2026-10-08)

An unattended pass that used the factory the way a new user would. It tried three user goals through the supported interfaces: the `curl | bash` installer, the GitHub Actions workflows, and issue and PR labels.

## Setup

| | |
|---|---|
| Factory version | `install.sh` and templates from `v1` (`683a2e8`). `main` was `654c3f1`, three commits ahead (#34, #35, #36). |
| Scratch repo | New private `jonbaldie/sf-explore-2026-10-08`: a Node project with `npm test` (`node --test`) and no model key. Deleted after the pass. |
| Pipeline repo | `jonbaldie/software-factory-sandbox` (public), with `OPENROUTER_API_KEY`, the GitHub App, `FACTORY_TEST_COMMAND=npm test`, `FACTORY_MERGE` unset, and the default pi harness and model. |
| Evidence | [`2026-10-08-evidence/`](2026-10-08-evidence/). Links to the scratch repo no longer work, so its output was saved there. |

## Confirmed bugs

### 1. A TODO with no space after the colon gets filed again each time it moves: [#37](https://github.com/jonbaldie/software-factory/issues/37)

- **Impact:** duplicate tickets, each with its own triage run, which costs model credit and can lead to duplicate implementation PRs.
- **Start:** a repo with the factory installed and no issues for this TODO.
- **Replay:** commit `// TODO(factory):Validate the input type` at line 1 and run the scout. Then add a line above it and run the scout again.
- **Expected:** one issue titled `Validate the input type`. The README says the scout "checks existing issue titles to avoid duplicates".
- **Actual:** issue #5 `src/nospace.js:1:// TODO(factory):Validate the input type`, then issue #6 `src/nospace.js:2:// TODO(factory):Validate the input type`.
- **Evidence:** [`06-nospace-duplicate.txt`](2026-10-08-evidence/06-nospace-duplicate.txt). Cause: `title=${hit#*TODO(factory): }` needs a space after the colon.

### 2. Scout titles keep the `*/` or `-->` comment closer and a CRLF carriage return: [#38](https://github.com/jonbaldie/software-factory/issues/38)

- **Impact:** messy ticket titles. If the file is later converted to LF line endings, its CRLF TODO gets filed again.
- **Start:** a repo with the factory installed and no issues for these TODOs.
- **Replay:** commit `/* TODO(factory): Add a maxLength option to slug */`, a CRLF file containing `// TODO(factory): Support Windows line endings in slug`, and `<!-- TODO(factory): Add a page footer -->`. Then run the scout.
- **Expected:** titles containing only the comment text.
- **Actual:** `Add a maxLength option to slug */`, `Support Windows line endings in slug\r` (confirmed with `od -c`) and `Add a page footer -->`. Trailing spaces were also kept: `Handle empty titles in slug   `.
- **Repeats:** two scout runs: the block and CRLF cases in the first, the HTML case in the second.
- **Evidence:** [`03-scout1-issues.txt`](2026-10-08-evidence/03-scout1-issues.txt), [`07-html-todo.txt`](2026-10-08-evidence/07-html-todo.txt).

## Journeys

### A. Install the factory into a new repo: works

- **Goal:** workflows and prompts copied, labels created, test command set, and the missing key reported.
- **Ordinary path:** before `package.json` existed, the installer stopped cleanly with "couldn't detect how to run your tests" and changed nothing. With `package.json`, it added 13 files, created 11 labels, kept the existing `bug` and `enhancement` labels, set `FACTORY_TEST_COMMAND=npm test`, enabled Actions to approve PRs (`can_approve_pull_request_reviews: true`, checked through the API), and flagged the missing `OPENROUTER_API_KEY`. See [`01-install.txt`](2026-10-08-evidence/01-install.txt).
- **Variation:** a rerun with `--test-command 'npm test'` reported every file `unchanged` and left the variables as they were. See [`02-reinstall.txt`](2026-10-08-evidence/02-reinstall.txt).

### B. Turn `TODO(factory):` comments into triaged tickets: two bugs

- **Goal:** one `needs-triage` issue per TODO, triage started, no duplicates on later runs.
- **Ordinary path:** one run filed 4 issues and dispatched 4 triage runs. With no key, each triage failed with `No OpenRouter credential. Add an OPENROUTER_API_KEY repository secret.`, set `agent:failed`, and commented with a retry hint. See [`04-triage-nokey.txt`](2026-10-08-evidence/04-triage-nokey.txt).
- **Variations:**
  - A second scout run filed nothing new, including for the CRLF and trailing-space titles. See [`05-scout2-issues.txt`](2026-10-08-evidence/05-scout2-issues.txt).
  - Re-adding `needs-triage`, as the failure comment suggests, started triage again.
  - Moving a TODO with no space after the colon, and using block or HTML comments, produced bugs 1 and 2.

### C. Turn an issue into an approved PR: works

- **Goal:** a fully specified `needs-triage` issue from the owner becomes a PR that passes its tests and is approved, then waits for the human to merge it.
- **Ordinary path:** issue [sandbox#109](https://github.com/jonbaldie/software-factory-sandbox/issues/109) (`countLines`) went through [triage](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37824933302) (`enhancement` and `ready-for-agent`, with a brief), [implement](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37825018869), PR [sandbox#110](https://github.com/jonbaldie/software-factory-sandbox/pull/110) and [review](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37825464588), and was approved in about 5 minutes. On the PR head, `npm test` passed 136/136 when run separately. The issue's examples and further edge cases (`'\n'`, `'\r'`, `'a\r\rb'`, `'\n\n'`) gave the right counts. See [`11-pr110.txt`](2026-10-08-evidence/11-pr110.txt), [`11-pr110.diff`](2026-10-08-evidence/11-pr110.diff) and [`12-independent-check.txt`](2026-10-08-evidence/12-independent-check.txt).
- **Variation:** a human pushed a test commit to the approved PR. The push cleared the approval and set `agent:review`. The [re-review](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37825692369) asked for the PR description to cover the new test, using round 1 of 3. The [fix run](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37825932366) made no commit. It added the evidence to the description, and the next review approved. See [`13-rereview.txt`](2026-10-08-evidence/13-rereview.txt) and [`14-after-fix.txt`](2026-10-08-evidence/14-after-fix.txt).

## Unresolved and rejected candidates

- **Rejected:** a duplicate check that fails on CRLF titles or titles with trailing spaces. The second scout run matched both.
- **Unresolved, not replayed:**
  - The scout reads the file name up to the first `:` in the `git grep` output, so a file whose name contains `:` gets a broken source link.
  - The duplicate check reads only the newest 1000 issues. In a larger repo, a long-standing TODO whose issue has dropped out of that window, such as one closed as `wontfix`, could be filed again.

## Usability observations

- **Observation:** `install.sh` and `run-agent` come from `v1`, which is behind `main`. The scout fixes for duplicate titles in one run (#35) and capped report counts (#36) are merged but haven't reached users.
- **Observation:** a human commit on an approved PR can cost a fix round to update the agent's TDD "Slices" evidence, even though the code was approved.
  - **Suggestion:** have the reviewer accept human commits without slice evidence.
- **Observation:** the issue keeps `ready-for-agent` after its PR opens. This matches the docs, but the label doesn't show which issues are already in progress.

## Not explored

- The Claude Code harness.
- `FACTORY_MERGE=true` and conflicts.
- `needs-info` and `wontfix` triage results.
- Outside reporters.
- Taking work over by assigning someone.
- The scheduled (cron) trigger. Only `workflow_dispatch` was used.

## Interventions and cleanup

- **Interventions:** none to the product. Scout and triage runs were started by hand with `workflow_dispatch`. The pass spent model credit on 6 sandbox agent runs: triage, implement, three reviews and one fix.
- **Cleanup:**
  - Closed sandbox#110 without merging, deleted the `agent/issue-109` branch, and closed sandbox#109.
  - Deleted the scratch repo.
