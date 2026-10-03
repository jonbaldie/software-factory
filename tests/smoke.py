# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Smoke-tests the factory's push handling on a live sandbox repository, using real GitHub Actions.

tests/labels.py simulates GitHub. This drives the installed workflows instead, so it also checks GitHub's
event delivery and the per-PR job queue. It spends model credit on one implement run and about seven
reviews, and takes about 15 minutes.

Every stage runs on the same factory PR:
  s1   A ready-for-agent issue becomes a PR, which the reviewer approves and leaves open: FACTORY_MERGE is off.
  s2   A push to the approved PR clears the approval, and a new review checks the new head.
  s3   A push during a review discards that review's verdict without spending a fix round. The commit it
       replaces fails its tests, so a kept verdict would have requested changes.
  s4a  As s2, but the push introduces a merge conflict with the base branch.
  s4b  As s3, but the push introduces a merge conflict with the base branch.

The expected outcomes, and the record of past runs, are in tests/smoke.md.

The pushed commits are written for jonbaldie/software-factory-sandbox, a small Node library. s4a merges a
change to `smoke.txt` into the base branch, so that the PR's later edits to that file conflict with it.

Needs gh signed in with write access to the sandbox, git able to push to it over HTTPS (`gh auth setup-git`),
and the factory installed there with FACTORY_MERGE unset. Only REST calls are used.

Usage: uv run tests/smoke.py [--repo OWNER/NAME] [--pr N] [--stages s2,s3] [--report FILE] [--close]
"""
import argparse, json, os, re, shutil, subprocess, sys, tempfile, time
from datetime import datetime, timedelta, timezone

BOT = "github-actions[bot]"
PUSH, REVIEW, FIX, IMPLEMENT = "factory-review-push.yml", "factory-review.yml", "factory-fix.yml", "factory-implement.yml"
AGENT_STEP = "Agent reviews the change"
SMOKE_FILE = "smoke.txt"
TESTS = "test/textkit.test.js"
STAGES = ["s1", "s2", "s3", "s4a", "s4b"]
MARGIN = timedelta(seconds=5)  # allows for clock skew against GitHub's timestamps
FAILED_LABELS = {"agent:failed", "ready-for-human"}

ISSUE_TITLE = "Add uncapitalize"
ISSUE_BODY = """\
Add `uncapitalize(input)` to `src/textkit.js`, the mirror of `capitalize`: it lowercases the first Unicode code point \
and leaves the rest of the string unchanged. It does not trim. An empty string returns an empty string.

```js
uncapitalize('Hello World'); // "hello World"
uncapitalize('HELLO');       // "hELLO"
uncapitalize('');            // ""
```

## Smoke test

