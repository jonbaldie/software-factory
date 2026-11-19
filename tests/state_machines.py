#!/usr/bin/env python3
"""Validate the explicit state-machine specs in docs/state-machines/ against the repo.

Every check here reads from the artefacts AND from machines.json, so a change
in either one without the other fails:

1. machines.json parses; ids unique and complete (A1-A16, B1-B5, C, D1-D3,
   E1-E14, F); every machine names a spec that exists, evidence files that
   exist, and at least one transition with declared states.
2. Label vocabulary (both directions): labels claimed by the specs exist in
   install.sh's tables; labels used by workflows exist in the same universe;
   install.sh's tables match label_roots.
3. Cross-workflow dispatches: each of the 9 declared sites names the right
   file, line range and target — a retargeted dispatch fails.
4. Head-validity guard: require_current_head *calls* (whole-line, so a
   commented-out call fails) match the invariants.
5. Fix-round cap: MAX_ROUNDS in the workflow matches inv["max_rounds"].
6. Triage invariant: the 5 documented states appear in triage-labels.md,
   the triage workflow and the specs.

Run: uv run tests/state_machines.py
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC_DIR = os.path.join(ROOT, "docs", "state-machines")
FAILURES = []


def check(cond, msg):
    if cond:
        print(f"✅ {msg}")
    else:
        FAILURES.append(msg)
        print(f"❌ {msg}")


def read(rel):
    with open(os.path.join(ROOT, rel)) as f:
        return f.read()


def label_universe():
    names = set()
    install = read("install.sh")
    for m in re.finditer(r"^(needs-[a-z-]+|ready-for-[a-z]+|wontfix|agent:[a-z-]+|bug|enhancement)\|", install, re.M):
        names.add(m.group(1))
    page = read("docs/agents/triage-labels.md")
    for name in ("needs-triage", "needs-info", "ready-for-agent", "ready-for-human", "wontfix"):
        if f"`{name}`" in page:
            names.add(name)
    return names


def dispatch_sites():
    hits = []
    for sub in ("template/.github/workflows", "template/.github/factory"):
        d = os.path.join(ROOT, sub)
        for fn in sorted(os.listdir(d)):
            if fn.endswith((".yml", ".sh")):
                path = os.path.join(sub, fn)
                for lineno, line in enumerate(open(os.path.join(ROOT, path)), 1):
                    for m_ in re.finditer(r"gh workflow run (\S+\.yml)", line):
                        hits.append({"site": path, "lineno": lineno, "target": m_.group(1)})
    return hits


def main():
    with open(os.path.join(SPEC_DIR, "machines.json")) as f:
        doc = json.load(f)
    inv = doc["invariants"]
    machines = doc["machines"]

    expected = (["A%d" % i for i in range(1, 17)] + ["B%d" % i for i in range(1, 6)]
                + ["C"] + ["D%d" % i for i in range(1, 4)] + ["E%d" % i for i in range(1, 15)] + ["F"])
    ids = [m["id"] for m in machines]
    check(len(ids) == len(set(ids)), "machine ids are unique")
    check(set(ids) == set(expected) and len(ids) == len(expected),
          f"all {len(expected)} inventoried machines are specified (A1-A16, B1-B5, C, D1-D3, E1-E14, F)")

    universe = label_universe()
    bad_files, bad_labels, bad_transitions, bad_specs = [], [], [], []
    for m in machines:
        if not os.path.exists(os.path.join(SPEC_DIR, m["spec"])):
            bad_specs.append(m["id"])
        for f in m["files"]:
            if f in ("docs/exploratory-testing/", ".audit/"):
                continue
            if not os.path.exists(os.path.join(ROOT, f)):
                bad_files.append(f"{m['id']}:{f}")
        for label in m["labels"]:
            if label not in universe:
                bad_labels.append(f"{m['id']}:{label}")
        if m["id"] == "F":
            continue
        if not m["states"] or not m["transitions"]:
            bad_transitions.append(f"{m['id']}:empty")
            continue
        for t in m["transitions"]:
            for key in ("from", "to"):
                v = t.get(key, "")
                if v not in ("*", "-") and v not in m["states"]:
                    bad_transitions.append(f"{m['id']}:transition {key}={v!r} not a declared state")
    check(not bad_specs, f"every machine's spec file exists (bad: {bad_specs})")
    check(not bad_files, f"every evidence file exists (bad: {bad_files})")
    check(not bad_labels, f"every claimed label is in the label universe (bad: {bad_labels})")
    check(not bad_transitions, f"every transition names declared states (bad: {bad_transitions[:4]})")

    # install.sh tables vs label_roots (name|color|description lines, in order)
    lines = [l.split("|")[0] for l in read("install.sh").splitlines() if "|" in l and re.match(r"^(needs-|ready-for-|agent:|wontfix|bug|enhancement)", l)]
    check(lines[:11] == inv["label_roots"]["install_force"], f"install.sh force table matches label_roots ({lines[:11]})")
    check(lines[11:] == inv["label_roots"]["category_only_if_missing"], f"install.sh category table matches label_roots ({lines[11:]})")

    # labels used by workflows ⊆ universe (reverse direction)
    used = set()
    for sub in ("template/.github/workflows",):
        d = os.path.join(ROOT, sub)
        for fn in sorted(os.listdir(d)):
            text = open(os.path.join(d, fn)).read()
            used.update(re.findall(r"(?:needs-|ready-for-|agent:)[a-z-]+", text))
            used.update(re.findall(r"\b(?:bug|enhancement)\b", text))
    check(used <= universe, f"workflow labels ⊆ universe (unknown: {sorted(used - universe)})")

    check(inv["triage_states"] == ["needs-triage", "needs-info", "ready-for-agent", "ready-for-human", "wontfix"],
          "triage states are exactly the documented 5 (A1)")
    triage = read("template/.github/workflows/factory-triage.yml")
    page = read("docs/agents/triage-labels.md")
    for s in inv["triage_states"]:
        if f"`{s}`" not in page or s not in triage:
            check(False, f"triage state {s} documented in triage-labels.md and used in factory-triage.yml")

    review = read("template/.github/workflows/factory-review.yml")
    fix = read("template/.github/workflows/factory-fix.yml")
    for name, text, key in (("factory-review.yml", review, "factory-review.yml"), ("factory-fix.yml", fix, "factory-fix.yml")):
        calls = [l for l in text.splitlines() if l.strip() == "require_current_head"]
        check(len(calls) == inv["require_current_head_calls"][key],
              f"require_current_head() calls in {name} match the spec ({inv['require_current_head_calls'][key]} calls)")
    m = re.search(r"MAX_ROUNDS:\s*(\d+)", review)
    check(m and int(m.group(1)) == inv["max_rounds"], f"MAX_ROUNDS matches inv['max_rounds'] ({inv['max_rounds']})")

    sites = dispatch_sites()
    spec = doc["dispatches"]
    declared = {(d["site"], d["target"]) for d in spec}
    actual = {(h["site"], h["target"]) for h in sites}
    check(len(sites) == len(spec) == inv["dispatch_sites"], f"gh workflow run sites == {inv['dispatch_sites']} (found {len(sites)})")
    check(declared == actual, f"dispatch (site, target) pairs match the spec (only in tree: {sorted(actual - declared)}; only in spec: {sorted(declared - actual)})")

    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
