# Prompt-method machines (B1–B5)

Each prompt is a gated sequence executed by the model; the workflows enforce
its outputs (B3/B5 feed `run-agent/`'s `result` contract; B4's checklist is
reviewed by the next stage). Files: `template/.github/factory/*.md`.

## B1. `bug.md` — diagnose-then-fix

| State | Gate (must hold before leaving) |
|---|---|
| 1. Red loop | One command goes red on the **reported** symptom (seam test → CLI fixture diff → throwaway harness → random-input loop, in that order). Tight: seconds, deterministic, specific assert. Intermittent ⇒ raise the repro rate. Wrong symptom/severity = **a different bug** ⇒ stop. |
| 2. Minimise | Cut one element at a time, re-run after each cut. Done when every remaining element is load-bearing. |
| 3. Hypothesise | 3–5 ranked hypotheses, each falsifiable ("if X, changing Y makes it disappear") — before testing any. |
| 4. Probe | Rank order, one variable per probe; tag debug logs `[DEBUG-xxxx]`, one random suffix per run. Done when a probe confirms one hypothesis (= root cause). |
| 5. Regression test, then fix | Test at a "correct seam" (real call site); red → fix → green → original loop green. No correct seam ⇒ `No seam:` finding in the PR description, fix anyway. |

Terminal: return `needs-info` only for "no matching red" (that report is the
finished result). Output sections (required): Root cause, Reproduction,
Regression, Verification, Cleanup, Retained, Decisions.

## B2. `enhancement.md` — test-first vertical slices

| State | Gate |
|---|---|
| 1. Choose seams | Public interfaces chosen **before** any test; recorded under `Seams:`. |
| 2. Red → green per behaviour | One behaviour at a time ("tracer bullet"): write test → watch red (keep the failure line) → minimal code → green. Green-on-arrival ⇒ an earlier slice built it; note which. Next test only after green. |

"Good test" criteria (invariants): seam-only calls; literal expected values;
mock only system boundaries; one logical assertion. Output:
`Slices:`, `Seams:`, Verification, Cleanup, Retained.

## B3. `implement.md` — outcome + evidence

States: the run returns exactly one outcome.

| Outcome | Exit condition | Side effects |
|---|---|---|
| `completed` | Work done | Summary = PR body stub with method sections (B1/B2) + Verification + Cleanup + Retained + Decisions. |
| `needs-info` | Genuinely blocked on questions | Undo this run's file changes (keep previous saved work); report tried/established/questions; post `<!-- factory:implement needs-info -->…`; no PR. |

Evidence invariants: report failures/retries (a later pass doesn't erase
earlier ones); claim a check only if its result is in **this** run
(otherwise "unverified"); "not applicable" only with a one-line reason and
never for required checks. Cleanup scope: debug-marker search excluding
factory instruction text; an exact scoped retry command when a broader
search hit. "Previous attempt" section present ⇒ resume semantics (A8).

## B4. `review.md` — approve gate

Approve only if all four hold: (1) does everything the ticket asks, nothing
unrelated; (2) follows AGENTS.md/CLAUDE.md; (3) edge cases tested;
(4) evidence complete — checked against B3's summary requirements and, if a
Method section is present, **every box on the method's "Done when"
checklist** (that checklist is the method's whole bar for review; extra
logs only if the ticket/repo explicitly requires them). Gaps ⇒ name the
missing item, request the specific command/result — not a code change.
Output: `approve` | `request_changes` with concrete `required_changes`.

## B5. `fix.md` — fix sequence + description-only path

Steps: follow standards; base already merged, uncommitted (resolve conflicts
first if listed, keep both intentions, remove all markers); address every
feedback point; tests pass; leave changes uncommitted, outside `.github/`.
Summary appended to PR body (A15). **Description-only feedback needs no
commit**: write the missing evidence into the summary with the requested
headings; the appended section supersedes. (The workflow commits only if
`MERGE_HEAD` exists or the staged diff is non-empty; an empty summary with
no changes is an error — the workflow's commit step fails the job.)
