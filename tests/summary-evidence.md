# Initial implementation summary evidence

Live checks for [software-factory#26](https://github.com/jonbaldie/software-factory/issues/26), 2026-10-12. These observe generated descriptions and reviewer verdicts, not just words in prompt files. They spend model credit and are not part of CI.

## Setup and seams

- Repository: [software-factory-sandbox](https://github.com/jonbaldie/software-factory-sandbox). No competing PRs or active factory jobs at startup; unrelated needs-info issue #18 was left alone.
- `FACTORY_TEST_COMMAND=npm test`; `FACTORY_MERGE` stayed unset. Existing App credentials and `run-agent@v1` were unchanged.
- Seams named by the ticket: the initial implementation description and the reviewer's verdict/required changes. The bug fixture calls exported `slugify`: `Straße` produces `stra-e`, but should produce `strasse` after a narrow `ß` → `ss` transliteration.
- Installed only the five candidate prompts, through CI-green sandbox PRs [#120](https://github.com/jonbaldie/software-factory-sandbox/pull/120), [#122](https://github.com/jonbaldie/software-factory-sandbox/pull/122), [#124](https://github.com/jonbaldie/software-factory-sandbox/pull/124), and [#127](https://github.com/jonbaldie/software-factory-sandbox/pull/127). Final sandbox base: [`4b01d13`](https://github.com/jonbaldie/software-factory-sandbox/commit/4b01d1398412a52598934bd198ed56160453990a). All five installed prompts were compared byte-for-byte with software-factory candidate `e7d1a2d` and matched. No workflows, merge protections, retry limits, or output schemas changed.

## Attempts, including failures

1. **Incorrect setup:** [issue #117](https://github.com/jonbaldie/software-factory-sandbox/issues/117) alleged an empty-suffix bug that did not exist. The [implementer](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/38241633401) correctly returned `needs-info`: the exact call and existing tests passed. No PR or branch was created. Closed the incorrect fixture and independently reproduced the sharp-s bug before continuing.
2. **Old prompts, red summary check:** [issue #118](https://github.com/jonbaldie/software-factory-sandbox/issues/118) produced [PR #119](https://github.com/jonbaldie/software-factory-sandbox/pull/119) in [implement run 38242028479](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/38242028479). Its initial description had a root cause, regression failure excerpt, and passing test count, but no cleanup, retained-artifact accounting, or explicit original reproduction/green regression commands. Checking the generated body for `**Cleanup:**` failed with `AssertionError: initial summary is missing Cleanup evidence`. The [old reviewer](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/38242369009) nevertheless approved; that approval does not establish the omitted evidence.
3. **First candidate, failed first-review acceptance:** [issue #121](https://github.com/jonbaldie/software-factory-sandbox/issues/121) produced [PR #123](https://github.com/jonbaldie/software-factory-sandbox/pull/123) in [implement run 38242651942](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/38242651942). All named sections appeared, but cleanup accounted for only one of two instruction-text matches and omitted the exact scoped retry command. The [first review](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/38243105389) [requested a description-only correction](https://github.com/jonbaldie/software-factory-sandbox/pull/123#issuecomment-6123428618). The [fixer](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/38243417996) supplied both matches and the exact command, with 130 passing tests. This failed acceptance and prompted the explicit instruction-text exclusion/scoped-retry requirement.
4. **Second candidate, failed first-review acceptance:** [issue #125](https://github.com/jonbaldie/software-factory-sandbox/issues/125) produced [PR #126](https://github.com/jonbaldie/software-factory-sandbox/pull/126) in [implement run 38243618037](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/38243618037). Its cleanup was complete and it disclosed a stale post-fix assertion failure and a successful corrected probe. The [review](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/38244075886) [requested extra minimization/hypothesis logs](https://github.com/jonbaldie/software-factory-sandbox/pull/126#issuecomment-6123559313), beyond the method's closing checklist. The reviewer rewrite had inadvertently omitted the original instruction that this checklist is the whole method review bar. That instruction was restored before the fresh final run. The queued [fixer](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/38244360965) finished successfully after the fixture PR was closed; its recreated branch was then deleted.

These failures remain part of the evidence; later success does not erase them.

## Final candidate: first review accepts the initial summary

[Issue #128](https://github.com/jonbaldie/software-factory-sandbox/issues/128) produced [PR #129](https://github.com/jonbaldie/software-factory-sandbox/pull/129) in [implement run 38244602841](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/38244602841), at [`43d67fa`](https://github.com/jonbaldie/software-factory-sandbox/commit/43d67fa348493e2aa62626f17a24109e24c027c9).

The initial generated body, captured before review/fixing, contained **Root cause:**, **Reproduction:**, **Regression:**, **Verification:**, **Cleanup:**, **Retained:**, and **Decisions:**. It included:

- Original reproduction: an inline Node assertion calling `slugify("Straße")`, with actual `stra-e`/expected `strasse` before the fix and success after it.
- Regression: `node --test --test-name-pattern='slugify transliterates German sharp s' test/textkit.test.js`, with the pre-fix failure and post-fix result (1 passed, 0 failed). The retained test covers both `Straße` and minimized `ß`.
- Required checks: `npm test` passed 130 tests; `git diff --check` passed.
- Failed attempt/retry: `rg --files` was unavailable; `find . -maxdepth 3 -type f -not -path './.git/*' -print | sort` succeeded. The unavailable command was disclosed, not silently replaced by the successful inventory.
- Cleanup: `grep -nH -F '[DEBUG-' src/textkit.js test/textkit.test.js README.md` found no markers. The changed-file scope and factory instruction-text exclusions were stated. No disposable files were created; reproduction/probes were inline.
- Retained evidence: `test/textkit.test.js` keeps the exported-interface regression; no separate fixture file is needed.

**PASS:** [first review 38245065864](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/38245065864) [approved](https://github.com/jonbaldie/software-factory-sandbox/pull/129#issuecomment-6123689429) the same head at 11:50:54 UTC. The saved initial body equalled the body at approval, there was exactly one verdict, it was `approve`, and no fixer amendment existed. The [App CI check](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/38245059355/job/114796754431) also passed on that exact head. No description-only fix round preceded acceptance.

### Independent regression replay

In the disposable local sandbox clone, ran `npm test` at generated head `43d67fa`: **130 passed, 0 failed**. Restored only `src/textkit.js` from base `4b01d13`, retaining the generated test. Its named regression exited **1**:

```text
slugify transliterates German sharp s
+ 'stra-e'
- 'strasse'
```

Restored the generated source and reran that same command: **1 passed, 0 failed**, exit **0**. This confirms that the retained test observes exported production code and fails without the fix, rather than trusting the summary alone.

## Missing-cleanup negative check

Saved the accepted initial body and removed only the paragraph between `**Cleanup:**` and `**Retained:**`. The code, head, and all other evidence stayed unchanged.

Setup failure: `gh pr edit --body-file` failed on the deprecated GraphQL Projects-classic field. A REST `PATCH /repos/jonbaldie/software-factory-sandbox/pulls/129` succeeded and the body was checked against the intended cleanup-only deletion. The already-dispatched [review 38245358431](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/38245358431) had captured the original description at 11:51:45–47 UTC, before the REST update at 11:51:53; it is not evidence for the negative check. Dispatched a fresh [review 38245460826](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/38245460826) after verifying the edited body.

**PASS:** [review 38245460826](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/38245460826) [requested changes](https://github.com/jonbaldie/software-factory-sandbox/pull/129#issuecomment-6123749425) at the same head. Its sole required change named **Cleanup:** and requested the exact search command, scope, result, and disposable-file accounting (or an explicit statement that none were created/remain). It explicitly said no code change was needed unless accounting revealed leftovers. The snapshot at this verdict exactly matched the cleanup-only deletion. Restored the accepted initial body after saving that evidence, then closed the fixture.

## Local checks and review

- `uv run tests/labels.py`: **120 passed, 0 failed** on the final prompts. Used a workspace-local virtual environment installed with `uv pip sync` from compiled pinned requirements, then `VIRTUAL_ENV=… uv run --active`. The project has no dependency lockfile; no production dependency was added or changed.
- One earlier labels invocation hit the harness's 120-second command timeout after 66 output lines. Its partial log was preserved in the supplied run-log directory. A fresh invocation with a 300-second allowance completed successfully in 119 seconds, and the final prompt revision passed again. The interruption was a harness timeout, not a reported assertion failure.
- `uv run tests/pi.py`: **22 scenarios passed**. Markdown-only changes have no typechecking command.
- Standards and Spec reviews ran in independent parallel agents against starting commit `84f81f7`. Findings about repeated policy, enhancement applicability, and fixer retry reporting were addressed; final review results are recorded in the shipping PR.
- No trigger or queue behavior changed, so the push/merge smoke suites were not rerun. These live runs test the changed summary/review behavior instead.

## Cleanup and retained evidence

Verified all five temporary issues (#117, #118, #121, #125, #128) closed and all four bug fixture PRs (#119, #123, #126, #129) closed without merging. All eight temporary branches (four bug branches and four installation branches) are deleted. No sandbox Actions jobs remain active and `FACTORY_MERGE` is still unset. The negative check's already-started [fixer](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/38245729263) finished successfully after closure; cleanup was checked again afterwards.

Installation PRs are merged prompt upgrades, not disposable fixtures. This report, linked Actions transcripts, PR descriptions, verdict comments, and generated regression commits are durable evidence for future checks. The run-owned local sandbox clone, virtual environment, and temporary requirements file were removed; failure logs remain in the supplied run-log directory. No Docker containers, images, or volumes were created; pre-existing Docker resources were left untouched.

## Repeat the checks

1. Reserve an idle sandbox and install candidate prompts through a CI-green PR. Keep `FACTORY_MERGE` unset.
2. Independently reproduce a small bug, create a `bug` issue, then add `ready-for-agent` in a separate call.
3. Save the initial PR body before any fixer amendment. Check its evidence, exact first verdict/head, and that no description-only fix preceded approval.
4. Replay the generated regression with base and fixed production code.
5. Save the accepted body, remove only Cleanup using the REST PR endpoint, verify the edit succeeded, then dispatch `gh workflow run factory-review.yml --repo OWNER/REPO -f pr=N`. Preserve the specific rejection before restoring the body or closing the fixture.
6. Close fixture PRs/issues, wait for factory jobs, delete branches, and retain all failed attempts and evidence links in the report.