This issue drives software-factory's push smoke test (`tests/smoke.py`). While the PR is open, a maintainer will push \
commits to it: more `uncapitalize` tests, and edits to `smoke.txt` that conflict with the base branch on purpose. \
Those commits are part of this change, so review them with it. Implementers: don't create or edit `smoke.txt`.
"""
WRONG = "assert.equal(uncapitalize('HELLO'), 'hello');"
RIGHT = "assert.equal(uncapitalize('HELLO'), 'hELLO');"


class StageFailed(Exception):
    pass


def log(msg):
    print(f"{datetime.now(timezone.utc):%H:%M:%S} {msg}", flush=True)


def now():
    return datetime.now(timezone.utc)


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def when(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def run(*cmd, cwd=None, check=True):
    p = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    if check and p.returncode:
        raise RuntimeError(f"{' '.join(cmd)} failed:\n{p.stderr.strip()}")
    return p


def wait(what, probe, timeout, every=10):
    log(f"waiting for {what}")
    deadline = time.time() + timeout
    while True:
        found = probe()
        if found:
            return found
        if time.time() > deadline:
            raise StageFailed(f"timed out after {timeout // 60} minutes waiting for {what}")
        time.sleep(every)


class GitHub:
    def __init__(self, repo):
        self.repo = repo

    def call(self, method, path, fields=(), jq=None, paginate=False):
        cmd = ["gh", "api", "-X", method, path if path.startswith("repos/") else f"repos/{self.repo}/{path}"]
        if paginate:
            cmd.append("--paginate")
        if jq:
            cmd += ["--jq", jq]
        for key, value in fields:
            cmd += ["-f", f"{key}={value}"]
        for attempt in range(4):
            p = run(*cmd, check=False)
            if p.returncode == 0:
                return p.stdout
            # Writes aren't retried, since a request that timed out may still have happened.
            if method != "GET" or attempt == 3:
                raise RuntimeError(f"gh api {method} {path} failed:\n{p.stderr.strip()}")
            time.sleep(5 * (attempt + 1))

    def get(self, path):
        return json.loads(self.call("GET", path))

    def items(self, path, key="."):
        out = self.call("GET", path, jq=f"{key}[]", paginate=True)
        return [json.loads(line) for line in out.splitlines() if line]

    def post(self, path, **fields):
        flat = []
        for key, value in fields.items():
            flat += [(f"{key}[]", v) for v in value] if isinstance(value, list) else [(key, value)]
        return json.loads(self.call("POST", path, flat) or "null")

    def pr(self, n):
        return self.get(f"pulls/{n}")

    def labels(self, n):
        return {label["name"] for label in self.items(f"issues/{n}/labels?per_page=100")}

    def comments(self, n, since):
        found = self.items(f"issues/{n}/comments?per_page=100&since={iso(since)}")
        return [c for c in found if when(c["created_at"]) >= since]

    def events(self, n, since):
        return [e for e in self.items(f"issues/{n}/events?per_page=100") if when(e["created_at"]) >= since]

    def runs(self, workflow, since):
        found = self.items(f"actions/workflows/{workflow}/runs?per_page=100&created=%3E%3D{iso(since)}", ".workflow_runs")
        return sorted(found, key=lambda r: (r["created_at"], r["id"]))

    def job(self, run_id):
        jobs = self.items(f"actions/runs/{run_id}/jobs?per_page=100", ".jobs")
        return jobs[0] if jobs else None

    def mergeable(self, n):
        def probe():
            pr = self.pr(n)
            return pr if pr["mergeable"] is not None else None
        pr = wait(f"GitHub to work out whether #{n} can merge", probe, 300, every=5)
        return pr["mergeable"], pr["mergeable_state"]


def step(job, name):
    return next((s for s in (job or {}).get("steps", []) if s["name"] == name), None)


class Clone:
    """A local clone of the sandbox, for the pushes a person would make."""

    def __init__(self, repo, path, trailers):
        self.path, self.trailers = path, trailers
        if not os.path.isdir(os.path.join(path, ".git")):
            run("git", "clone", "--quiet", f"https://github.com/{repo}.git", path)

    def git(self, *args, check=True):
        return run("git", *args, cwd=self.path, check=check)

    def fetch(self, branch):
        self.git("fetch", "--quiet", "origin", f"+refs/heads/{branch}:refs/remotes/origin/{branch}")

    def checkout(self, branch, start=None):
        self.fetch(start or branch)
        self.git("checkout", "--quiet", "-B", branch, f"origin/{start or branch}")

    def read(self, name, rev=None):
        if rev:
            p = self.git("show", f"{rev}:{name}", check=False)
            return p.stdout if p.returncode == 0 else None
        path = os.path.join(self.path, name)
        return open(path).read() if os.path.exists(path) else None

    def commit(self, message, files):
        for name, content in files.items():
            path = os.path.join(self.path, name)
            if content is None:
                if os.path.exists(path):
                    os.remove(path)
            else:
                with open(path, "w") as f:
                    f.write(content)
        self.git("add", "-A")
        self.git("commit", "--quiet", "-m", message, *[f"--trailer={t}" for t in self.trailers])
        return self.git("rev-parse", "HEAD").stdout.strip()

    def push(self, branch):
        self.git("push", "--quiet", "origin", f"HEAD:refs/heads/{branch}")

    def conflicts(self, ours, theirs):
        p = self.git("merge-tree", "--write-tree", ours, theirs, check=False)
        # A conflict exits 1 too, but only an error writes to stderr.
        if p.returncode not in (0, 1) or p.stderr.strip():
            raise RuntimeError(f"git merge-tree failed:\n{p.stderr.strip()}")
        return p.returncode == 1

    def tests_pass(self):
        """Runs the sandbox's tests at HEAD, or returns None without Node."""
        if not shutil.which("node"):
            return None
        return run("node", "--test", cwd=self.path, check=False).returncode == 0


