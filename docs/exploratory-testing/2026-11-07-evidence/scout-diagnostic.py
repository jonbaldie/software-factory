import importlib.util
import json
from pathlib import Path

root = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('labels', root / 'tests/labels.py')
labels = importlib.util.module_from_spec(spec)
spec.loader.exec_module(labels)

cases = {
    'real comment': ('// TODO(factory): Real work\n', ['Real work']),
    'multiline template data': ('const text = `\n// TODO(factory): Literal data\n`;\n', []),
    'interpolation comment': ('const text = `${\n// TODO(factory): Interpolation work\n1}`;\n', ['Interpolation work']),
}
for attempt in (1, 2):
    for name, (source, expected) in cases.items():
        scenario = dict(name=name, wf='factory-scout.yml', target='issue', event=None,
                        start=[], comments=[], files={'src/example.js': source})
        result = labels.run_scenario(scenario, trace=True)
        print(json.dumps({'attempt': attempt, 'case': name, 'failed': result['failed'],
                          'titles': result['created_issue_titles'],
                          'bodies': result['created_issue_bodies'],
                          'dispatch': result['dispatch'], 'steps': result['log']}, indent=2))
        assert not result['failed']
        assert result['created_issue_titles'] == expected
print('PASS: expected issue titles in both fresh fixture attempts')
