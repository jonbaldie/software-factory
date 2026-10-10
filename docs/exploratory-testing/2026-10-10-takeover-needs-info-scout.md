# Exploratory pass: takeover, needs-info, and the scout on `main` (2026-10-10)

An unattended pass on areas the [2026-10-08 pass](2026-10-08-install-scout-pipeline.md) left unexplored. It covered three user goals, using issue labels, assignment, comments, the `Factory 4 · Scout` workflow and the installer.

## Setup

| | |
|---|---|
| Factory version | `main` at `5d5409a`. `v1` is still `683a2e8`, 10 commits behind. |
| Pipeline repo | `jonbaldie/software-factory-sandbox`, with the default pi harness and model, `OPENROUTER_API_KEY`, the GitHub App, `FACTORY_TEST_COMMAND=npm test` and `FACTORY_MERGE` unset. Its `factory-triage.yml`, `factory-review.yml`, `factory-fix.yml` and prompts match `main`. Its `factory-implement.yml` and `factory-scout.yml` are older. |
| Scratch repo | New private `jonbaldie/sf-explore-2026-10-10`: a Node project with `npm test` and no model key. The factory was installed with `curl …/main/install.sh \| bash -s -- --ref main`. Deleted after the pass. |
| Evidence | [`2026-10-10-evidence/`](2026-10-10-evidence/). The scratch repo no longer exists, so its output was saved there. |

## Confirmed bugs

### 1. Re-triaging a paused `ready-for-agent` issue never starts implementation: [#50](https://github.com/jonbaldie/software-factory/issues/50)

- **Impact:** after a human hands an issue back, it shows a fresh brief and `ready-for-agent`, but nothing runs and nothing says so. The work stalls silently.
- **Start:** the sandbox, and a fully specified issue from the owner for a helper that doesn't exist.
- **Replay:** open the issue assigned to yourself, then add `ready-for-agent`. Implement posts ⏸️. Unassign yourself, then add `needs-triage`.
- **Expected:** the README says "A `ready-for-agent` triage starts implementation straight away". The ⏸️ comment says unassigning and re-adding `needs-triage` hands the issue back.
- **Actual:** triage set `enhancement,ready-for-agent` and posted a brief, but dispatched no implement run. Its log shows `IMPLEMENTING: true`. "Clear an earlier failure" treats an existing `ready-for-agent` without `agent:failed` as "the implementer has the ticket already". After 3 minutes there was no run, branch or PR.
- **Repeats:** 2/2. sandbox#113 followed both ⏸️ comments exactly. sandbox#114 was the minimal replay.
- **Workaround:** remove and re-add `ready-for-agent`. This started implement run 38018319078, which was cancelled once the agent began.
- **Evidence:** [`02-handback-no-implement.txt`](2026-10-10-evidence/02-handback-no-implement.txt).

### 2. Scout ticket links break when the file name contains a space: [#51](https://github.com/jonbaldie/software-factory/issues/51)

- **Impact:** the ticket's source link opens a 404. #42 fixed the same problem for colons.
- **Start:** the scratch repo with the factory from `main`.
- **Replay:** commit `src/j my file.js` containing `// TODO(factory): Handle spaces in file names` and run the scout.
- **Expected:** a link to `.../blob/<sha>/src/j%20my%20file.js#L1`.
- **Actual:** GitHub renders `<a href=".../blob/<sha>/src/j">` followed by ` my file.js#L1` as text. Through the authenticated contents API, `src/j` is 404 and `src/j%20my%20file.js` resolves.
- **Repeats:** 2/2 scout runs. The second used `src/l upload client.js`.
- **Evidence:** [`04-scout-main.txt`](2026-10-10-evidence/04-scout-main.txt).

### 3. Scout titles keep the closer and trailing code of a mid-line block comment, such as JSX: [#52](https://github.com/jonbaldie/software-factory/issues/52)

- **Impact:** messy titles in React projects, where `{/* … */}` is the only comment syntax in markup.
- **Start:** the scratch repo with the factory from `main`.
- **Replay:** commit `{/* TODO(factory): Show a spinner while loading */}` in a `.jsx` file and run the scout.
- **Expected:** `Show a spinner while loading`. #38 established that titles contain only the comment text.
- **Actual:** `Show a spinner while loading */}`. In a second run, `<section>{/* TODO(factory): Add a card footer */}</section>;` gave `Add a card footer */}</section>;`.
- **Repeats:** 2/2 scout runs.
- **Evidence:** [`04-scout-main.txt`](2026-10-10-evidence/04-scout-main.txt).

## Journeys

### A. Take over an issue by assigning it, then hand it back: one bug