class Report:
    def __init__(self):
        self.stages, self.failures = [], 0

    def stage(self, key, title):
        self.current = {"key": key, "title": title, "lines": [], "checks": []}
        self.stages.append(self.current)
        log(f"=== {key}: {title}")

    def note(self, text):
        self.current["lines"].append(text)
        log(text)

    def check(self, ok, text):
        self.current["checks"].append((ok, text))
        self.failures += not ok
        log(f"{'PASS' if ok else 'FAIL'} {text}")
        return ok

    def markdown(self, header):
        out = [header]
        for s in self.stages:
            out += ["", f"#### {s['key']} · {s['title']}", ""]
            out += [f"- {line}" for line in s["lines"]]
            out += [f"- {'✅' if ok else '❌'} {text}" for ok, text in s["checks"]]
        return "\n".join(out) + "\n"


class Smoke:
    def __init__(self, gh, clone, report, stamp):
        self.gh, self.clone, self.report, self.stamp = gh, clone, report, stamp
        self.base = gh.get(f"repos/{gh.repo}")["default_branch"]
        self.pr = self.issue = self.branch = None

    # ---- links ----
    def commit_link(self, sha):
        return f"[`{sha[:7]}`](https://github.com/{self.gh.repo}/commit/{sha})"

    def run_link(self, r):
        return f"[{r['name']} #{r['run_number']}]({r['html_url']}) ({r['conclusion'] or r['status']})"

    # ---- reading the PR ----
    def verdicts(self, since):
        """The factory's review results since a time: approve, request_changes, or discarded."""
        out = []
        for c in self.gh.comments(self.pr, since):
            if c["user"]["login"] != BOT:
                continue
            body, kind = c["body"], None
            if body.startswith("<!-- factory:review "):
                kind = body.split()[2]
                sha = re.search(r"Reviewed commit: `([0-9a-f]{40})`", body)
            elif body.startswith("The PR changed since `"):
                kind = "discarded"
                sha = re.match(r"The PR changed since `([0-9a-f]{40})`", body)
            if kind:
                run_id = re.search(r"/actions/runs/(\d+)", body)
                out.append({"kind": kind, "sha": sha and sha[1], "run": run_id and int(run_id[1]),
                            "url": c["html_url"], "at": when(c["created_at"]), "body": body})
        return out

    def factory_runs(self, since):
        return [r for wf in (PUSH, REVIEW, FIX) for r in self.gh.runs(wf, since)]

    def settle(self, since, timeout=45 * 60):
        """Waits until no factory run is pending and the PR is approved at its head, or handed to a person."""
        def probe():
            if any(r["status"] != "completed" for r in self.factory_runs(since)):
                return None
            labels = self.gh.labels(self.pr)
            if labels & FAILED_LABELS:
                return labels
            current = self.gh.pr(self.pr)["head"]["sha"]
            approvals = [v for v in self.verdicts(since) if v["kind"] == "approve"]
            if "agent:approved" in labels and approvals and approvals[-1]["sha"] == current:
                return labels
            return None
        return wait(f"#{self.pr} to settle", probe, timeout, every=15)

    def require_approved(self):
        pr = self.gh.pr(self.pr)
        labels = self.gh.labels(self.pr)
        approvals = [v for v in self.verdicts(when(pr["created_at"])) if v["kind"] == "approve"]
        if pr["state"] != "open" or "agent:approved" not in labels or not approvals or approvals[-1]["sha"] != pr["head"]["sha"]:
            raise StageFailed(f"#{self.pr} must be open and approved at its head before this stage (labels: {sorted(labels)})")
        return pr

    # ---- acting like a person ----
    def push(self, message, files, conflict=False, passing=True):
        self.clone.checkout(self.branch)
        self.clone.fetch(self.base)
        sha = self.clone.commit(message, files)
        if self.clone.conflicts(sha, f"origin/{self.base}") != conflict:
            raise StageFailed(f"{sha[:7]} should {'' if conflict else 'not '}conflict with {self.base}")
        tests = self.clone.tests_pass()
        if tests is not None and tests != passing:
            raise StageFailed(f"{sha[:7]}'s tests should {'pass' if passing else 'fail'}")
        at = now() - MARGIN
        self.clone.push(self.branch)
        self.report.note(f"Pushed {self.commit_link(sha)}: {message.splitlines()[0]}"
                         + ("" if tests is None else f" (tests {'pass' if tests else 'fail'} locally)"))
        return sha, at

    def tests_with(self, name, line):
        self.clone.checkout(self.branch)
        text = self.clone.read(TESTS)
        if not re.search(r"import \{[^}]*\buncapitalize\b[^}]*\} from '\.\./src/textkit\.js'", text):
            raise StageFailed(f"{TESTS} doesn't import uncapitalize")
        return text.rstrip("\n") + f"\n\ntest('{name}', () => {{\n  {line}\n}});\n"

    def smoke_text(self, side):
        return f"{side}: written by software-factory tests/smoke.py run {self.stamp} to conflict with the other branch.\n"

    def change_base(self):
        """Merges a change to smoke.txt into the base branch, which the PR's later edits conflict with."""
        branch = f"smoke/base-{self.stamp}"
        self.clone.checkout(branch, start=self.base)
        sha = self.clone.commit(f"Smoke test: change {SMOKE_FILE} on {self.base}", {SMOKE_FILE: self.smoke_text(f"Base branch, {self.base}")})
        self.clone.push(branch)
        pr = self.gh.post("pulls", title=f"Smoke test: change {SMOKE_FILE} on {self.base}", head=branch, base=self.base,
                          body=f"Sets up the merge conflict for software-factory's push smoke test on #{self.pr}.")

        def merged():
            p = run("gh", "api", "-X", "PUT", f"repos/{self.gh.repo}/pulls/{pr['number']}/merge",
                    "-f", "merge_method=squash", "-f", f"sha={sha}", check=False)
            return p.returncode == 0
        wait(f"#{pr['number']} to merge into {self.base}", merged, 15 * 60, every=15)
        self.report.note(f"Merged [#{pr['number']}]({pr['html_url']}) into `{self.base}`, changing `{SMOKE_FILE}`")
        try:
            self.gh.call("DELETE", f"git/refs/heads/{branch}")
        except RuntimeError:
            if self.clone.git("push", "--quiet", "origin", "--delete", branch, check=False).returncode:
                self.report.note(f"Couldn't delete `{branch}`, so delete it by hand")

    def merge_base(self):
        self.clone.checkout(self.branch)
        self.clone.fetch(self.base)
        return self.clone.git("merge-base", "HEAD", f"origin/{self.base}").stdout.strip()

    # ---- waiting on the factory ----
    def handler(self, since):
        def probe():
            done = [r for r in self.gh.runs(PUSH, since) if r["event"] == "pull_request_target"]
            return done[0] if done and done[0]["status"] == "completed" else None
        return wait("the push handler", probe, 30 * 60, every=5)

    def running_review(self, since):
        """The review run that is part-way through its agent step, so a push now lands mid-review."""
        def probe():
            for r in self.gh.runs(REVIEW, since):
                agent = step(self.gh.job(r["id"]), AGENT_STEP)
                if agent and agent["status"] == "in_progress":
                    return r
                if agent and agent["conclusion"] == "success":
                    raise StageFailed(f"review {r['html_url']} finished its agent step before the push could land")
            return None
        return wait("a review to reach its agent step", probe, 30 * 60, every=3)

    # ---- checks shared by the stages ----
    def check_handler(self, h, sha, note=""):
        job = self.gh.job(h["id"])
        ok = h["conclusion"] == "success" and job and job["conclusion"] == "success" and \
            (step(job, "Invalidate approval and request a review") or {}).get("conclusion") == "success"
        self.report.check(ok, f"The push handler ran for {sha[:7]}{note}: {self.run_link(h)}")

    def check_approval_cleared(self, since, sha):
        events = self.gh.events(self.pr, since)
        first = min((v["at"] for v in self.verdicts(since) if v["sha"] == sha), default=now())
        cleared = [e for e in events if e["event"] == "unlabeled" and e["label"]["name"] == "agent:approved"
                   and e["actor"]["login"] == BOT and when(e["created_at"]) <= first]
        queued = [e for e in events if e["event"] == "labeled" and e["label"]["name"] == "agent:review"
                  and e["actor"]["login"] == BOT and when(e["created_at"]) <= first]
        self.report.check(bool(cleared and queued), "The factory removed `agent:approved` and added `agent:review` before the new verdict")

    def check_reviewed(self, since, sha):
        named = [v for v in self.verdicts(since) if v["sha"] == sha and v["kind"] != "discarded"]
        self.report.check(len(named) == 1, f"One review verdict names {sha[:7]}: "
                          + ", ".join(f"[{v['kind']}]({v['url']})" for v in named))

    def check_discarded(self, since, review, sha):
        found = [v for v in self.verdicts(since) if v["run"] == review["id"]]
        ok = bool(found) and all(v["kind"] == "discarded" and v["sha"] == sha for v in found)
        self.report.check(ok, f"Review {self.run_link(review)} checked {sha[:7]}, then discarded its result"
                          + "".join(f" ([comment]({v['url']}))" for v in found))

    def check_no_round(self, since, sha, until):
        rounds = [v for v in self.verdicts(since) if v["kind"] == "request_changes" and v["sha"] == sha]
        labelled = [e for e in self.gh.events(self.pr, since) if e["event"] == "labeled"
                    and e["label"]["name"] == "agent:changes-requested" and when(e["created_at"]) <= until]
        fixes = [r for r in self.gh.runs(FIX, since) if when(r["created_at"]) <= until]
        self.report.check(not rounds and not labelled and not fixes,
                          f"No fix round for {sha[:7]}: no request-changes verdict, no `agent:changes-requested`, no fix run")

    def check_queued(self, h, review):
        """The handler for a push mid-review is created at once, but waits in the PR's queue for the review to end."""
        ran = self.gh.job(review["id"])
        acted = step(self.gh.job(h["id"]), "Invalidate approval and request a review")
        ok = bool(ran and acted) and when(h["created_at"]) < when(ran["completed_at"]) <= when(acted["started_at"])
        self.report.check(ok, f"The second push's handler waited in the PR queue until {self.run_link(review)} finished"
                          + (f" ({(when(acted['started_at']) - when(h['created_at'])).seconds}s)" if ok else ""))

    def check_runs_clean(self, since):
        runs = self.factory_runs(since)
        bad = [r for r in runs if r["conclusion"] not in ("success", "skipped")]
        reviewed = [r for r in runs if r["path"].endswith(REVIEW)
                    and (step(self.gh.job(r["id"]), AGENT_STEP) or {}).get("conclusion") == "success"]
        skipped = [r for r in runs if r["path"].endswith(REVIEW) and r not in reviewed]
        self.report.note("Factory runs: " + ", ".join(self.run_link(r) for r in runs))
        self.report.check(not bad, f"No factory run failed or was cancelled ({len(reviewed)} reviews ran the agent, "
                          f"{len(skipped)} review requests stood down)")

    def check_settled(self, since, sha, conflicting=False):
        labels = self.settle(since)
        pr = self.gh.pr(self.pr)
        self.report.check("agent:approved" in labels and pr["head"]["sha"] == sha and pr["state"] == "open" and not pr["merged"],
                          f"#{self.pr} ends approved and open at {self.commit_link(pr['head']['sha'])} "
                          f"(labels: {', '.join(sorted(labels))})")
        mergeable, state = self.gh.mergeable(self.pr)
        self.report.check(mergeable is (not conflicting),
                          f"GitHub reports #{self.pr} {'conflicting' if conflicting else 'mergeable'} (`{state}`)")

    # ---- stages ----
    def s1(self):
        self.report.stage("s1", "A factory PR is approved with FACTORY_MERGE off")
        since = now() - MARGIN
        # Labels given at creation are announced late, along with any added since, so a second
        # ready-for-agent event would queue a second implement run. Add the label in a later call.
        # No category label: the enhancement method's review wants every test in the description's
        # Slices list, which the person's pushed tests aren't, and a fix round can't add them there.
        issue = self.gh.post("issues", title=ISSUE_TITLE, body=ISSUE_BODY)
        self.issue = issue["number"]
        self.gh.post(f"issues/{self.issue}/labels", labels=["ready-for-agent"])
        self.report.note(f"Opened [#{self.issue}]({issue['html_url']}) with `ready-for-agent`")

        def opened():
            if self.gh.labels(self.issue) & {"agent:failed", "needs-info", "ready-for-human"}:
                raise StageFailed(f"implementation of #{self.issue} stopped: {sorted(self.gh.labels(self.issue))}")
            owner = self.gh.repo.split("/")[0]
            prs = self.gh.items(f"pulls?state=all&head={owner}:agent/issue-{self.issue}")
            return prs[0] if prs else None
        pr = wait("the factory to open a PR", opened, 40 * 60, every=15)
        self.pr, self.branch = pr["number"], pr["head"]["ref"]
        self.report.note(f"The factory opened [#{self.pr}]({pr['html_url']}) from `{self.branch}`")
        labels = self.settle(since)
        implement = [r for r in self.gh.runs(IMPLEMENT, since) if r["conclusion"] != "skipped"]
        self.report.check(bool(implement) and all(r["conclusion"] == "success" for r in implement),
                          "Implementation succeeded: " + ", ".join(self.run_link(r) for r in implement))
        self.check_runs_clean(since)
        pr = self.gh.pr(self.pr)
        approvals = [v for v in self.verdicts(since) if v["kind"] == "approve"]
        self.report.check("agent:approved" in labels and approvals and approvals[-1]["sha"] == pr["head"]["sha"],
                          f"Approved at the head, {self.commit_link(pr['head']['sha'])}" +
                          (f": [verdict]({approvals[-1]['url']})" if approvals else ""))
        self.report.check(bool(approvals) and "ready for you to merge" in approvals[-1]["body"] and pr["state"] == "open",
                          "The approval leaves the PR for a person to merge, and it is still open")
        rounds = [v for v in self.verdicts(since) if v["kind"] == "request_changes"]
        if rounds:
            self.report.note(f"The reviewer requested changes {len(rounds)} time(s) before approving")

    def s2(self):
        self.report.stage("s2", "A push to an approved PR clears the approval and starts a new review")
        self.require_approved()
        text = self.tests_with("uncapitalize leaves a leading digit unchanged",
                               "assert.equal(uncapitalize('1st Place'), '1st Place');")
        sha, since = self.push("Test uncapitalize with a leading digit", {TESTS: text})
        self.check_handler(self.handler(since), sha)
        self.check_settled(since, sha)
        self.check_approval_cleared(since, sha)
        self.check_reviewed(since, sha)
        self.check_runs_clean(since)

    def s3(self):
        self.report.stage("s3", "A push during a review discards its verdict without spending a fix round")
        self.require_approved()
        text = self.tests_with("uncapitalize lowercases only the first code point", WRONG)
        stale, since = self.push("Test uncapitalize on all-caps input, with the wrong expectation", {TESTS: text},
                                 passing=False)
        self.check_handler(self.handler(since), stale)
        review = self.running_review(since)
        self.report.note(f"{self.run_link(review)} is running its agent on {stale[:7]}")
        sha, pushed = self.push("Correct the all-caps uncapitalize test", {TESTS: self.clone.read(TESTS).replace(WRONG, RIGHT)})
        self.mid_review_checks(since, stale, review, sha, pushed)

    def s4a(self):
        self.report.stage("s4a", "A push that introduces a merge conflict clears the approval and starts a new review")
        self.require_approved()
        # A resumed run reuses the base change it already merged. merge_base() fetches the base first.
        merge_base = self.merge_base()
        if self.clone.read(SMOKE_FILE, f"origin/{self.base}") == self.clone.read(SMOKE_FILE, merge_base):
            self.change_base()
        else:
            self.report.note(f"`{self.base}` has changed `{SMOKE_FILE}` since #{self.pr} branched")
        mergeable, state = self.gh.mergeable(self.pr)
        self.report.check(mergeable is True, f"#{self.pr} still merges cleanly after the base change (`{state}`)")
        sha, since = self.push(f"Edit {SMOKE_FILE} so it conflicts with {self.base}", {SMOKE_FILE: self.smoke_text(f"PR #{self.pr}, s4a")},
                               conflict=True)
        self.check_handler(self.handler(since), sha, " despite the conflict")
        self.check_settled(since, sha, conflicting=True)
        self.check_approval_cleared(since, sha)
        self.check_reviewed(since, sha)
        self.check_runs_clean(since)
        others = self.gh.items(f"actions/runs?per_page=100&event=pull_request&head_sha={sha}", ".workflow_runs")
        self.report.note(f"`pull_request` workflow runs for {sha[:7]}: {len(others)}. GitHub skips them while a PR conflicts.")

    def s4b(self):
        self.report.stage("s4b", "A push during a review that introduces a merge conflict discards the verdict")
        self.require_approved()
        merge_base = self.merge_base()
        if not self.clone.conflicts("HEAD", f"origin/{self.base}"):
            raise StageFailed(f"s4b continues from s4a: #{self.pr} must conflict on {SMOKE_FILE}")
        stale, since = self.push(f"Restore {SMOKE_FILE}, resolving the conflict",
                                 {SMOKE_FILE: self.clone.read(SMOKE_FILE, rev=merge_base)})
        self.check_handler(self.handler(since), stale)
        review = self.running_review(since)
        self.report.note(f"{self.run_link(review)} is running its agent on {stale[:7]}")
        sha, pushed = self.push(f"Edit {SMOKE_FILE} so it conflicts with {self.base} again",
                                {SMOKE_FILE: self.smoke_text(f"PR #{self.pr}, s4b")}, conflict=True)
        self.mid_review_checks(since, stale, review, sha, pushed, conflicting=True)

    def mid_review_checks(self, since, stale, review, sha, pushed, conflicting=False):
        h = self.handler(pushed)
        self.check_settled(since, sha, conflicting)
        review = self.gh.get(f"actions/runs/{review['id']}")
        self.check_discarded(since, review, stale)
        first = min((v["at"] for v in self.verdicts(since) if v["sha"] == sha), default=now())
        self.check_no_round(since, stale, first)
        self.check_handler(h, sha, " despite the conflict" if conflicting else "")
        self.check_queued(h, review)
        self.check_reviewed(since, sha)
        self.check_runs_clean(since)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo", default="jonbaldie/software-factory-sandbox")
    parser.add_argument("--pr", type=int, help="continue with this approved factory PR instead of running s1")
    parser.add_argument("--stages", default=",".join(STAGES), help="comma-separated stages to run, in order")
    parser.add_argument("--clone", help="a clone of the sandbox to push from; defaults to a temporary clone")
    parser.add_argument("--report", help="also write the Markdown report to this file")
    parser.add_argument("--close", action="store_true", help="close the PR and its issue afterwards")
    parser.add_argument("--trailer", action="append", default=[], help="a trailer to add to each commit")
    args = parser.parse_args()
    stages = [s for s in args.stages.split(",") if s]
    if unknown := set(stages) - set(STAGES):
        parser.error(f"unknown stages: {', '.join(sorted(unknown))}")
    if args.pr:
        stages = [s for s in stages if s != "s1"]
    elif "s1" not in stages:
        parser.error("pass --pr to skip s1")

    gh = GitHub(args.repo)
    if PUSH not in {f["name"] for f in gh.items("contents/.github/workflows")}:
        sys.exit(f"{args.repo} has no {PUSH}: install the factory there first")
    p = run("gh", "api", f"repos/{args.repo}/actions/variables/FACTORY_MERGE", "--jq", ".value", check=False)
    if p.returncode == 0 and p.stdout.strip() == "true":
        sys.exit("FACTORY_MERGE is true, so the factory would merge the PR: unset it for the smoke test")
    if p.returncode and "404" not in p.stderr:
        log("couldn't read FACTORY_MERGE; s1 checks the approval's wording instead")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    workdir = args.clone or tempfile.mkdtemp(prefix="factory-smoke-")
    report = Report()
    smoke = Smoke(gh, Clone(args.repo, workdir, args.trailer), report, stamp)
    base_sha = gh.get(f"commits/{smoke.base}")["sha"]
    factory = gh.get("repos/jonbaldie/software-factory/commits/v1")["sha"]
    if args.pr:
        pr = gh.pr(args.pr)
        smoke.pr, smoke.branch = pr["number"], pr["head"]["ref"]
    try:
        for stage in stages:
            getattr(smoke, stage)()
    except (StageFailed, RuntimeError) as e:
        if not report.stages:
            report.stage(stage, "setup")
        report.check(False, f"Stopped: {e}")
    finally:
        pr_link = f"[#{smoke.pr}](https://github.com/{args.repo}/pull/{smoke.pr})" if smoke.pr else "no PR"
        header = (f"### {now():%Y-%m-%d %H:%M} UTC, run {stamp}\n\n"
                  f"{args.repo} at {smoke.commit_link(base_sha)}, `run-agent@v1` at "
                  f"[`{factory[:7]}`](https://github.com/jonbaldie/software-factory/commit/{factory}). PR {pr_link}. "
                  f"{'All checks passed.' if not report.failures else f'{report.failures} check(s) failed.'}")
        text = report.markdown(header)
        print("\n" + text)
        if args.report:
            with open(args.report, "w") as f:
                f.write(text)
        if args.close and smoke.pr:
            gh.call("PATCH", f"pulls/{smoke.pr}", [("state", "closed")])
            if smoke.issue:
                gh.call("PATCH", f"issues/{smoke.issue}", [("state", "closed"), ("state_reason", "not_planned")])
        if not args.clone:
            shutil.rmtree(workdir, ignore_errors=True)
    sys.exit(1 if report.failures else 0)


if __name__ == "__main__":
    main()
