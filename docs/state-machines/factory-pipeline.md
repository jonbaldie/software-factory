# Factory pipeline machines (A1–A16)

Storage keys: **issue labels**, **PR labels**, **factory review comments**
(bearing `<!-- factory:review … -->` markers), **branches** (`agent/issue-N`),
**workflow dispatches**. Files: `template/.github/workflows/factory-*.yml`,
`template/.github/factory/*.md`, `template/.github/factory/ticket.jq`,
`template/.github/factory/scout.sh`, `run-agent/`.
The 9 sites are enumerated in [`machines.json`](machines.json) (`dispatches`)
and checked in CI against the tree.

## A1. Issue lifecycle

Storage: issue labels + branch `agent/issue-N` existence.

States (invariant: at most one triage state is on — the failure handler
removes `needs-triage`, leaving *no* triage state; scout files new issues
with no category):

| Role | States |
|---|---|
| triage state | `needs-triage` · `needs-info` · `ready-for-agent` · `ready-for-human` · `wontfix` |
| category | `bug` · `enhancement` |
| overlay | `agent:working` · `agent:failed` · `agent:wip` |
| orthogonal | OPEN/CLOSED · assigned/unassigned |

Transitions:

| Event | From → To | Guard / detail |
|---|---|---|
| reporter-or-maintainer comment | `needs-info` → `needs-triage` | Triage is woken only if the issue is `needs-info` and the commenter is the issue author or an OWNER/MEMBER/COLLABORATOR. |
| triage verdict | `needs-triage` → exactly one of `needs-info` / `ready-for-agent` / `ready-for-human` / `wontfix` | Sets category (replaces the other). `wontfix` also closes the issue (`--reason "not planned"`). If the issue is already CLOSED or `agent:working` is on, it still updates labels but does not dispatch implement. |
| outsider verdict | `needs-triage` → `ready-for-human` (not `ready-for-agent`) | Issue author ∉ {OWNER, MEMBER, COLLABORATOR}, author ≠ `github-actions[bot]`, and the issue does not already carry `ready-for-agent`. |
| dispatch | `ready-for-agent` → implement run | Explicit `gh workflow run factory-implement.yml` (label edits with `GITHUB_TOKEN` don't fire workflows). The run's first action claims `agent:working` (keeps `ready-for-agent`; re-triage sees `agent:working` and starts no second run). |
| issue closed at publication | `ready-for-agent` → stand down | Re-checked before publishing the PR and again before saving WIP: remove `agent:working`, post a stand-down comment, `exit 0` — nothing is published and nothing is saved. To resume: reopen, remove and re-add `ready-for-agent`. |
| implement `completed` | `ready-for-agent` → (PR open) | Removes `agent:working` + `agent:wip`. |
| implement `needs-info` | `ready-for-agent` → `needs-info` | Removes `agent:working,ready-for-agent,agent:failed`. |
| any stage failure/cancel | * → `agent:failed` (+ `agent:wip` iff saved, A8) | First action of every run: clear `agent:failed`. |
| retry | `agent:failed` → stage label | Re-add `needs-triage` (triage) or `ready-for-agent` (implement). `agent:wip` present ⇒ resume; removed ⇒ start over. |
| failure after the PR exists | `ready-for-agent` → `agent:failed` **on the PR** | Hand-off failure: `agent:failed` goes on the PR (review's start clears it), never pushed again; `agent:working,agent:wip` removed from the issue; handoff instructions posted. |
| duplicate implement | `ready-for-agent` → no run | An open PR for `agent/issue-N` already exists: stand down (the run isn't unfinished). |

## A2. PR lifecycle

Storage: PR labels + review comments + `headRefOid`.

States:

| Role | States |
|---|---|
| queue | `agent:review` (queued/under review) |
| handoff | `agent:changes-requested` (fixer owns) |
| verdict | `agent:approved` (**bound to a commit** — `Reviewed commit: <sha>` in the comment; any new head expires it) |
| failure | `agent:failed` |
| escalation | `ready-for-human` |
| orthogonal | OPEN/CLOSED/MERGED |

Transitions:

| Event | From → To | Guard / detail |
|---|---|---|
| implement opens PR | — → `agent:review` | Explicit dispatch to `factory-review.yml` (`automatic=true`). |
| push (`synchronize`) | `agent:approved`\|`agent:review` → `agent:review` | Drop `agent:approved`, (re)add `agent:review`, dispatch review (`factory-review-push.yml`). Metadata only — never checkout/execute PR code. |
| review `approve` | `agent:review` → `agent:approved` | Head must still be the reviewed sha (A4); then A6 merge gate or wait. |
| review `request_changes` or tests failing | `agent:review` → `agent:changes-requested` (round < 3) · `ready-for-human` (round ≥ 3) | Round counted per A5; dispatches fix. |
| fix finish | `agent:changes-requested` → `agent:review` | Dispatch review `automatic=true`. |
| stage failure | * → `agent:failed` | Retry: re-add `agent:review` / `agent:changes-requested`. Manual re-review of an approved PR: adding `agent:review` clears `agent:approved` at run start. |

## A3. Serialisation (concurrency)

Storage: GitHub Actions `concurrency` groups.

- Issue workflows share `factory-issue-<N>` (never concurrent; no `queue: max`,
  so a pending run *can* be replaced — unlike PR groups).
- PR workflows share `factory-pr-<N>` with `queue: max` (never *cancelled*):
  a delayed push must not replace a pending fix or review.
- Concurrency is on the **job**, not the workflow (a skipped label run would
  otherwise cancel a queued useful run).
- `automatic=true` is the idempotence gate: a queued automatic run stands
  down if the PR has left the expected label (`agent:review` for review,
  `agent:changes-requested` for fix) or is no longer OPEN. Manual dispatch
  (`automatic` unset) always runs — but the per-stage OPEN + assignee pauses
  (A7) still apply to manual dispatches too (review:54, fix:49).

## A4. Head-commit validity (stale verdict)

Storage: `headRefOid` vs `steps.revision` (sha at checkout), checked by
`require_current_head()` (12 refs in `factory-review.yml`, 3 in
`factory-fix.yml`).

- Review checks at entry, after publishing the comment, after `gh pr edit`
  and before the dispatch, before merging, each CI-poll iteration, and after
  a merge failure.
- On change: supersede this run's comments (PATCH body; markers stripped so
  they cost no fix round), drop handoff labels, dispatch `automatic=true`
  review, `exit 0`.
- Push handler checks from the other side: if the latest factory `approve`
  comment names the *current* head, stand down (already reviewed).
- Fix discards changes on head change (re-dispatches the same feedback,
  same round); a push racing only the `git push` itself: if the push fails
  and the head changed, the job re-queues and **exits 0**; other push
  failures still fail the job.
- Merge uses `--match-head-commit "$REVIEWED_SHA"` (last line of defence).

## A5. Fix-round counter

Storage: **counted from comments** — count of `github-actions` comments
containing `<!-- factory:review request_changes -->`, +1 for the current run.
Cap `MAX_ROUNDS = 3` (declared in `factory-review.yml`, mirrored in
[`machines.json`](machines.json)).

- Round 3 rejection → `ready-for-human`, no dispatch.
- Merge conflict after approve: posts a `request_changes` marker (consumes
  a round), fixer if `round < MAX_ROUNDS`, else `ready-for-human`.
- Stale-verdict discarding (A4) **refunds** the round (markers removed).

## A6. Merge gate (`FACTORY_MERGE`)

| Step | Condition / outcome |
|---|---|
| 1. Head | `require_current_head()` still holds after labelling approved. |
| 2. CI wait | Poll `gh pr checks --required`, 60 × 5 s: wait only while buckets ∈ {pending, pass, skipping}, ≥1 pending. Empty result breaks too, if `mergeStateStatus` ∉ {BLOCKED, UNKNOWN}; failed checks break immediately (GitHub's rules then govern). Head re-checked each iteration. |
| 3. Assignee (only when `MERGE=true`) | Re-check just before merging (A7): assigned ⇒ leave approved, open. The CI poll loop itself does not check assignees. |
| 4. Merge | `gh pr merge --squash --delete-branch --match-head-commit "$REVIEWED_SHA"`. |
| 5. On failure | `require_current_head()` again; wait for `mergeable` to leave UNKNOWN (6 × 5 s); `CONFLICTING` + rounds left ⇒ fixer (consumes round); else `ready-for-human` with a "GitHub blocked the merge" comment. |

## A7. Assignee pause

Storage: issue assignees; PR assignees ∪ closing-issue assignees (`sort -u`).

- Every stage checks at start: if assigned, post ⏸️ and leave labels untouched
  (triage's exception: a reply on an assigned issue gets no comment at all).
- Review re-checks at step A6.3 (after the CI wait, only when `MERGE=true`); the CI poll loop itself does not check assignees.
- Push handler deliberately does **not** pause: a push to assigned work still
  clears approval and re-queues review (labels must reflect "needs review"
  while a human owns the work).
- Hand-back protocol: unassign, then remove and re-add the stage label.

## A8. Failure / recovery

Per workflow: `"Report failure"` step (`if: failure() || cancelled()`):
remove the stage's working label, add `agent:failed`, post a 💥 comment
with retry instructions, no dispatch. Implement adds the WIP sub-machine:

- Eligible: the agent step ran (success/failure/cancelled) AND the tree is
  dirty **or HEAD is ahead of the origin branch** (`unpushed` commits are a
  reason to save) AND no `.github/` changes (diff vs `merge-base(HEAD, GITHUB_SHA)`,
  so the agent's own commits count; resumed WIP's base excludes main's own
  `.github/` moves).
- Reason from the failing step (`JOB_STATUS`, `AGENT_OUTCOME`,
  `TESTS_OUTCOME`, `PUBLISH_OUTCOME`): timeout/cancel · tests · agent error
  · pushing the finished work failed · run failure
  (test tail, 40 lines, when tests failed).
- Commit `WIP: <title>` + reason + run URL to `agent/issue-N`, force-push
  with `GITHUB_TOKEN`; `agent:wip` added only if the push succeeded.
- Resume: `wip_base = merge-base(HEAD, origin/agent/issue-N)`; the prompt
  gains a "Previous attempt" section (`git log <base>..origin/branch`).

## A9. Trust / authorisation

- **Implement gate**: triage downgrades its own `ready-for-agent` verdict to
  `ready-for-human` for outsiders (author ∉ {OWNER, MEMBER, COLLABORATOR},
  ≠ `github-actions[bot]` (scout), and no pre-existing `ready-for-agent`
  (maintainer-given)). No issue template: a template adding `needs-triage`
  would let anyone start runs.
- **Comment visibility** (`ticket.jq`): agents see only
  OWNER/MEMBER/COLLABORATOR comments, plus factory-generated ones
  (`> *This was generated by AI during triage.*` or
  `<!-- factory:implement needs-info -->`, author `github-actions`), plus —
  for triage only (`--arg reporter`) — the reporter's own comments. The
  reporter's words *in the issue body* are still visible to every stage
  (the body is the ticket). Review receives no factory review and no PR
  comments at all; fix receives the latest factory review by marker plus
  maintainer PR comments.
- **Triage trigger**: `issue_comment` starts a run only if `needs-info` ∧
  commenter is the issue author or OWNER/MEMBER/COLLABORATOR.
- **Approval counting** (A5) filters `author.login == "github-actions"` —
  "anyone can post a comment with the marker".

## A10. Category → method dispatch

One shared assembly site (`template/.github/factory/prompt.sh:29-32`) serves
implement, review **and** fix: case-insensitive match, first match wins —
**`bug` before `enhancement`** (so `bug` wins if both labels present);
neither ⇒ general instructions only. `bug.md` / `enhancement.md` carry
"Done when" checklists the reviewer enforces (B4).

## A11. Cross-workflow handoffs

`GITHUB_TOKEN` label edits don't trigger workflows, so every handoff is an
explicit `gh workflow run` (`machines.json` lists all 9 sites; the validator
counts them):

| # | From → To | `automatic` |
|---|---|---|
| 1 | triage → implement | — (open-PR guard dedups) |
| 2 | implement → review | `true` |
| 3 | fix → review | `true` |
| 4 | review → fix (merge conflict, line 279) | — |
| 5 | review → fix (rejection, line 296) | — |
| 6 | review self-requeue (stale head) | `true` |
| 7 | fix self-retry (stale head) | `true` |
| 8 | push → review | `true` |
| 9 | scout → triage | — |

## A12. Scout discovery loop (`factory-scout.yml`)

States: a flat scan with title-dedup bookkeeping (`existing` = all issue
titles — paged through every issue with `gh api --paginate`, PRs filtered
out (`scout.sh:7-8`); the title is the dedup key; the list grows within the
run, so repeated TODO titles file once).

- Streaming parse of NUL-delimited `git grep -z -n -I -F 'TODO(factory):'`
  (path may contain colons; binary matches skipped; `*.md` and `.github`
  skipped).
- Title: trim leading space, strip trailing block (`*/` if opener has `/*`)
  or HTML (`-->` if opener has `<!--`) closer, strip trailing whitespace/CRLF.
  Blank titles: skipped.
- File with `--label needs-triage`, append title to `existing`, dispatch
  triage (site 9); dispatch failure ⇒ report + `exit 1` (already-filed
  issues remain).
- Report: per-label open counts via `count()` (fetch limit 1001 to separate
  "31" from "1000+"); merged-approved-in-7-days via `--search "merged:>=$since"`.

## A13. Agent outcome classification (`run-agent`)

Two layers, one contract: the transcript's final `result` JSON line.

`run-agent/pi.mjs` (pi has no budget flag / structured output):

- **Budget**: `spent` (finished messages) + `streaming` (in-flight)
  accumulates cost; crossing ⇒ `SIGTERM` to the process group, `SIGKILL`
  after 5 s; `overBudget` latched at first crossing.
- **Subtype precedence**: `error_max_budget_usd` (overBudget) >
  `error_during_execution` (nonzero exit ∨ no assistant message ∨
  stopReason ∈ {error, aborted} — pi exits 0 in JSON mode even on provider
  failure) > `error_structured_output` (schema set but extraction/validation
  failed) > `success`.
- **Structured extraction**: the last valid ```` ```json ```` block,
  tolerating ```` ``` ```` inside JSON strings (extend past the first fence
  if that fails to parse), incrementally validating required keys, top-level
  types and enums. Anything else = no answer ⇒ the stage fails rather than
  acting on a guess.
- **Transcript parity**: raw stream + a Claude-Code-shaped `result` line;
  partial trailing line terminated first.

`run-agent/action.yml`: harness dispatch (pi/claude; unknown ⇒ error),
per-harness credential checks, tool-name mapping (Claude `Glob` → pi
`find`), extracts the last `result` line (missing ⇒ error), exposes
cost/turns/structured-output, writes the job summary, fails the step iff
`is_error`. The invocation is `|| true`: the result line, not the exit
code, decides the outcome.

## A14. Prompt provenance (per-stage snapshot)

- Triage & implement: prompts from the checked-out **default branch**
  (implement works on the saved branch afterwards — "the prompt is the
  current one, the work is the old one").
- Review & fix: prompts unpacked from `origin/<base>` via `git archive`
  **outside the checkout** (the agent can't commit them; PRs opened before
  a prompt change still get the new prompt).
- `.github/` guard: implement diffs vs `merge-base(HEAD, GITHUB_SHA)`;
  fix diffs the **staged tree vs `origin/BASE`** (the base merge brings
  base's `.github/` in — any remainder came from the agent). Fix also
  scans conflicted files for leftover `<<<<<<<`/`>>>>>>>` markers.

## A15. PR body accumulation

- Implement creates the body from the `completed` summary + `Closes #N`.
- Fix appends its summary + a `_Fixed by the factory_` footer; the reviewer
  reads the whole accumulated body (later sections supersede earlier ones).
- A retry after the PR was closed opens a **fresh** PR (the closed one
  keeps its old description and can't merge).

## A16. Scout parser (JS-aware TODO classification)

`template/.github/factory/scout-js.py` sorts every JS/TS TODO before the
issue machine (A12) sees it: `scout-parse.cjs` (vendored Babel parser) +
the `in_js_string` quote lexer (`scout.sh:9-33, 38-60`) classify each TODO
as `normal` / `block` / `html` / `skip` (inside a string) / `unparsed`.
A `skip` (inside a string, regexp, or JSX text — `scout-parse.cjs:22` ignores all three) posts a "Skipped TODO" report entry and files nothing;
`unparsed` is still filed but noted. This decides which TODOs become issues
at all — it is a filter in front of A12's dedup.
