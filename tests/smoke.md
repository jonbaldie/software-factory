# Live smoke tests

`tests/labels.py` checks each job's label changes against a fake `gh`. It can't check what GitHub does around those jobs: which events start a workflow, how the per-PR queue orders the review, fix and push-handler jobs, and whether `pull_request_target` still fires when a push makes the PR conflict with its base. `tests/smoke.py` checks those on the [sandbox](https://github.com/jonbaldie/software-factory-sandbox) with real GitHub Actions runs.

Run it after changing how review, fix or the push handler are triggered, queued or invalidated. It spends model credit on one implement run and about seven reviews, so CI doesn't run it.

The separate merge suite checks automatic merging, a passing push during review, and conflict recovery through the fixer. It uses three small fixture PRs and spends about five reviews and one fix, with no implementation run.

## Run it

1. Install the version under test in the sandbox and merge it to the sandbox's default branch. The workflows only run from there.
2. For the default push suite, leave `FACTORY_MERGE` unset in the sandbox. The script stops if it is `true`. Both suites require permission to read Actions variables; the merge suite also requires permission to change them.
3. Sign in with `gh` as someone with write access to the sandbox, and let git push to it over HTTPS (`gh auth setup-git`).
4. Reserve the sandbox for this run: close other factory PRs and wait for active factory jobs to finish. Don't start other factory work until it ends. GitHub's API doesn't associate dispatched review/fix runs with their PR, so those observations require exclusive use of the sandbox. The script rejects existing competing work at startup.
5. From this repository:

   ```sh
   uv run tests/smoke.py --report smoke-report.md
   ```

It takes about 15 minutes, longer if the reviewer requests changes. Each check prints `PASS` or `FAIL` as it completes. At the end the script prints a Markdown report with the commit, run and comment links, and exits non-zero if any check failed. Add the report to [Runs](#runs).

To continue after a stop, pass the approved PR and the remaining stages, for example `--pr N --stages s3,s4a,s4b`. s4b continues from s4a's conflict. The PR and its issue stay open for inspection; close them afterwards, or pass `--close`.

By default the script uses a temporary clone. `--clone` must point to a clean, disposable sandbox clone: the script resets its local test branches to the remote before each push.

### Automatic merging

With the same exclusive use of the sandbox, run:

```sh
uv run tests/smoke.py --suite merge --close --report merge-smoke-report.md
```

The driver saves the original value of `FACTORY_MERGE`, enables it for this suite, and restores the original value (including an absent variable) in `finally`, on success, failure or Ctrl-C. It records restoration in the report. A killed process or loss of GitHub access can prevent restoration; the setup output records the original value for recovery.

Each stage creates its own issue and PR on `agent/issue-N`, then dispatches the installed reviewer. These deterministic fixture commits isolate review, fix and merge behaviour from implementation. `--stages m2` or `--stages m3` reruns only that stage with a fresh PR; `--pr` is not supported for this suite. Node and npm must be installed locally so the driver can check the fixtures before pushing and run `npm test` on `main` after merging.

| Stage | Action | Required outcome |
|---|---|---|
| m1 | Open a passing fixture PR and dispatch review with merging enabled. | The factory squash-merges the exact reviewed head. |
| m2 | Wait until the agent reviews a passing commit, then push another passing commit. | The stale review discards its verdict without a fix round. The push handler waits in the PR queue; a fresh review approves the replacement and the factory merges it. The duplicate review request skips its agent. |
| m3 | Open a passing fixture PR, then merge a base change that conflicts with it. Dispatch review explicitly, since GitHub skips `pull_request` workflows for conflicting PRs. | The reviewer approves the conflicting head, hands the merge conflict to one fix run, then reviews a different, fixed commit before merging it. Both branches' intended changes survive. |

Every stage checks the bot merge actor, the approval's commit and timing, successful test and agent steps, and that the squash commit is on the base branch with exactly the reviewed tree. It runs all sandbox tests locally on the merged base and checks that no factory job failed or was cancelled. m3 changes separate fields on the same JSON line, with separate tests for each side; choosing either whole file cannot satisfy both tests.

`--close` closes any unfinished test PRs and issues, waits for factory jobs to finish, and deletes all branches created by the suite. The merged `smoke-merge.json` and `test/factory-merge-{base,branch}.test.js` fixtures remain for future runs; each run updates their markers. Without `--close`, unfinished work remains for inspection and the merge setting is still restored.

## Expected outcomes

Every stage uses the same factory PR. Each stage after s1 starts from a PR approved at its head, and ends that way. Fix rounds caused by the reviewer's judgement are allowed in s1 and are reported. Elsewhere they fail the run.

The issue has no `bug` or `enhancement` label, keeping the test focused on event handling. Enhancement issues also require test evidence in the PR description. The first attempt exposed a loop where the reviewer rejected evidence appended by the fixer; the follow-up below records its fix.

| Stage | The script | Expected |
|---|---|---|
| s1 | Opens an issue, *Add uncapitalize*, and adds `ready-for-agent`. | Implementation opens a PR from `agent/issue-N`. The review approves it with *ready for you to merge* and `Reviewed commit:` naming the PR's head. The PR stays open. No factory run fails or is cancelled. |
| s2 | Pushes a passing test to the approved PR. | **Factory · Review new commits** runs on `pull_request_target`. The factory removes `agent:approved` and adds `agent:review` before any new verdict. Exactly one verdict names the pushed commit, and the PR ends approved at it. |
| s3 | Pushes a test with a wrong expectation, waits until its review is running the agent, then pushes the corrected test. | The review that checked the failing commit posts *The PR changed since `<commit>` was checked. Discarded that result…* and no verdict. No request-changes verdict names that commit, `agent:changes-requested` is never added and no fix run starts, so no fix round is spent. The second push's handler is created at once but waits in the PR's queue until that review ends, then requests a review. Exactly one verdict names the corrected commit; the second review request stands down. The PR ends approved at the corrected commit and mergeable. |
| s4a | Merges a change to `smoke.txt` into the sandbox's default branch, then pushes a different `smoke.txt` to the PR. | The PR merges cleanly before the push and conflicts after it. The push handler still runs, though GitHub starts no `pull_request` workflows for the conflicting commit. The approval is cleared as in s2. Exactly one verdict names the conflicting commit. The PR ends approved, open and conflicting. With `FACTORY_MERGE` off there is no merge attempt, so the conflict starts no fix run. |
| s4b | Pushes a commit that restores `smoke.txt`, so the PR merges cleanly again. Waits until its review is running the agent, then pushes the conflicting `smoke.txt` again. | As s3: the stale review discards its result without a fix round, the conflicting push's handler waits for it and then runs, and exactly one verdict names the conflicting commit. The PR ends approved, open and conflicting. |

Every stage also checks that no review, fix or push-handler run failed or was cancelled. A cancelled run would mean the PR's queue dropped a pending job.

Still not covered live: a push in the narrow interval between the final head check and GitHub's merge request (the `--match-head-commit` guard), pushes during a fix run, and pushes to an assigned PR. m2 covers a push during the agent review, not that later merge-request race.

## Runs

The first complete-suite attempt passed m1 and m2. It stopped before m3 review because GitHub still reported the earlier clean mergeability immediately after the base fixture merged. The driver now confirms the conflict with local Git and waits for GitHub to report it, then dispatches review. Restoration and cleanup passed; m3 is rerun separately below.

### 2026-10-04 05:56 UTC, run 20261004-055123

jonbaldie/software-factory-sandbox at [`4e5ce3a`](https://github.com/jonbaldie/software-factory-sandbox/commit/4e5ce3a47943293c75a99603277a537e9eab264d), `run-agent@v1` at [`9f9db37`](https://github.com/jonbaldie/software-factory/commit/9f9db379e60b394eb62e55398ed5d1c67c231da0). PR [#89](https://github.com/jonbaldie/software-factory-sandbox/pull/89). 2 check(s) failed.

#### setup · Enable automatic merging for the reserved sandbox

- Original FACTORY_MERGE: None (None means unset)
- ✅ FACTORY_MERGE is true

#### m1 · A passing PR automatically merges at its reviewed head

- Opened [#85](https://github.com/jonbaldie/software-factory-sandbox/pull/85) at [`8fff99a`](https://github.com/jonbaldie/software-factory-sandbox/commit/8fff99a1a25b2eade8dfbb51552b3f6fb7a0643e), for [issue #84](https://github.com/jonbaldie/software-factory-sandbox/issues/84); local tests pass
- Factory runs: [Factory 2 · Review #68](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37181085848) (success)
- ✅ Merged head [`8fff99a`](https://github.com/jonbaldie/software-factory-sandbox/commit/8fff99a1a25b2eade8dfbb51552b3f6fb7a0643e) has one fresh approval after tests and agent review: [verdict](https://github.com/jonbaldie/software-factory-sandbox/pull/85#issuecomment-5977084117)
- ✅ The factory merged the expected PR head: [`8fff99a`](https://github.com/jonbaldie/software-factory-sandbox/commit/8fff99a1a25b2eade8dfbb51552b3f6fb7a0643e)
- ✅ Squash commit [`5bbb924`](https://github.com/jonbaldie/software-factory-sandbox/commit/5bbb92436523c9b118bb53277b778a48e22c25a5) is on `main` with exactly the reviewed tree
- ✅ All sandbox tests pass on `main` after the merge
- ✅ No fix round for 8fff99a: no request-changes verdict, no `agent:changes-requested`, no fix run
- ✅ No factory run failed or was cancelled (1 reviews ran the agent, 0 review requests stood down)

#### m2 · A passing push during review requires a fresh approval before merging

- Opened [#87](https://github.com/jonbaldie/software-factory-sandbox/pull/87) at [`7332440`](https://github.com/jonbaldie/software-factory-sandbox/commit/73324405c446963767f6b4762c42af96086f5a55), for [issue #86](https://github.com/jonbaldie/software-factory-sandbox/issues/86); local tests pass
- [Factory 2 · Review #69](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37181165460) (in_progress) is reviewing passing commit [`7332440`](https://github.com/jonbaldie/software-factory-sandbox/commit/73324405c446963767f6b4762c42af96086f5a55)
- Pushed [`ff03eef`](https://github.com/jonbaldie/software-factory-sandbox/commit/ff03eef8f2e6aec7c4965ed5d17fe34db52b6969): Merge smoke: replace the passing commit during review (tests pass locally)
- Factory runs: [Factory · Review new commits #10](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37181182717) (success), [Factory 2 · Review #69](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37181165460) (success), [Factory 2 · Review #70](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37181197486) (success), [Factory 2 · Review #71](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37181206344) (success)
- ✅ The stale and replacement reviews ran their agents; the duplicate request skipped its agent
- ✅ Review [Factory 2 · Review #69](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37181165460) (success) checked 7332440, then discarded its result ([comment](https://github.com/jonbaldie/software-factory-sandbox/pull/87#issuecomment-5977092072))
- ✅ The push handler ran for ff03eef: [Factory · Review new commits #10](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37181182717) (success)
- ✅ The second push's handler waited in the PR queue until [Factory 2 · Review #69](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37181165460) (in_progress) finished (25s)
- ✅ No fix round for 7332440: no request-changes verdict, no `agent:changes-requested`, no fix run
- ✅ Merged head [`ff03eef`](https://github.com/jonbaldie/software-factory-sandbox/commit/ff03eef8f2e6aec7c4965ed5d17fe34db52b6969) has one fresh approval after tests and agent review: [verdict](https://github.com/jonbaldie/software-factory-sandbox/pull/87#issuecomment-5977098848)
- ✅ The factory merged the expected PR head: [`ff03eef`](https://github.com/jonbaldie/software-factory-sandbox/commit/ff03eef8f2e6aec7c4965ed5d17fe34db52b6969)
- ✅ Squash commit [`993403b`](https://github.com/jonbaldie/software-factory-sandbox/commit/993403b716ab4ecfee5ee05eff636e38f1b91f69) is on `main` with exactly the reviewed tree
- ✅ All sandbox tests pass on `main` after the merge
- ✅ No factory run failed or was cancelled (2 reviews ran the agent, 1 review requests stood down)

#### m3 · A merge conflict is fixed, reviewed again and automatically merged

- Opened [#89](https://github.com/jonbaldie/software-factory-sandbox/pull/89) at [`67c1692`](https://github.com/jonbaldie/software-factory-sandbox/commit/67c16925d84480d46eaddf7d51ef9dfd78fbdf1e), for [issue #88](https://github.com/jonbaldie/software-factory-sandbox/issues/88); local tests pass
- Merged base fixture [#90](https://github.com/jonbaldie/software-factory-sandbox/pull/90) after [CI](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37181290393/job/111374236428)
- ❌ #89 conflicts before review (`clean`)
- ❌ Stopped: StageFailed: the conflict scenario did not create a conflict

#### restore · Restore the sandbox's original merge setting

- ✅ Restored FACTORY_MERGE to None

#### cleanup · Close temporary work and remove its branches

- ✅ Deleted `agent/issue-84`
- ✅ Deleted `agent/issue-86`
- ✅ Deleted `agent/issue-88`
- ✅ Deleted `smoke/merge-base-20261004-055123`

### 2026-10-04, merge-suite setup correction and interrupt recovery

The first attempt on [sandbox #83](https://github.com/jonbaldie/software-factory-sandbox/pull/83) put the conflict scenario's instructions in the clean-merge ticket too. The [reviewer](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37180899187) consequently requested a base-side update that m1 was not meant to make. The fixture tickets now describe only their own scenario, and the driver runs and reports `npm test` for fixture preparation and the merged base.

Stopped that attempt with SIGINT while the factory was running. The driver's `finally` restored the originally absent `FACTORY_MERGE`, closed [issue #82](https://github.com/jonbaldie/software-factory-sandbox/issues/82) and PR #83, waited for factory jobs, and deleted `agent/issue-82`. Nothing from that attempt merged into the sandbox base.

### 2026-10-03, factory follow-ups: both regressions verified live

[Sandbox #81](https://github.com/jonbaldie/software-factory-sandbox/pull/81) installed the templates from [software-factory #20](https://github.com/jonbaldie/software-factory/pull/20), with merging still off. Reopened the original enhancement PR [#76](https://github.com/jonbaldie/software-factory-sandbox/pull/76) to replay the failures:

- [Duplicate implementation](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37151493174) succeeded and skipped checkout, the agent and all later work. PR head `b5c71f42a443b11df2f89138701417c552b35816`, description, labels and issue state were unchanged.
- [Fix](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37151543531) appended the missing **Slices** evidence and corrected test count. It merged the current base; source, tests and README were unchanged.
- [Review](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37151617910) accepted the appended evidence and [approved](https://github.com/jonbaldie/software-factory-sandbox/pull/76#issuecomment-5973193577) commit [`0fc3650`](https://github.com/jonbaldie/software-factory-sandbox/commit/0fc365055e28bb72d62dc49a239bcc3305edcff2). All 133 sandbox tests passed.

The local suite passes 75 scenarios, including regressions for duplicate implementation and description-only fixes without a commit. PR #76 was closed again after verification. Smoke PR #78 and issue #77 are closed, the temporary branches are deleted, and `smoke.txt` remains on the sandbox's main branch.

### 2026-10-03 20:21 UTC, run 20261003-201804

jonbaldie/software-factory-sandbox at [`1348f4c`](https://github.com/jonbaldie/software-factory-sandbox/commit/1348f4cb053eb714cf27eec1118ab933ed8a0d37), `run-agent@v1` at [`c17f716`](https://github.com/jonbaldie/software-factory/commit/c17f7168d7a5402a5eb2f27c880135a52daae9f6). PR [#78](https://github.com/jonbaldie/software-factory-sandbox/pull/78). All checks passed.

#### s4b · A push during a review that introduces a merge conflict discards the verdict

- Pushed [`d53f6ae`](https://github.com/jonbaldie/software-factory-sandbox/commit/d53f6aeb7fdaa6caebe7118dac35e1fb787a531d): Restore smoke.txt, resolving the conflict (tests pass locally)
- [Factory 2 · Review #62](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37151062844) (in_progress) is running its agent on d53f6ae
- Pushed [`146e364`](https://github.com/jonbaldie/software-factory-sandbox/commit/146e364460211290df0ea8f43365caf3ea4dcf33): Edit smoke.txt so it conflicts with main again (tests pass locally)
- Factory runs: [Factory · Review new commits #8](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37151054750) (success), [Factory · Review new commits #9](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37151119270) (success), [Factory 2 · Review #62](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37151062844) (success), [Factory 2 · Review #63](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37151181646) (success), [Factory 2 · Review #64](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37151191702) (success)
- ✅ The push handler ran for d53f6ae: [Factory · Review new commits #8](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37151054750) (success)
- ✅ #78 ends approved and open at [`146e364`](https://github.com/jonbaldie/software-factory-sandbox/commit/146e364460211290df0ea8f43365caf3ea4dcf33) (labels: agent:approved)
- ✅ GitHub reports #78 conflicting (`dirty`)
- ✅ The stale and replacement reviews ran their agents; the duplicate request skipped its agent
- ✅ Review [Factory 2 · Review #62](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37151062844) (success) checked d53f6ae, then discarded its result ([comment](https://github.com/jonbaldie/software-factory-sandbox/pull/78#issuecomment-5973121072))
- ✅ No fix round for d53f6ae: no request-changes verdict, no `agent:changes-requested`, no fix run
- ✅ The push handler ran for 146e364 despite the conflict: [Factory · Review new commits #9](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37151119270) (success)
- ✅ The second push's handler waited in the PR queue until [Factory 2 · Review #62](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37151062844) (success) finished (67s)
- ✅ One review verdict names 146e364: [approve](https://github.com/jonbaldie/software-factory-sandbox/pull/78#issuecomment-5973130990)
- ✅ No fix round for 146e364: no request-changes verdict, no `agent:changes-requested`, no fix run
- ✅ No factory run failed or was cancelled (2 reviews ran the agent, 1 review requests stood down)

Resumed with `--pr 78 --stages s4b --close` after tightening the driver’s assertions. All 11 checks passed; cleanup closed both PR #78 and issue #77.

### 2026-10-03, `v1.8.1`: all checks passed

The sandbox ran the `v1` templates at [`c17f716`](https://github.com/jonbaldie/software-factory/commit/c17f7168d7a5402a5eb2f27c880135a52daae9f6), installed by [sandbox#74](https://github.com/jonbaldie/software-factory-sandbox/pull/74). All 35 checks passed on PR [#78](https://github.com/jonbaldie/software-factory-sandbox/pull/78) over two invocations. s1 to s3 ran first. That invocation merged [#79](https://github.com/jonbaldie/software-factory-sandbox/pull/79), s4a's base change, then stopped because the session's GitHub proxy refused to delete #79's branch; that cleanup is now best effort. s4a and s4b then resumed with `--pr 78 --stages s4a,s4b`.

#### s1 · A factory PR is approved with FACTORY_MERGE off

- Opened [#77](https://github.com/jonbaldie/software-factory-sandbox/issues/77) with `ready-for-agent`
- The factory opened [#78](https://github.com/jonbaldie/software-factory-sandbox/pull/78) from `agent/issue-77`
- Factory runs: [Factory 2 · Review #53](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37148589677) (success)
- ✅ Implementation succeeded: [Factory 1 · Implement #64](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37148520781) (success)
- ✅ No factory run failed or was cancelled (1 reviews ran the agent, 0 review requests stood down)
- ✅ Approved at the head, [`3d172b6`](https://github.com/jonbaldie/software-factory-sandbox/commit/3d172b614a097be94d81d13201bca15f46d0e9a7): [verdict](https://github.com/jonbaldie/software-factory-sandbox/pull/78#issuecomment-5972800444)
- ✅ The approval leaves the PR for a person to merge, and it is still open

#### s2 · A push to an approved PR clears the approval and starts a new review

- Pushed [`f2eeb6d`](https://github.com/jonbaldie/software-factory-sandbox/commit/f2eeb6d3b548c9e7d6a1e38e41cbe90654bcb32c): Test uncapitalize with a leading digit (tests pass locally)
- Factory runs: [Factory · Review new commits #2](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37148735936) (success), [Factory 2 · Review #54](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37148744227) (success)
- ✅ The push handler ran for f2eeb6d: [Factory · Review new commits #2](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37148735936) (success)
- ✅ #78 ends approved and open at [`f2eeb6d`](https://github.com/jonbaldie/software-factory-sandbox/commit/f2eeb6d3b548c9e7d6a1e38e41cbe90654bcb32c) (labels: agent:approved)
- ✅ GitHub reports #78 mergeable (`clean`)
- ✅ The factory removed `agent:approved` and added `agent:review` before the new verdict
- ✅ One review verdict names f2eeb6d: [approve](https://github.com/jonbaldie/software-factory-sandbox/pull/78#issuecomment-5972814994)
- ✅ No factory run failed or was cancelled (1 reviews ran the agent, 0 review requests stood down)

#### s3 · A push during a review discards its verdict without spending a fix round

- Pushed [`5808cc2`](https://github.com/jonbaldie/software-factory-sandbox/commit/5808cc2c3febc59b05b272008c1b268375ddeddd): Test uncapitalize on all-caps input, with the wrong expectation (tests fail locally)
- [Factory 2 · Review #55](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37148858926) (in_progress) is running its agent on 5808cc2
- Pushed [`ddfbf74`](https://github.com/jonbaldie/software-factory-sandbox/commit/ddfbf74e0d53120c1dac3dce4da06f0f083f1424): Correct the all-caps uncapitalize test (tests pass locally)
- Factory runs: [Factory · Review new commits #3](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37148852975) (success), [Factory · Review new commits #4](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37148879939) (success), [Factory 2 · Review #55](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37148858926) (success), [Factory 2 · Review #56](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37148915554) (success), [Factory 2 · Review #57](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37148924601) (success)
- ✅ The push handler ran for 5808cc2: [Factory · Review new commits #3](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37148852975) (success)
- ✅ #78 ends approved and open at [`ddfbf74`](https://github.com/jonbaldie/software-factory-sandbox/commit/ddfbf74e0d53120c1dac3dce4da06f0f083f1424) (labels: agent:approved)
- ✅ GitHub reports #78 mergeable (`clean`)
- ✅ Review [Factory 2 · Review #55](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37148858926) (success) checked 5808cc2, then discarded its result ([comment](https://github.com/jonbaldie/software-factory-sandbox/pull/78#issuecomment-5972824952))
- ✅ No fix round for 5808cc2: no request-changes verdict, no `agent:changes-requested`, no fix run
- ✅ The push handler ran for ddfbf74: [Factory · Review new commits #4](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37148879939) (success)
- ✅ The second push's handler waited in the PR queue until [Factory 2 · Review #55](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37148858926) (success) finished (38s)
- ✅ One review verdict names ddfbf74: [approve](https://github.com/jonbaldie/software-factory-sandbox/pull/78#issuecomment-5972834267)
- ✅ No factory run failed or was cancelled (2 reviews ran the agent, 1 review requests stood down)

#### s4a · A push that introduces a merge conflict clears the approval and starts a new review

- Merged [#80](https://github.com/jonbaldie/software-factory-sandbox/pull/80) into `main`, changing `smoke.txt` again, after [#79](https://github.com/jonbaldie/software-factory-sandbox/pull/79) had already done so. A stale fetch, since fixed, missed #79.
- Couldn't delete `smoke/base-20261003-194557`, so delete it by hand
- Pushed [`9325915`](https://github.com/jonbaldie/software-factory-sandbox/commit/9325915d3099872db099b64c6cd9f26458901ee8): Edit smoke.txt so it conflicts with main (tests pass locally)
- Factory runs: [Factory · Review new commits #5](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37149151939) (success), [Factory 2 · Review #58](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37149160796) (success)
- `pull_request` workflow runs for 9325915: 0. GitHub skips them while a PR conflicts.
- ✅ #78 still merges cleanly after the base change (`clean`)
- ✅ The push handler ran for 9325915 despite the conflict: [Factory · Review new commits #5](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37149151939) (success)
- ✅ #78 ends approved and open at [`9325915`](https://github.com/jonbaldie/software-factory-sandbox/commit/9325915d3099872db099b64c6cd9f26458901ee8) (labels: agent:approved)
- ✅ GitHub reports #78 conflicting (`dirty`)
- ✅ The factory removed `agent:approved` and added `agent:review` before the new verdict
- ✅ One review verdict names 9325915: [approve](https://github.com/jonbaldie/software-factory-sandbox/pull/78#issuecomment-5972863058)
- ✅ No factory run failed or was cancelled (1 reviews ran the agent, 0 review requests stood down)

#### s4b · A push during a review that introduces a merge conflict discards the verdict

- Pushed [`c5a8e32`](https://github.com/jonbaldie/software-factory-sandbox/commit/c5a8e320ffc9de46021894e8f0e4015b4608f983): Restore smoke.txt, resolving the conflict (tests pass locally)
- [Factory 2 · Review #59](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37149252063) (in_progress) is running its agent on c5a8e32
- Pushed [`61346a7`](https://github.com/jonbaldie/software-factory-sandbox/commit/61346a7f249ee9bcfa24abcc2be7f634d1e25ca1): Edit smoke.txt so it conflicts with main again (tests pass locally)
- Factory runs: [Factory · Review new commits #6](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37149245017) (success), [Factory · Review new commits #7](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37149272860) (success), [Factory 2 · Review #59](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37149252063) (success), [Factory 2 · Review #60](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37149306640) (success), [Factory 2 · Review #61](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37149315101) (success)
- ✅ The push handler ran for c5a8e32: [Factory · Review new commits #6](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37149245017) (success)
- ✅ #78 ends approved and open at [`61346a7`](https://github.com/jonbaldie/software-factory-sandbox/commit/61346a7f249ee9bcfa24abcc2be7f634d1e25ca1) (labels: agent:approved)
- ✅ GitHub reports #78 conflicting (`dirty`)
- ✅ Review [Factory 2 · Review #59](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37149252063) (success) checked c5a8e32, then discarded its result ([comment](https://github.com/jonbaldie/software-factory-sandbox/pull/78#issuecomment-5972873822))
- ✅ No fix round for c5a8e32: no request-changes verdict, no `agent:changes-requested`, no fix run
- ✅ The push handler ran for 61346a7 despite the conflict: [Factory · Review new commits #7](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37149272860) (success)
- ✅ The second push's handler waited in the PR queue until [Factory 2 · Review #59](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37149252063) (success) finished (42s)
- ✅ One review verdict names 61346a7: [approve](https://github.com/jonbaldie/software-factory-sandbox/pull/78#issuecomment-5972880499)
- ✅ No factory run failed or was cancelled (2 reviews ran the agent, 1 review requests stood down)

### 2026-10-03, `v1.8.1`: stopped at s2 on review judgement

The first attempt, on PR [#76](https://github.com/jonbaldie/software-factory-sandbox/pull/76) from [#75](https://github.com/jonbaldie/software-factory-sandbox/issues/75), had the issue labelled `enhancement`. It found a duplicate implementation risk and a description-review loop in the factory; the test driver worked around both for the next run:

- ✅ s1: [Implement #61](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37147718521) opened the PR, and [Review #49](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37147882051) [approved it](https://github.com/jonbaldie/software-factory-sandbox/pull/76#issuecomment-5972706485), leaving it for a person to merge.
- ❌ s1: the issue was created with `enhancement`, and `ready-for-agent` was added a second later. GitHub announced `ready-for-agent` twice, which queued [Implement #62](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37147720001). It was cancelled before it started. A second run would have started over from the base branch and force-pushed over the open PR with `GITHUB_TOKEN`, which starts no push handler. The script now adds the label after creating the issue.
- ✅ s2: the push of [`b5c71f4`](https://github.com/jonbaldie/software-factory-sandbox/commit/b5c71f42a443b11df2f89138701417c552b35816) started [Review new commits #1](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37147976725). It cleared the approval, and [Review #50](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37147985500) checked the new head.
- ❌ s2: the enhancement method's reviewer [requested changes](https://github.com/jonbaldie/software-factory-sandbox/pull/76#issuecomment-5972719660) because the pushed test wasn't in the description's **Slices** list. Fix runs [#20](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37148066790) and [#21](https://github.com/jonbaldie/software-factory-sandbox/actions/runs/37148257435) changed no files and could only append notes to the description. The reviewer rejected the same commit [twice more](https://github.com/jonbaldie/software-factory-sandbox/pull/76#issuecomment-5972763650), and the PR went to `ready-for-human`. The smoke test now uses an uncategorised issue. At that point a fix round could not satisfy a request to change the description itself; the follow-up above resolves this.
