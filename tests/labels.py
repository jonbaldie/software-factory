# /// script
# dependencies = ["pyyaml"]
# ///
"""Runs the review and fix jobs from template/.github/workflows against a fake gh, and checks the PR's labels.

Each scenario runs the job's real `run:` steps in bash. The agent step is stubbed with a verdict or a crash,
and the other `uses:` steps succeed without doing anything.

Usage: uv run tests/labels.py [--trace]
"""
import argparse, json, os, re, shutil, subprocess, sys, tempfile
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAKEBIN = os.path.join(ROOT, "tests", "fakebin")
REPO_LABELS = """needs-triage needs-info ready-for-agent ready-for-human wontfix agent:working agent:review
agent:changes-requested agent:approved agent:failed agent:wip bug enhancement""".split()

# ---- GitHub expressions: the subset these workflows use ----
TOKEN = re.compile(r"\s*(?:(\|\||&&|==|!=|!|\(|\)|,)|'((?:[^']|'')*)'|(\d+)|([A-Za-z_][A-Za-z0-9_.\-]*))")


def tokenize(s):
    out, pos = [], 0
    s = s.strip()
    while pos < len(s):
        m = TOKEN.match(s, pos)
        if not m:
            raise ValueError(f"cannot tokenize {s!r} at {pos}")
        op, string, num, ident = m.groups()
        out.append(("op", op) if op else ("str", string.replace("''", "'")) if string is not None
                   else ("num", int(num)) if num else ("id", ident))
        pos = m.end()
        while pos < len(s) and s[pos].isspace():
            pos += 1
    return out


def evaluate(expr, ctx):
    toks = tokenize(expr)
    i = 0

    def peek():
        return toks[i] if i < len(toks) else (None, None)

    def take():
        nonlocal i
        i += 1
        return toks[i - 1]

    def p_or():
        v = p_and()
        while peek() == ("op", "||"):
            take()
            r = p_and()
            v = v if truthy(v) else r
        return v

    def p_and():
        v = p_cmp()
        while peek() == ("op", "&&"):
            take()
            r = p_cmp()
            v = r if truthy(v) else v
        return v

    def p_cmp():
        v = p_unary()
        if peek() in (("op", "=="), ("op", "!=")):
            op = take()[1]
            r = p_unary()
            eq = to_str(v).lower() == to_str(r).lower()
            return eq if op == "==" else not eq
        return v

    def p_unary():
        if peek() == ("op", "!"):
            take()
            return not truthy(p_unary())
        return p_primary()

    def p_primary():
        kind, val = take()
        if (kind, val) == ("op", "("):
            v = p_or()
            take()
            return v
        if kind in ("str", "num"):
            return val
        if val in ("true", "false", "null"):
            return {"true": True, "false": False, "null": None}[val]
        if peek() == ("op", "("):
            take()
            take()  # no-argument status functions only
            return ctx["funcs"][val]()
        cur = ctx
        for part in val.split("."):
            cur = cur.get(part) if isinstance(cur, dict) else None
        return cur

    return p_or()


def truthy(v):
    return v not in (None, False, 0, "")


def to_str(v):
    return "" if v is None else ("true" if v is True else "false" if v is False else str(v))


def interp(value, ctx):
    return re.sub(r"\$\{\{\s*(.*?)\s*\}\}", lambda m: to_str(evaluate(m.group(1), ctx)), str(value))


# ---- Agent stubs ----
def approve(repo):
    return True, {"structured-output": json.dumps({"verdict": "approve", "summary": "Looks right.", "required_changes": []})}


def request_changes(repo):
    return True, {"structured-output": json.dumps({"verdict": "request_changes", "summary": "One gap.", "required_changes": ["Add a test for tabs"]})}


def fixes(repo):
    with open(os.path.join(repo, "README.md"), "a") as f:
        f.write("fixed\n")
    return True, {"result": "Added the test for tabs."}


def crashes(repo):
    return False, {}


REVIEW_ROUND_1 = "<!-- factory:review request_changes -->\n### 🔁 Changes requested (round 1 of 3)\n\nOne gap.\n\n- Add a test for tabs"
REVIEW_FAILED = "💥 The review stage failed. [See the run](https://example/run/1). Re-add `agent:review` to retry."
FIX_FAILED = "💥 The fix stage failed. [See the run](https://example/run/1). Re-add `agent:changes-requested` to retry."

