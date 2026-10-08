"""Runs run-agent/pi.mjs against a fake pi that ends with a given final message, and checks the result line it writes.

Usage: uv run tests/pi.py
"""
import json, os, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SCHEMA = {"type": "object", "required": ["verdict"],
          "properties": {"verdict": {"type": "string"}, "kind": {"enum": ["bug", "feature"]}, "notes": {"type": "array", "items": {"type": "string"}}}}

FAKE_PI = """#!/usr/bin/env python3
import json, os, sys
sys.stdin.read()
message = {"role": "assistant", "content": [{"type": "text", "text": os.environ["FAKE_PI_TEXT"]}],
           "stopReason": "stop", "usage": {"cost": {"total": 0.01}}}
print(json.dumps({"type": "message_end", "message": message}))
print(json.dumps({"type": "turn_end"}))
"""

FENCE = "```"

# (name, final message, expected subtype, expected structured_output)
SCENARIOS = [
    ("plain answer", f'{FENCE}json\n{{"verdict":"ok"}}\n{FENCE}', "success", {"verdict": "ok"}),
    ("backticks in a string", f'{FENCE}json\n{{"verdict":"use {FENCE} here"}}\n{FENCE}',
     "success", {"verdict": f"use {FENCE} here"}),
    ("code fence in a summary", "Done.\n\n" + FENCE + "json\n"
     + json.dumps({"verdict": f"Root cause: x.\n\n{FENCE}\nFAIL test_x\n{FENCE}"}) + f"\n{FENCE}",
     "success", {"verdict": f"Root cause: x.\n\n{FENCE}\nFAIL test_x\n{FENCE}"}),
    ("prose after the block", f'{FENCE}json\n{{"verdict":"a {FENCE} b"}}\n{FENCE}\n\nThat is all.',
     "success", {"verdict": f"a {FENCE} b"}),
    ("last block wins", f'{FENCE}json\n{{"verdict":"first"}}\n{FENCE}\n\n{FENCE}json\n{{"verdict":"second"}}\n{FENCE}',
     "success", {"verdict": "second"}),
    ("other fences before the answer", f'{FENCE}\nsome code\n{FENCE}\n\n{FENCE}json\n{{"verdict":"ok"}}\n{FENCE}',
     "success", {"verdict": "ok"}),
    ("closing fence on the JSON line", f'{FENCE}json\n{{"verdict":"ok"}}{FENCE}', "success", {"verdict": "ok"}),
    ("indented closing fence", f'{FENCE}json\n{{"verdict":"ok"}}\n  {FENCE}', "success", {"verdict": "ok"}),
    ("CRLF line endings", f'{FENCE}json\r\n{{"verdict":"a {FENCE} b"}}\r\n{FENCE}\r\n', "success", {"verdict": f"a {FENCE} b"}),
    ("empty block before the answer", f'{FENCE}json\n{FENCE}\n\n{FENCE}json\n{{"verdict":"ok"}}\n{FENCE}',
     "success", {"verdict": "ok"}),
    ("invalid block before the answer", f'{FENCE}json\n{{"verdict":}}\n{FENCE}\n\n{FENCE}json\n{{"verdict":"ok"}}\n{FENCE}',
     "success", {"verdict": "ok"}),
    ("unclosed block before the answer", f'{FENCE}json\n{{"verdict":\n{FENCE}json\n{{"verdict":"ok"}}\n{FENCE}',
     "success", {"verdict": "ok"}),
    ("enum value", f'{FENCE}json\n{{"verdict":"ok","kind":"bug"}}\n{FENCE}', "success", {"verdict": "ok", "kind": "bug"}),
    ("invalid answer after a valid one", f'{FENCE}json\n{{"verdict":"ok"}}\n{FENCE}\n\n{FENCE}json\n{{"verdict":}}\n{FENCE}',
     "error_structured_output", None),
    ("unclosed answer after a valid one", f'{FENCE}json\n{{"verdict":"ok"}}\n{FENCE}\n\n{FENCE}json\n{{"verdict":"changed',
     "error_structured_output", None),
    ("no block", '{"verdict":"ok"}', "error_structured_output", None),
    ("invalid JSON", f'{FENCE}json\n{{"verdict":}}\n{FENCE}', "error_structured_output", None),
    ("unclosed block", f'{FENCE}json\n{{"verdict":"ok"}}', "error_structured_output", None),
    ("missing required key", f'{FENCE}json\n{{"notes":[]}}\n{FENCE}', "error_structured_output", None),
    ("wrong type", f'{FENCE}json\n{{"verdict":1}}\n{FENCE}', "error_structured_output", None),
    ("value outside the enum", f'{FENCE}json\n{{"verdict":"ok","kind":"chore"}}\n{FENCE}', "error_structured_output", None),
    ("wrong item type", f'{FENCE}json\n{{"verdict":"ok","notes":[1]}}\n{FENCE}', "error_structured_output", None),
]


def run(text):
    with tempfile.TemporaryDirectory() as tmp:
        fake = os.path.join(tmp, "pi")
        with open(fake, "w") as f:
            f.write(FAKE_PI)
        os.chmod(fake, 0o755)
        prompt = os.path.join(tmp, "prompt.md")
        with open(prompt, "w") as f:
            f.write("Answer.\n")
        transcript = os.path.join(tmp, "transcript.jsonl")
        env = {**os.environ, "PATH": tmp + os.pathsep + os.environ["PATH"], "FAKE_PI_TEXT": text,
               "PROMPT_FILE": prompt, "MODEL": "fake", "BUDGET": "1", "ALLOWED_TOOLS": "",
               "JSON_SCHEMA": json.dumps(SCHEMA), "TRANSCRIPT": transcript}
        p = subprocess.run(["node", os.path.join(ROOT, "run-agent", "pi.mjs")], env=env, capture_output=True, text=True)
        if p.returncode:
            sys.exit(f"pi.mjs exited {p.returncode}:\n{p.stdout}{p.stderr}")
        with open(transcript) as f:
            return json.loads(f.read().splitlines()[-1])


failed = 0
for name, text, subtype, structured in SCENARIOS:
    result = run(text)
    got = (result["subtype"], result.get("structured_output"))
    if got == (subtype, structured):
        print(f"✅ {name}")
    else:
        failed += 1
        print(f"❌ {name}: expected {(subtype, structured)}, got {got}")
sys.exit(1 if failed else 0)
