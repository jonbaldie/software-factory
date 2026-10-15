"""Runs install.sh in a throwaway npm repo against a fake gh, and checks the variables it leaves and what it changes.

Usage: uv run tests/install.py
"""
import json, os, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Keeps the repo's variables in $FAKE_GH_STATE. $FAKE_GH_STATE's "fail_reads" makes every variable read fail like a GitHub outage.
FAKE_GH = r"""#!/usr/bin/env python3
import json, os, subprocess, sys
path = os.environ["FAKE_GH_STATE"]
st = json.load(open(path))
args = sys.argv[1:]
st["calls"].append(args)

def save():
    json.dump(st, open(path, "w"), indent=1)

def flag(name):
    return args[args.index(name) + 1] if name in args else None

def out(obj):
    q = flag("-q") or flag("--jq")
    if q:
        r = subprocess.run(["jq", "-r", q], input=json.dumps(obj), capture_output=True, text=True)
        sys.stdout.write(r.stdout)
        sys.stderr.write(r.stderr)
        sys.exit(r.returncode)
    print(json.dumps(obj))

def fail(msg):
    save()
    sys.stderr.write(msg + "\n")
    sys.exit(1)

kind, verb = (args + [""])[:2]
if kind == "auth":
    pass
elif kind == "repo":
    save()
    out({"nameWithOwner": "owner/repo"})
elif kind == "variable" and verb == "list" and st["fail_reads"]:
    fail("HTTP 503: unavailable (https://api.github.com/repos/owner/repo/actions/variables)")
elif kind == "variable" and verb == "list":
    fields = flag("--json").split(",")
    save()
    out([{k: v for k, v in {"name": n, "value": val}.items() if k in fields} for n, val in st["variables"].items()])
elif kind == "variable" and verb == "set":
    st["variables"][args[2]] = flag("--body")
elif kind == "variable" and verb == "delete":
    st["variables"].pop(args[2])
elif kind == "label" and verb == "list":
    save()
    out([{"name": n} for n in st["labels"]])
elif kind == "label" and verb == "create":
    if args[2] not in st["labels"]:
        st["labels"].append(args[2])
elif kind == "api":
    save()
    out({"can_approve_pull_request_reviews": True})
elif kind == "secret":
    save()
    out([{"name": n} for n in st["secrets"]])
else:
    fail(f"fake gh: unexpected call {args}")
save()
"""

PACKAGE = {"name": "fixture", "scripts": {"test": "node --test"}}


def run(variables, flags=(), fail_reads=False, secrets=()):
    """Installs into a fresh npm repo. Returns (exit code, output, variables after, labels after, whether files were written)."""
    with tempfile.TemporaryDirectory() as tmp:
        repo, fakebin = os.path.join(tmp, "repo"), os.path.join(tmp, "bin")
        os.makedirs(repo)
        os.makedirs(fakebin)
        with open(os.path.join(fakebin, "gh"), "w") as f:
            f.write(FAKE_GH)
        os.chmod(os.path.join(fakebin, "gh"), 0o755)
        with open(os.path.join(repo, "package.json"), "w") as f:
            json.dump(PACKAGE, f)
        with open(os.path.join(repo, "package-lock.json"), "w") as f:
            f.write("{}")
        subprocess.run(["git", "init", "-q", repo], check=True)
        state = os.path.join(tmp, "state.json")
        with open(state, "w") as f:
            json.dump({"variables": dict(variables), "labels": [], "calls": [], "fail_reads": fail_reads, "secrets": list(secrets)}, f)
        env = dict(os.environ, PATH=fakebin + os.pathsep + os.environ["PATH"], FAKE_GH_STATE=state)
        p = subprocess.run(["bash", os.path.join(ROOT, "install.sh"), *flags], cwd=repo, env=env, capture_output=True, text=True)
        with open(state) as f:
            st = json.load(f)
        return p.returncode, p.stdout + p.stderr, st["variables"], st["labels"], os.path.isdir(os.path.join(repo, ".github"))


CUSTOM = {"FACTORY_TEST_COMMAND": "make test", "FACTORY_SETUP_COMMAND": "make deps"}

failures = []


def check(name, ok, output):
    print(("ok   " if ok else "FAIL ") + name)
    if not ok:
        failures.append(name)
        print("     " + output.replace("\n", "\n     "))


code, output, variables, labels, wrote = run(CUSTOM, fail_reads=True)
check("a failed variable read stops the install before it changes anything",
      code != 0 and variables == CUSTOM and not labels and not wrote and "couldn't read" in output and "HTTP 503" in output, output)

code, output, variables, labels, wrote = run(CUSTOM, ["--test-command", "just test", "--setup-command", "just deps"], fail_reads=True)
check("a failed variable read stops the install even when both commands are given",
      code != 0 and variables == CUSTOM and not labels and not wrote, output)

code, output, variables, labels, wrote = run({})
check("absent variables are detected from package.json",
      code == 0 and variables == {"FACTORY_TEST_COMMAND": "npm test", "FACTORY_SETUP_COMMAND": "npm ci"} and wrote, output)

code, output, variables, labels, wrote = run(CUSTOM)
check("saved custom commands are kept", code == 0 and variables == CUSTOM, output)

code, output, variables, labels, wrote = run(CUSTOM, ["--test-command", "just test", "--setup-command", ""])
check("flags override saved commands", code == 0 and variables == {"FACTORY_TEST_COMMAND": "just test"}, output)

code, output, variables, labels, wrote = run({"FACTORY_TEST_COMMAND": "make test\nmake lint"})
check("a multi-line saved command is kept whole",
      code == 0 and variables == {"FACTORY_TEST_COMMAND": "make test\nmake lint", "FACTORY_SETUP_COMMAND": "npm ci"}, output)

code, output, variables, labels, wrote = run({**CUSTOM, "FACTORY_MERGE": "true", "FACTORY_HARNESS": "claude"}, secrets=["OPENROUTER_API_KEY"])
check("FACTORY_MERGE and FACTORY_HARNESS are read",
      code == 0 and "FACTORY_MERGE = true" in output and "! ANTHROPIC_API_KEY is missing" in output, output)

if failures:
    sys.exit(f"\n{len(failures)} failed")
print("\nall passed")