- **Goal:** while the issue is assigned, every stage posts ⏸️ and leaves the labels alone. After it's handed back, the factory picks it up again.
- **Ordinary path:** on sandbox#112, assigned to the owner, adding `needs-triage` posted ⏸️ and skipped every step after the assignee check, including the agent. Adding `ready-for-agent` while it was still assigned made implement post ⏸️ too, and the labels stayed. See [`01-assigned-112.txt`](2026-10-10-evidence/01-assigned-112.txt).
- **Variation, hand-back:**
  - On #112, triage correctly closed the issue as `wontfix`, because `capitalize` already exists. This covered the "already built" `wontfix` path. Triage also removed the stale `ready-for-agent` and closed the issue as not planned.
  - On #113 and #114, which asked for new helpers, the hand-back stalled (bug 1).

### B. Answer a `needs-info` question and get a fix: works

- **Goal:** a vague bug report gets questions. The reporter's reply sends the issue back to triage, and implementation resumes.
- **Ordinary path:** sandbox#115, "slugify makes broken slugs for some page titles" with no examples, was triaged as `bug,needs-info`. The comment summarised the settled facts and asked for an exact title, the actual slug and the expected slug.
- **Variation:** I replied as the reporter: `Straße` → `stra-e`, expected `strasse`. The comment started triage. Triage swapped `needs-info` for `ready-for-agent` and dispatched implement. The PR, sandbox#116, was opened and approved about 5 minutes after the reply (02:51:37 to 02:56:14 UTC).
- **Independent check:**
  - On PR head `6f84943`, `npm test` passed 130/130.
  - The new regression test failed against the base `slugify` with `actual: 'stra-e'`, matching the PR's claim.
  - Extra probes gave `Fußball-Weltmeisterschaft` → `fussball-weltmeisterschaft` and `Maße & Gewichte` → `masse-gewichte`.
  - See [`05-pr116-independent-check.txt`](2026-10-10-evidence/05-pr116-independent-check.txt), [`06-needs-info-115.txt`](2026-10-10-evidence/06-needs-info-115.txt) and [`06-pr116.diff`](2026-10-10-evidence/06-pr116.diff).

### C. Scout on `main`: earlier fixes hold, two new bugs

- **Goal:** each TODO becomes one ticket with a clean title and a working source link. Markdown, binary files and blank TODOs are skipped, and a rerun files nothing again.
- **Ordinary path:** the `--ref main` install added 13 files and 11 labels, set `npm test`, and flagged the missing key. See [`03-scratch-install-main.txt`](2026-10-10-evidence/03-scratch-install-main.txt). One scout run filed 9 tickets from 12 fixtures:
  - #37 holds: `TODO(factory):Validate…` gives `Validate the input type`.
  - #38 holds: the trailing `*/` and `-->` and CRLF's `\r` are stripped.
  - #41 holds: the blank TODO was skipped, and TODOs after it were still filed.
  - #42 holds: `src/g:colon.js` links correctly.
  - #43 holds: the binary file was skipped.
  - `docs/notes.md` was skipped, and `# TODO(factory):` in Python works.
  - New: the JSX title (bug 3) and the link for a path with a space (bug 2).
- **Variation:** a second run after adding two TODOs filed only those two, with no duplicates of the first nine. It replayed bugs 2 and 3.

## Unresolved and rejected candidates

- **Rejected:** a TODO longer than 256 characters stopping the scout. GitHub accepted the 316-character title, and later TODOs were filed.
- **Unresolved, not replayed:**
  - A JSX TODO whose trailing code changes would get a new title, and the exact-match duplicate check would file it again. This follows from the code.
  - Carried over from 2026-10-08: the duplicate check reads only the newest 1000 issues.
  - The scout skips `*.md` only. MDX (`.mdx`) and `.markdown` docs are scanned, although the README says it "skips Markdown". Not run.

## Usability observations

- **Observation:** `v1`, which users install, is 10 commits behind `main`. It is still missing the scout fixes for #37, #38, #41, #42 and #43, and the `.github/` check from #40.
- **Observation:** the two ⏸️ comments on one issue give different hand-back instructions: re-add `needs-triage`, or re-add `ready-for-agent`. Only the second starts implementation when both labels are present (bug 1).
- **Observation:** as on 2026-10-08, the issue keeps `ready-for-agent` after its PR opens, so the label doesn't show that an issue is already in progress.

## Not explored

- The Claude Code harness.
- `FACTORY_MERGE=true` and merge conflicts. `tests/smoke.py` covers these against live Actions.
- `wontfix` for a duplicate of an open ticket. Only "already built" was hit.
- A `needs-info` reply from a non-member, which should be ignored. This needs a second account.
- Taking over a PR, as opposed to an issue, by assigning it.

## Interventions and cleanup

- **Interventions:** none to the product.
  - The scout was started with `workflow_dispatch`.
  - Implement run 38018319078 was cancelled by hand once the agent started.
  - Model spend in the sandbox: 5 triage runs (one per issue for #112 to #115, plus #115's re-triage), 2 implement runs (one cancelled) and 1 review.
- **Cleanup:**
  - Closed sandbox#112 (by triage), #113, #114 and #115 as not planned.
  - Closed sandbox#116 without merging and deleted `agent/issue-115`.
  - Deleted the scratch repo.
  - No Docker containers, images or volumes were created.