# event: the label name for a `labeled` event, or None for workflow_dispatch.
# The retries are issue #9: a retried review or fix clears agent:failed, and a failed retry puts it back.
SCENARIOS = [
    dict(name="review retry, approved", wf="factory-review.yml", event="agent:review", start=["agent:failed", "agent:review"],
         comments=[REVIEW_FAILED], agent=approve, final=["agent:approved"], dispatch=[]),
    dict(name="review retry, changes requested", wf="factory-review.yml", event="agent:review", start=["agent:failed", "agent:review"],
         comments=[REVIEW_FAILED], agent=request_changes, final=["agent:changes-requested"], dispatch=["factory-fix.yml"]),
    dict(name="review retry, fails again", wf="factory-review.yml", event="agent:review", start=["agent:failed", "agent:review"],
         comments=[REVIEW_FAILED], agent=crashes, final=["agent:failed"], dispatch=[], last_comment="💥 The review stage failed"),
    dict(name="fix retry, hands back", wf="factory-fix.yml", event="agent:changes-requested", start=["agent:failed", "agent:changes-requested"],
         comments=[REVIEW_ROUND_1, FIX_FAILED], agent=fixes, final=["agent:review"], dispatch=["factory-review.yml"]),
    dict(name="fix retry, fails again", wf="factory-fix.yml", event="agent:changes-requested", start=["agent:failed", "agent:changes-requested"],
         comments=[REVIEW_ROUND_1, FIX_FAILED], agent=crashes, final=["agent:failed"], dispatch=[], last_comment="💥 The fix stage failed"),
    dict(name="review, never failed", wf="factory-review.yml", event="agent:review", start=["agent:review"],
         comments=[], agent=approve, final=["agent:approved"], dispatch=[]),
    dict(name="review dispatched by fix, never failed", wf="factory-review.yml", event=None, start=["agent:review"],
         comments=[REVIEW_ROUND_1], agent=request_changes, final=["agent:changes-requested"], dispatch=["factory-fix.yml"]),
    dict(name="fix dispatched by review, never failed", wf="factory-fix.yml", event=None, start=["agent:changes-requested"],
         comments=[REVIEW_ROUND_1], agent=fixes, final=["agent:review"], dispatch=["factory-review.yml"]),
    dict(name="unrelated label, job skipped", wf="factory-review.yml", event="agent:failed", start=["agent:failed"],
         comments=[REVIEW_FAILED], agent=approve, final=["agent:failed"], dispatch=[]),
]


def sh(*cmd, cwd=None):
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True)


def make_repo(root):
    """A repo with the factory installed on main and the agent's branch checked out."""
    repo = os.path.join(root, "repo")
    os.makedirs(repo)
    shutil.copytree(os.path.join(ROOT, "template/.github"), os.path.join(repo, ".github"))
    with open(os.path.join(repo, "README.md"), "w") as f:
        f.write("textkit\n")
    g = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com"]
    sh("git", "init", "-q", "-b", "main", cwd=repo)
    sh("git", "add", ".", cwd=repo)
    sh(*g, "commit", "-q", "-m", "base", cwd=repo)
    sh("git", "update-ref", "refs/remotes/origin/main", "HEAD", cwd=repo)
    sh("git", "switch", "-q", "-c", "agent/issue-39", cwd=repo)
    with open(os.path.join(repo, "README.md"), "a") as f:
        f.write("isBlank\n")
    sh(*g, "commit", "-qam", "Add isBlank", cwd=repo)
    return repo


