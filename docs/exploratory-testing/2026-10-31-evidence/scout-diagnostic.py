import importlib.util
import json
from pathlib import Path

root = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('labels', root / 'tests/labels.py')
labels = importlib.util.module_from_spec(spec)
spec.loader.exec_module(labels)

cases = {
    'comment': '// TODO(factory): Real work\n',
    'single-line string': 'const text = "// TODO(factory): Literal data";\n',
    'multiline string': 'const text = `\n// TODO(factory): Literal data\n`;\n',
}
for attempt in (1, 2):
    for name, source in cases.items():
        scenario = dict(name=name, wf='factory-scout.yml', target='issue', event=None,
                        start=[], comments=[], files={'src/example.js': source})
        result = labels.run_scenario(scenario, trace=True)
        print(json.dumps({'attempt': attempt, 'case': name, 'failed': result['failed'],
                          'created_issue_titles': result['created_issue_titles'],
                          'created_issue_bodies': result['created_issue_bodies'],
                          'dispatch': result['dispatch'], 'summary': result['summary'],
                          'steps': result['log']}, indent=2))
        assert not result['failed']
        expected = ['Real work'] if name == 'comment' else [] if name == 'single-line string' else ['Literal data']
        assert result['created_issue_titles'] == expected
