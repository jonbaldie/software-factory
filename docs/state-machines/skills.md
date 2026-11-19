# Skill-process machines (E1–E14)

These are **prompt-encoded** processes in `.agents/skills/`: states exist
only as far as an agent following the instructions advances them. None are
executed by this repo's CI; each spec below is the declared sequence, kept
stable so a skill edit must update it. Files: `.agents/skills/*/SKILL.md`
unless stated otherwise.

## E1. `triage` + `AGENT-BRIEF.md` + `OUT-OF-SCOPE.md`

The only skill that **declares** its machine ("a small state machine"):
2 category roles × 5 state roles, invariant = exactly one of each;
conflicting state roles ⇒ flag and ask before acting.

| Role | States |
|---|---|
| category | `bug` · `enhancement` |
| state | `needs-triage` · `needs-info` · `ready-for-agent` · `ready-for-human` · `wontfix` |

Hand-driven transitions: unlabeled → `needs-triage` → one of the four
outcomes; `needs-info` → `needs-triage` on reporter reply; maintainer
override anytime (flag unusual transitions). Discovery buckets: Unlabeled,
`needs-triage`, stale `needs-info` (reporter activity since last notes).

Per-issue procedure (gated sequence): 1. **Gather** (incl. redundancy:
existing implementation ⇒ `wontfix`; prior rejection: `.out-of-scope/`);
2. **Recommend**, wait for direction; 3. **Verify the claim** (reproduce
bug / run PR tests) — confirmed / failed / insufficient-detail;
4. **Grill** if needed (grilling + domain-modeling, rounds);
5. **Apply outcome**. `wontfix` splits 3 ways: already-implemented (point
to code, no KB write) / rejected bug (polite, close) / rejected
enhancement (write `.out-of-scope/<concept>.md`, link, close).
Quick-override path skips grilling. Repeat sessions must not re-ask
answered questions.

`.out-of-scope/` KB lifecycle: one file per concept; check on intake
(concept similarity, not keywords); match ⇒ confirm (append to Prior
requests + close) / reconsider (delete/update KB, proceed) / disagree
(proceed); rejected features only, never already-built ones.

> Relationship to the factory: same label vocabulary, **different machine**
> — the factory's triage (A1) is stricter (outsider-hold, auto-dispatch,
> single-shot brief) and does not verify claims, grill, or use the KB.

## E2. `wayfinder` + `docs/agents/issue-tracker.md`

Two phases over a tracker:

- **Chart**: grill the destination → map the frontier breadth-first →
  create map (`wayfinder:map`) + child tickets → wire blocking edges in a
  second pass (needs ids) → fire research subagents → stop.
