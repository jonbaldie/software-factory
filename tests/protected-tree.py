# /// script
# dependencies = []
# ///
import hashlib
import os
import shutil
import subprocess
import tempfile
import zlib
from pathlib import Path

GUARD = Path(__file__).resolve().parents[1] / "template/.github/factory/protected-tree.sh"


def run(repo, *args, check=True):
    return subprocess.run(args, cwd=repo, text=True, capture_output=True, check=check)


def git(repo, *args, check=True):
    return run(repo, "git", *args, check=check)


def guard(repo, *args, check=True):
    return run(repo, "bash", str(GUARD), *args, check=check)


def guard_with_git_failure(repo, command, *args, emit_output=False):
    with tempfile.TemporaryDirectory(prefix="protected-failure-") as temp:
        shim = Path(temp) / "git"
        shim.write_text('''#!/bin/bash
if [[ " $* " == *" $FAIL_GIT "* ]]; then
  if [ "$EMIT_OUTPUT" = true ]; then "$REAL_GIT" "$@"; fi
  echo "injected $FAIL_GIT failure" >&2
  exit 23
fi
exec "$REAL_GIT" "$@"
''')
        shim.chmod(0o755)
        return subprocess.run(["bash", str(GUARD), *args], cwd=repo, text=True, capture_output=True,
                              env={**os.environ, "PATH": temp + os.pathsep + os.environ["PATH"],
                                   "REAL_GIT": shutil.which("git"), "FAIL_GIT": command,
                                   "EMIT_OUTPUT": str(emit_output).lower()})


def rejects_git_failure(repo, command, *args, emit_output=False):
    result = guard_with_git_failure(repo, command, *args, emit_output=emit_output)
    assert f"injected {command} failure" in result.stderr, result
    assert result.returncode != 0, (command, args, result)