def run_scenario(sc, trace):
    root = tempfile.mkdtemp(prefix="labels-")
    repo = make_repo(root)
    temp = os.path.join(root, "runner")
    os.makedirs(temp)
    state_path = os.path.join(root, "state.json")
    state = {
        "repo_labels": REPO_LABELS, "merge_ok": True, "calls": [], "dispatches": [], "label_history": [],
        "pr": {"number": 40, "baseRefName": "main", "headRefName": "agent/issue-39", "state": "OPEN",
               "body": "Adds isBlank.\n\nCloses #39", "labels": [{"name": n} for n in sc["start"]],
               "comments": [{"author": {"login": "github-actions"}, "authorAssociation": "NONE", "body": b} for b in sc["comments"]],
               "closingIssuesReferences": [{"number": 39}]},
        "issues": {"39": {"number": 39, "title": "Add isBlank", "body": "Return true for blank strings.",
                          "labels": [{"name": "enhancement"}, {"name": "ready-for-agent"}], "comments": []}},
    }
    with open(state_path, "w") as f:
        json.dump(state, f)

    with open(os.path.join(ROOT, "template/.github/workflows", sc["wf"]), encoding="utf-8") as f:
        (_, job), = yaml.safe_load(f)["jobs"].items()
    event_name = "pull_request" if sc["event"] else "workflow_dispatch"
    ctx = {
        "github": {"event_name": event_name, "repository": "o/sandbox", "server_url": "https://github.com", "run_id": "1",
                   "token": "fake-token",
                   "event": {"pull_request": {"number": 40}, "label": {"name": sc["event"]}} if sc["event"] else {}},
        "inputs": {} if sc["event"] else {"pr": "40"},
        "vars": {"FACTORY_TEST_COMMAND": "true"}, "secrets": {}, "runner": {"temp": temp}, "steps": {}, "env": {},
    }
    failed = False
    ctx["funcs"] = {"success": lambda: not failed, "failure": lambda: failed, "cancelled": lambda: False, "always": lambda: True}
    log = []
    during = None

    if not truthy(evaluate(job["if"], ctx)):
        log.append("job skipped")
    else:
        ctx["env"] = {k: interp(v, ctx) for k, v in job.get("env", {}).items()}
        for step in job["steps"]:
            label = step.get("name") or step.get("uses")
            cond = re.sub(r"^\$\{\{\s*(.*?)\s*\}\}$", r"\1", str(step.get("if", "success()")))
            if not truthy(evaluate(cond, ctx)):
                log.append(f"skip  {label}")
                continue
            step_env = {k: interp(v, ctx) for k, v in step.get("env", {}).items()}
            outputs = {}
            if "uses" in step:
                if "run-agent" in step["uses"]:
                    with open(state_path) as f:
                        during = sorted(l["name"] for l in json.load(f)["pr"]["labels"])
                    ok, outputs = sc["agent"](repo)
                else:
                    ok = True
            else:
                out_file = os.path.join(root, "github_output")
                open(out_file, "w").close()
                script = os.path.join(root, "step.sh")
                with open(script, "w", encoding="utf-8") as f:
                    f.write(step["run"])
                env = {"PATH": FAKEBIN + ":" + os.environ["PATH"], "HOME": os.environ["HOME"], "PYTHONUTF8": "1",
                       "GITHUB_OUTPUT": out_file, "RUNNER_TEMP": temp, "GITHUB_REPOSITORY": "o/sandbox",
                       "FAKE_GH_STATE": state_path, **ctx["env"], **step_env}
                # The shell GitHub runs a `run:` step with.
                p = subprocess.run(["bash", "--noprofile", "--norc", "-eo", "pipefail", script],
                                   cwd=repo, env=env, capture_output=True, text=True)
                ok = p.returncode == 0
                for line in open(out_file):
                    if "=" in line:
                        k, v = line.rstrip("\n").split("=", 1)
                        outputs[k] = v
                if trace and (p.stdout.strip() or p.stderr.strip()):
                    log.append("      " + (p.stdout + p.stderr).strip().replace("\n", "\n      "))
            log.append(f"{'ok' if ok else 'FAIL':5} {label}")
            if not ok:
                failed = True
            if "id" in step:
                ctx["steps"][step["id"]] = {"outputs": outputs, "outcome": "success" if ok else "failure"}

    with open(state_path) as f:
        st = json.load(f)
    shutil.rmtree(root)
    return {
        "during": during,
        "final": sorted(l["name"] for l in st["pr"]["labels"]),
        "history": st["label_history"],
        "dispatch": [d[0] for d in st["dispatches"]],
        "new_comments": [c["body"] for c in st["pr"]["comments"][len(sc["comments"]):]],
        "log": log,
    }


def check(sc, r):
    problems = []
    if r["during"] is not None and "agent:failed" in r["during"]:
        problems.append("agent:failed still on while the agent runs")
    if r["final"] != sorted(sc["final"]):
        problems.append(f"final labels {r['final']}, want {sorted(sc['final'])}")
    if r["dispatch"] != sc["dispatch"]:
        problems.append(f"dispatched {r['dispatch']}, want {sc['dispatch']}")
    if "last_comment" in sc and not (r["new_comments"] and r["new_comments"][-1].startswith(sc["last_comment"])):
        problems.append(f"last comment {r['new_comments'][-1:]}, want one starting {sc['last_comment']!r}")
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--trace", action="store_true", help="print each step, its output and the label history")
    a = ap.parse_args()
    red = 0
    for sc in SCENARIOS:
        r = run_scenario(sc, a.trace)
        problems = check(sc, r)
        red += bool(problems)
        print(f"{'FAIL' if problems else 'ok  '} {sc['name']}: during={r['during']} final={r['final']}")
        for p in problems:
            print(f"       - {p}")
        if a.trace:
            print("       history: " + " -> ".join(map(str, r["history"])))
            for line in r["log"]:
                print("       " + line)
    print(f"{red} failed, {len(SCENARIOS) - red} passed")
    sys.exit(1 if red else 0)


if __name__ == "__main__":
    main()