- **Work**: load map → pick frontier ticket (or user's) → **claim**
  (assign, before any work) → resolve → comment answer + close + append
  Decisions-so-far pointer → graduate fog / rule out-of-scope.

Ticket states: map ↔ child; `open-blocked` / `open-unblocked-unclaimed`
(the **frontier**) / `claimed` / `resolved` / `out-of-scope` (closed, never
graduates). Unblocked = every blocker closed. Never resolve >1 ticket per
session (research excepted). Types: research (AFK) / prototype (HITL) /
grilling (HITL) / task (HITL|AFK).

**Fog of war** = unordered "Not yet specified" (in scope, unsharp); ticket
iff the question can be stated precisely **now** (blocked is fine).
Out-of-scope is scope-based, closed, listed separately. This repo's
`docs/agents/issue-tracker.md` implements Map/child/natively-blocking/
Frontier (open, `blocked_by == 0`, unassigned, first-in-order)/Claim/
Resolve via `gh api` sub-issues + `dependencies/blocked_by`, with a
`Blocked by:` text-line fallback.

## E3. `implement-spec` — task-graph frontier + integration branch

States: `frontier` (blockers done, grabbable), `in-flight` (implementer
subagent in own worktree/branch), `merged-to-integration`, `done`.

Loop: read graph → (optional exploration subagent, notes outside the repo)
→ create integration branch (+ draft PR after first merge, if PRs close
work) → for each frontier ticket: implementer (confirm based on
integration tip, TDD, merge integration tip in before reporting) → merger
subagent → re-evaluate frontier → repeat; then one `code-review` over the
integration branch, fixes via a single implementer, mark PR ready/close
tickets, delete worktrees. Communication only via context pointers.

## E4. `grilling` — decision-tree rounds

State: a decision tree; the **frontier** = decisions whose prerequisites
are settled. Each round asks the *entire* frontier (numbered, each with a
recommended answer), waits, recomputes. A question blocked on a still-open
question in the same round belongs to a later round. Facts are the agent's
job (subagents), decisions the user's. Termination: frontier empty + user
confirmation. Shared primitive — `/triage`, `/wayfinder`,
`/improve-codebase-architecture`, `/grill-me`, `/grill-with-docs` all run it.

## E5. `diagnosing-bugs`

Six phases with per-phase completion criteria (skip only with justification):

1. **Feedback loop** — 10 construction methods in preference order; "tight"
   = fast + deterministic + specific assert; non-deterministic ⇒ raise the
   repro rate; impossible ⇒ stop and ask. Gate: red-capable command run.
2. **Reproduce + minimise** — wrong-bug check, multi-run repro, symptom
   capture; cut one thing at a time until all remainder are load-bearing.
3. **Hypothesise** — 3–5 ranked falsifiable hypotheses, shown to the user
   before testing.
4. **Instrument** — one variable per probe (debugger > targeted logs);
   `[DEBUG-*]` tags for single-grep cleanup; perf ⇒ baseline + bisect.
5. **Fix + regression test** — only at a "correct seam"; none ⇒ the
   absence is itself the finding (route to architecture improvement).
6. **Cleanup** — loop re-run, test pass, tags grepped out, throwaways
   deleted, root cause in the commit message.

Interactive variant: `scripts/hitl-loop.template.sh` runs the same loop
human-in-the-loop (a second executable protocol alongside E10).

Note: the unshrunk ancestor of factory `bug.md` (B1) — the factory version
hardens the gates and returns `needs-info` instead of asking.

## E6. `ask-matt` + `PHASE-BOUNDARIES.md`

`ask-matt` is a router over skills; it encodes the **main-flow sequence**
(idea → ship): `grill-with-docs` → optional `prototype` detour bridged by
`handoff` → multi-session? (`to-spec` → `to-tickets` → `implement` per
ticket / `implement-spec` once) → `tdd` + `code-review` → `pr` → `retro`.
Three on-ramps (`triage`, `diagnosing-bugs`, `wayfinder`) merge onto it;
`wayfinder` hands off at `to-spec`, never straight to `implement`.
Context hygiene: one unbroken window through `to-tickets`, then clear per
ticket.

`PHASE-BOUNDARIES.md` is an ordered decision tree (first "yes" wins):
1. Can you continue? (primary source needed / smart zone left) ⇒
   Continue. 2. Context irrelevant? ⇒ `/clear`. 3. Portability needed (new
   harness/dir/colleague/mid-phase fork)? ⇒ `/handoff`. 4. AFK-able (tightly
   scoped)? ⇒ Subagent. 5. Otherwise ⇒ `/compact` (the default, at the
   bottom). Decisions only at boundaries, never mid-phase.

## E7. `teach`

Workspace state is files: `MISSION.md` (why/success/constraints/out-of-scope;
one mission per workspace; revise on shift + learning record) →
`RESOURCES.md` (Knowledge/Wisdom, annotated, gaps explicit) → per-session:
read learning records → pick a task in the **zone of proximal development**
→ teach a lesson (`lessons/0001-*.html`, assets reused first) → **learning
record** iff genuine understanding / disclosed prior knowledge / corrected
misconception / mission shift (never mere coverage or activity logs).
Records carry optional `active | superseded by LR-NNNN` status plus
`Evidence`/`Implications`; supersession marks old records, never deletes.

## E8. `to-tickets` — slicing, blocking DAG, expand–contract

Sequence: gather → (optional) explore → draft **tracer-bullet vertical
slices** (each complete through all layers, demoable, single-window sized)
→ quiz the user (granularity / edges / merge-split, iterate to approval) →
publish **in dependency order** (blockers first) as local files
(`.scratch/<feature>/issues/NN-<slug>.md`) or tracker issues with
`ready-for-agent`. Output is a DAG with a "work the frontier" rule; a pure
chain degenerates to top-to-bottom. **Wide refactors** break vertical
slicing ⇒ exception path: **expand–contract** (add new form → migrate in
blast-radius batches, CI green throughout → contract: delete old form),
escalating to an integration branch only when batches can't stay green.

## E9. `setup-matt-pocock-skills` — conditional scaffolding interview

Explore (remote, existing AGENTS/CLAUDE block, GLOSSARY, `docs/adr/`,
`docs/agents/`, `.scratch/`, triage installed?, monorepo signals) → present
→ sections in order, one question at a time, each led by the recommended
answer. Section B (triage labels) is **skipped entirely** if `triage`
isn't installed; Section C (domain layout) asks only on monorepo signals.
Confirm-and-edit draft → write (never create `AGENTS.md` if `CLAUDE.md`
exists; update the `## Agent skills` block in place; seed from the skill's
templates). The local-tracker template (`issue-tracker-local.md`) defines a
file-based machine: `Status:` line (`ready-for-agent`, `claimed`/`resolved`
for wayfinder tickets), `Blocked by: NN,…`, frontier = scan open +
unblocked + unclaimed, first-by-number.

## E10. `wizard/template.sh` (+ `wizard/SKILL.md`)

Executable protocols (the library lists below are identical per wizard).
The wizard's library: `_STAGE_INDEX`/`TOTAL_STAGES`
counter with on-screen `Stage i/N`, `banner`, `stage`, `ask` /
`ask_secret` (Enter-keeps-current = idempotent re-runs), `write_env`
(idempotent `.env` upsert), `set_secret` / `set_var` (`gh` absent/failing
⇒ record in `SKIPPED`, never fail), `confirm`/`pause` gates, `finish`
summary. Skill process: scope (values + where each lands + secret?/public)
→ map each stage's click-path → author one stage per step → static verify
(`bash -n`, shellcheck, every value captured, every `set_secret` name
matches a `secrets.*` reference), never run end-to-end (opens browsers,
blocks on input).

## E11. `code-review` + `implement` + `tdd` (allocations)

`code-review` is a fixed-point + two-axis fan-out, not a state machine
itself (listed for the guard): pin fixed point (`git diff <fp>...HEAD`,
verify it resolves and the diff is non-empty — fail here, not in subagents)
→ identify spec (commit refs → user path → `docs/`/`specs/`/`.scratch/` →
ask; absent ⇒ Spec axis skipped) + standards sources (+ fixed 12-smell
baseline, repo overrides, judgement-call only) → run **Standards** and
**Spec** sub-agents in parallel → aggregate **without merging or
reranking**.

`implement` (1-line): tdd → typecheck/test → `code-review` → commit.
`tdd`: the red–green loop (reference for B2 at slice granularity);
`tdd/tests.md` gives good/bad/tautological test criteria, not a machine.
Allocations: `implement` and `tdd` are specified here, not in E14.

`code-review` is a fixed-point + two-axis fan-out, not a state machine
itself (listed for the guard): pin fixed point (`git diff <fp>...HEAD`,
verify it resolves and the diff is non-empty — fail here, not in subagents)
→ identify spec (commit refs → user path → `docs/`/`specs/`/`.scratch/` →
ask; absent ⇒ Spec axis skipped) + standards sources (+ fixed 12-smell
baseline, repo overrides, judgement-call only) → run **Standards** and
**Spec** sub-agents in parallel → aggregate **without merging or
reranking**.

`implement` (1-line): tdd → typecheck/test → `code-review` → commit.
`tdd`: the red–green loop (reference for B2 at slice granularity);
`tdd/tests.md` gives good/bad/tautological test criteria, not a machine.

## E12. `improve-codebase-architecture` + `codebase-design`

Explore/report/grill loop: scope (YAGNI: user direction, else hot spots from
`git log`) → explore with friction notes + deletion test → HTML candidate
report (recommendation strengths: Strong / Worth exploring / Speculative;
ADR-conflict callouts) → user picks → grilling+domain-modeling loop with
inline side effects (GLOSSARY additions, ADR offers, design-it-twice for
alternative interfaces). `DESIGN-IT-TWICE.md` is a parallel fan-out (3+
sub-agents under different constraints: minimise / maximise flexibility /
optimise common case / ports-and-adapters), then present, compare on
depth/locality/seam, recommend a hybrid. `DEEPENING.md` classifies
dependencies (in-process / local-substitutable / remote-owned /
true-external ⇒ mock) to choose testing strategy; "one adapter =
hypothetical seam, two = real".

## E13. `prototype/LOGIC.md`

Meta: where state machines are prototyped. Explicitly the skill for
validating **state models** before building: state the question → isolate
a pure portable module (choose shape by question: **reducer**
`(state, action) → state` / **explicit state machine** / pure functions /
owning class — "which actions are legal right now" is the tell for a
machine) → self-contained HTML demo (free-play buttons + guided
walkthroughs with reset to a known initial state; awkward cases mandatory,
incl. an illegal attempt) → handover → the pure module lifts into
production; the shell stays on a `prototype/<name>` branch. Anti-patterns:
no tests (a prototype needing tests isn't one), no real DB, no
generalising, no DOM in the module.

## E14. Minor / format-level

- **ADR lifecycle** (`domain-modeling/ADR-FORMAT.md`): optional `Status`
  frontmatter (`proposed | accepted | deprecated | superseded by
  ADR-NNNN`); created lazily; numbered by max+1; write only if hard-to-
  reverse + surprising-without-context + real trade-off.
- **`to-spec`**: linear process (explore → sketch seams, check with user →
  write spec from template → publish with `ready-for-agent`). Carries the
  same "inline a prototype snippet iff it encodes a decision more precisely
  than prose" rule as `to-tickets`.
- **`to-questionnaire`**: two interview steps with "Done when" per step,
  then write file to `to-questionnaire-<slug>.md`.
- **`handoff`**: one-shot — compact now → file in OS temp dir (never the
  workspace, never duplicate existing artifacts, redacted) with a
  "suggested skills" section for the next agent.
- **`research`**: background agent → primary-source investigation →
  single cited markdown file at the repo's existing convention.
- **`retro`**: gather session log → candidate categories (navigation /
  automated checks / standards / tooling) → suggest environment changes,
  not code.
- **`pr`**: a document template (Summary/Evidence/Merge-Danger with
  one-way-vs-two-way door call), not a process.
- **`domain-modeling`**: keeps GLOSSARY/ADRs current as decisions land
  (consumer half: `docs/agents/domain.md`, installed by E9).
- **`codebase-design`**: presents a 4-item dependency-category decision
  procedure (E12) — a classification rule, not a runtime machine.
- Trivial delegates with no machine: `grill-me`, `grill-with-docs` (call
  grilling ± domain-modeling), `wait-what` (re-pitch in STE + glossary
  terms), `.agents/skills/*/agents/openai.yaml` (harness metadata).
- `writing-for-agents`: guidance for writing skills/AGENTS.md/CLAUDE.md
  (not itself a process).
