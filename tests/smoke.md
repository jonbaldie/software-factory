# Push smoke test

`tests/labels.py` checks each job's label changes against a fake `gh`. It can't check what GitHub does around those jobs: which events start a workflow, how the per-PR queue orders the review, fix and push-handler jobs, and whether `pull_request_target` still fires when a push makes the PR conflict with its base. `tests/smoke.py` checks those on the [sandbox](https://github.com/jonbaldie/software-factory-sandbox) with real GitHub Actions runs.

Run it after changing how review, fix or the push handler are triggered, queued or invalidated. It spends model credit on one implement run and about seven reviews, so CI doesn't run it.

## Run it

1. Install the version under test in the sandbox and merge it to the sandbox's default branch. The workflows only run from there.
2. Leave `FACTORY_MERGE` unset in the sandbox. The script stops if it can read the variable and it is `true`.
3. Sign in with `gh` as someone with write access to the sandbox, and let git push to it over HTTPS (`gh auth setup-git`).
4. From this repository:

   ```sh
   uv run tests/smoke.py --report smoke-report.md
   ```

It takes 30 to 45 minutes. Each check prints `PASS` or `FAIL` as it completes. At the end the script prints a Markdown report with the commit, run and comment links, and exits non-zero if any check failed. Add the report to [Runs](#runs).

To continue after a stop, pass the approved PR and the remaining stages, for example `--pr 76 --stages s3,s4a,s4b`. s4b continues from s4a's conflict. The PR and its issue stay open for inspection; close them afterwards, or pass `--close`.

## Expected outcomes

Every stage uses the same factory PR. Each stage after s1 starts from a PR approved at its head, and ends that way. Fix rounds caused by the reviewer's judgement are allowed in s1 and are reported. Elsewhere they fail the run.

| Stage | The script | Expected |
|---|---|---|
| s1 | Opens an `enhancement` issue, *Add uncapitalize*, and adds `ready-for-agent`. | Implementation opens a PR from `agent/issue-N`. The review approves it with *ready for you to merge* and `Reviewed commit:` naming the PR's head. The PR stays open. No factory run fails or is cancelled. |
| s2 | Pushes a passing test to the approved PR. | **Factory · Review new commits** runs on `pull_request_target`. The factory removes `agent:approved` and adds `agent:review` before any new verdict. Exactly one verdict names the pushed commit, and the PR ends approved at it. |
| s3 | Pushes a test with a wrong expectation, waits until its review is running the agent, then pushes the corrected test. | The review that checked the failing commit posts *The PR changed since `<commit>` was checked. Discarded that result…* and no verdict. No request-changes verdict names that commit, `agent:changes-requested` is never added and no fix run starts, so no fix round is spent. The second push's handler is created at once but waits in the PR's queue until that review ends, then requests a review. Exactly one verdict names the corrected commit; the second review request stands down. The PR ends approved at the corrected commit and mergeable. |
| s4a | Merges a change to `smoke.txt` into the sandbox's default branch, then pushes a different `smoke.txt` to the PR. | The PR merges cleanly before the push and conflicts after it. The push handler still runs, though GitHub starts no `pull_request` workflows for the conflicting commit. The approval is cleared as in s2. Exactly one verdict names the conflicting commit. The PR ends approved, open and conflicting. With `FACTORY_MERGE` off there is no merge attempt, so the conflict starts no fix run. |
| s4b | Pushes a commit that restores `smoke.txt`, so the PR merges cleanly again. Waits until its review is running the agent, then pushes the conflicting `smoke.txt` again. | As s3: the stale review discards its result without a fix round, the conflicting push's handler waits for it and then runs, and exactly one verdict names the conflicting commit. The PR ends approved, open and conflicting. |

Every stage also checks that no review, fix or push-handler run failed or was cancelled. A cancelled run would mean the PR's queue dropped a pending job.

Not covered: pushes with `FACTORY_MERGE` on, where `--match-head-commit` must stop a merge of an unreviewed head; pushes during a fix run; and pushes to an assigned PR.

## Runs
