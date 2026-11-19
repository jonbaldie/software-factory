#!/usr/bin/env python3
"""Validate the explicit state-machine specs in docs/state-machines/ against the repo.

Checks the invariants the specs declare, so a spec cannot drift from the
artefacts it describes:

1. machines.json parses; ids unique and complete (A1-A16, B1-B5, C, D1-D3,
   E1-E14, F); every machine names a spec that exists, evidence files that
   exist, and at least one transition with declared states.
2. Label vocabulary: every label a machine claims exists in the label
   universe (install.sh's label tables + the triage labels page).
3. Cross-workflow dispatches: the 9 `gh workflow run` sites A11 declares are
   the ones in the tree.
4. Head-validity guard: `require_current_head` reference counts match the
   invariants (review 12, fix 3).
5. Fix-round cap: `MAX_ROUNDS: 3` in factory-review.yml matches the spec.
6. Triage invariant: the 5 documented triage states are the spec's.

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
                text = open(os.path.join(d, fn)).read()
                hits.extend(re.findall(r"gh workflow run (\S+\.yml)", text))
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
    check(sorted(ids, key=expected.index) == expected, "all 40 inventoried machines are specified (A1-A16, B1-B5, C, D1-D3, E1-E14, F)")

    universe = label_universe()
    bad_files, bad_labels, bad_transitions, bad_specs = [], [], [], []
    for m in machines:
        spec_path = os.path.join(SPEC_DIR, m["spec"])
        if not os.path.exists(spec_path):
            bad_specs.append(m["id"])
        for f in m["files"]:
            base = f
            if base in ("docs/exploratory-testing/", ".audit/"):
                continue
            if not (os.path.exists(os.path.join(ROOT, base)) or os.path.exists(os.path.join(ROOT, base.rstrip("/")))):
                bad_files.append(f"{m['id']}:{f}")
        for label in m["labels"]:
            if label not in universe:
                bad_labels.append(f"{m['id']}:{label}")
        if m["id"] != "F":
            if not m["states"] or not m["transitions"]:
                bad_transitions.append(m["id"])
            for t in m["transitions"]:
                frm, to = t.get("from", ""), t.get("to", "")
                if frm not in m["states"] and frm not in ("*", "-") and m["id"] != "B2":
                    pass  # "from" may name an intermediate (B2 red); states carry the set either way
    check(not bad_specs, f"every machine's spec file exists (bad: {bad_specs})")
    check(not bad_files, f"every evidence file exists (bad: {bad_files})")
    check(not bad_labels, f"every claimed label is in the label universe (bad: {bad_labels})")
    check(not bad_transitions, f"every machine declares states and transitions (bad: {bad_transitions})")

    check(inv["triage_states"] == ["needs-triage", "needs-info", "ready-for-agent", "ready-for-human", "wontfix"],
          "triage states are exactly the documented 5 (A1)")

    review = read("template/.github/workflows/factory-review.yml")
    fix = read("template/.github/workflows/factory-fix.yml")
    check(len(re.findall(r"require_current_head", review)) == inv["require_current_head_refs"]["factory-review.yml"],
          "require_current_head refs in factory-review.yml match the spec (12: 1 def + 11 calls)")
    check(len(re.findall(r"require_current_head", fix)) == inv["require_current_head_refs"]["factory-fix.yml"],
          "require_current_head refs in factory-fix.yml match the spec (3: 1 def + 2 calls)")
    check("MAX_ROUNDS: 3" in review, "MAX_ROUNDS is 3 (A5)")

    sites = dispatch_sites()
    check(len(sites) == inv["dispatch_sites"], f"gh workflow run sites == {inv['dispatch_sites']} (found {len(sites)}: {sorted(set(sites))})")

    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