def commit(repo, message):
    git(repo, "add", "-A")
    git(repo, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", message)


with tempfile.TemporaryDirectory(prefix="protected-tree-") as temp:
    repo = Path(temp)
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.name", "Test")
    git(repo, "config", "user.email", "test@example.com")
    (repo / ".github").mkdir()
    (repo / ".github/config").write_text("original\n")
    (repo / "other").write_text("original\n")
    commit(repo, "base")
    base = git(repo, "rev-parse", "HEAD").stdout.strip()
    baseline = guard(repo, "capture-revision", base).stdout.strip()
    rejects_git_failure(repo, "status", "clean")
    rejects_git_failure(repo, "diff", "capture-index")
    malformed = f"tree {baseline}\nauthor Legacy 1 +0000\ncommitter Legacy 1 +0000\n\nlegacy\n"
    legacy = subprocess.run(["git", "hash-object", "--literally", "-t", "commit", "-w", "--stdin"],
                            input=malformed, cwd=repo, text=True, capture_output=True, check=True).stdout.strip()
    git(repo, "update-ref", "refs/heads/legacy", legacy)
    assert git(repo, "fsck", "--full", check=False).returncode != 0
    assert guard(repo, "verify", baseline).returncode == 0
    (repo / ".github/config").write_text("agent\n")
    git(repo, "add", "-A")
    rejected = guard(repo, "verify", baseline, check=False)
    assert rejected.returncode != 0 and rejected.stdout.strip() == ".github/config"
    commit(repo, "agent")
    assert guard(repo, "verify", baseline, check=False).returncode != 0
    replacement = git(repo, "rev-parse", "HEAD^{tree}").stdout.strip()
    git(repo, "replace", baseline, replacement)
    assert guard(repo, "verify", baseline, check=False).returncode != 0
    git(repo, "replace", "-d", baseline)
    git(repo, "reset", "--hard", base)
    git(repo, "switch", "-qc", "branch")
    (repo / ".github/branch").write_text("pre-existing\n")
    (repo / "other").write_text("branch\n")
    commit(repo, "branch")
    git(repo, "switch", "-q", "main")
    (repo / "other").write_text("main\n")
    commit(repo, "main")
    git(repo, "switch", "-q", "branch")
    assert git(repo, "merge", "main", check=False).returncode != 0
    before = git(repo, "ls-files", "--stage", "-z").stdout
    merged = guard(repo, "capture-index").stdout.strip()
    assert git(repo, "ls-files", "--stage", "-z").stdout == before
    assert git(repo, "show", f"{merged}:.github/branch").stdout == "pre-existing\n"
    assert git(repo, "ls-files", "-u", "--", "other").stdout
    assert guard(repo, "verify", merged).returncode == 0
    (repo / ".github/branch").write_text("agent\n")
    git(repo, "add", ".github/branch")
    rejected = guard(repo, "verify", merged, check=False)
    assert rejected.returncode != 0 and rejected.stdout.strip() == ".github/branch"
    git(repo, "merge", "--abort")
    git(repo, "switch", "-q", "main")
    (repo / ".github/config").write_text("main\n")
    commit(repo, "protected-main")
    git(repo, "switch", "-q", "branch")
    (repo / ".github/config").write_text("branch\n")
    commit(repo, "protected-branch")
    assert git(repo, "merge", "main", check=False).returncode != 0
    before = git(repo, "ls-files", "--stage", "-z").stdout
    assert guard(repo, "capture-index", check=False).returncode != 0
    assert git(repo, "ls-files", "--stage", "-z").stdout == before

with tempfile.TemporaryDirectory(prefix="protected-history-") as temp:
    repo = Path(temp)
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.name", "Test")
    git(repo, "config", "user.email", "test@example.com")
    (repo / ".github").mkdir()
    protected = repo / ".github/config"
    protected.write_text("old\n")
    commit(repo, "old")
    old = git(repo, "rev-parse", "HEAD").stdout.strip()
    protected.write_text("middle\n")
    commit(repo, "middle")
    middle = git(repo, "rev-parse", "HEAD").stdout.strip()
    middle_tree = guard(repo, "capture-revision", middle).stdout.strip()
    protected.write_text("start\n")
    commit(repo, "start")
    start = git(repo, "rev-parse", "HEAD").stdout.strip()
    history = guard(repo, "capture-history", start).stdout.strip()
    rejects_git_failure(repo, "rev-list", "capture-history", start)
    rejects_git_failure(repo, "rev-list", "verify", middle_tree, start, hashlib.sha256(b"").hexdigest())
    rejects_git_failure(repo, "rev-list", "verify", middle_tree, start, history, emit_output=True)
    git(repo, "switch", "-qc", "work", old)
    (repo / "other").write_text("work\n")
    commit(repo, "work")
    base_tree = guard(repo, "capture-revision", old).stdout.strip()
    git(repo, "merge", "--no-edit", middle)
    assert guard(repo, "verify", base_tree, start, history).returncode == 0
    protected.write_text("start\n")
    git(repo, "add", ".github/config")
    assert guard(repo, "verify", base_tree, start, history, check=False).returncode != 0
    assert guard(repo, "clean", check=False).returncode != 0
    git(repo, "reset", "--hard", old)
    assert guard(repo, "verify", middle_tree, start, history).returncode == 0
    assert guard(repo, "verify", base_tree, start, history).returncode == 0
    git(repo, "reset", "--hard", start)
    protected.write_text("untrusted\n")
    commit(repo, "agent default")
    git(repo, "update-ref", "refs/heads/main", "HEAD")
    assert guard(repo, "verify", base_tree, start, history, check=False).returncode != 0
    git(repo, "reset", "--hard", old)
    alternate = subprocess.run(["git", "commit-tree", base_tree], input="alternate\n", cwd=repo,
                               text=True, capture_output=True, check=True).stdout.strip()
    data = subprocess.check_output(["git", "cat-file", "commit", middle], cwd=repo)
    changed = data.replace(f"parent {old}\n".encode(), f"parent {alternate}\n".encode())
    assert changed != data
    object_path = repo / ".git/objects" / middle[:2] / middle[2:]
    object_path.unlink()
    object_path.write_bytes(
        zlib.compress(b"commit " + str(len(changed)).encode() + b"\0" + changed))
    assert guard(repo, "verify", base_tree, start, history, check=False).returncode != 0
print("protected-tree: real index and tree checks passed")
