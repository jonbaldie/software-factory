import ast
import json
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[3]
source = ast.parse((root / 'tests/install.py').read_text())
fake = next(ast.literal_eval(n.value) for n in source.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'FAKE_GH' for t in n.targets))

with tempfile.TemporaryDirectory(dir=root / '.scratch') as temp:
    base = Path(temp)
    repo, bin_dir = base / 'repo', base / 'bin'
    repo.mkdir()
    bin_dir.mkdir()
    gh = bin_dir / 'gh'
    gh.write_text(fake)
    gh.chmod(0o755)
    state = base / 'gh.json'
    state.write_text(json.dumps({'variables': {}, 'labels': [], 'calls': [], 'fail_reads': False, 'secrets': []}))
    env = dict(os.environ, PATH=f'{bin_dir}:{os.environ["PATH"]}', FAKE_GH_STATE=str(state), npm_config_cache=str(base / 'npm-cache'))
    subprocess.run(['git', 'init', '-q', str(repo)], check=True)
    (repo / 'package.json').write_text('{"name":"fixture","version":"1.0.0","scripts":{"test":"node --test"}}\n')
    (repo / 'package-lock.json').write_text('{"name":"fixture","version":"1.0.0","lockfileVersion":3,"requires":true,"packages":{"":{"name":"fixture","version":"1.0.0"}}}\n')
    subprocess.run(['npm', 'ci', '--ignore-scripts'], cwd=repo, env=env, check=True, stdout=subprocess.DEVNULL)

    def install(label, *args, expected=0):
        result = subprocess.run(['bash', str(root / 'install.sh'), *args], cwd=repo, env=env, capture_output=True, text=True)
        variables = json.loads(state.read_text())['variables']
        print(f'{label}: exit={result.returncode}, variables={json.dumps(variables, sort_keys=True)}')
        print(result.stdout + result.stderr)
        assert result.returncode == expected
        return variables

    variables = install('fresh install')
    assert variables == {'FACTORY_TEST_COMMAND': 'npm test', 'FACTORY_SETUP_COMMAND': 'npm ci'}
    assert (repo / '.github/workflows/factory-scout.yml').read_bytes() == (root / 'template/.github/workflows/factory-scout.yml').read_bytes()
    variables = install('disable setup', '--setup-command', '')
    assert variables == {'FACTORY_TEST_COMMAND': 'npm test', 'FACTORY_SETUP_DISABLED': 'true'}
    variables = install('reinstall after disable')
    assert variables == {'FACTORY_TEST_COMMAND': 'npm test', 'FACTORY_SETUP_DISABLED': 'true'}
    variables = install('enable setup', '--setup-command', 'npm ci')
    assert variables == {'FACTORY_TEST_COMMAND': 'npm test', 'FACTORY_SETUP_COMMAND': 'npm ci'}
    variables = install('reinstall after enable')
    assert variables == {'FACTORY_TEST_COMMAND': 'npm test', 'FACTORY_SETUP_COMMAND': 'npm ci'}
    before = (repo / '.github/factory/implement.md').read_bytes()
    outside = repo / 'shared.md'
    outside.write_text('existing shared prompt\n')
    (repo / '.github/factory/review.md').unlink()
    (repo / '.github/factory/review.md').symlink_to('../../shared.md')
    variables = install('refuse symlinked destination', expected=1)
    assert outside.read_text() == 'existing shared prompt\n'
    assert (repo / '.github/factory/implement.md').read_bytes() == before
    assert variables == {'FACTORY_TEST_COMMAND': 'npm test', 'FACTORY_SETUP_COMMAND': 'npm ci'}
    (repo / '.github/factory/review.md').unlink()
    install('retry after removing symlink')
    assert (repo / '.github/factory/review.md').read_bytes() == (root / 'template/.github/factory/review.md').read_bytes()
    print('PASS: output, saved configuration, installed files, refusal and retry verified')
