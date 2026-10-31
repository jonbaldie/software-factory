#!/usr/bin/env bash
set -euo pipefail
root=$(git rev-parse --show-toplevel)
repo=jonbaldie/software-factory-sandbox
branch=exploratory/scout-20261031-0130
clone="$root/.scratch/sandbox"
evidence="$root/docs/exploratory-testing/2026-10-31-evidence"
run_id=
cleanup() {
  if [[ -n "$run_id" ]]; then
    status=$(gh run view "$run_id" -R "$repo" --json status --jq .status 2>/dev/null || true)
    if [[ -n "$status" && "$status" != completed ]]; then gh run cancel "$run_id" -R "$repo" || true; fi
  fi
  if git -C "$clone" ls-remote --exit-code --heads origin "$branch" >/dev/null 2>&1; then
    gh api -X DELETE "repos/$repo/git/refs/heads/$branch" >/dev/null || echo 'CLEANUP: remote branch deletion failed' >&2
  fi
}
trap cleanup EXIT INT TERM
cd "$clone"
[[ -z $(gh pr list -R "$repo" --state open --json number --jq '.[].number') ]]
[[ -z $(gh run list -R "$repo" --status in_progress --json databaseId --jq '.[].databaseId') ]]
[[ -z $(gh run list -R "$repo" --status queued --json databaseId --jq '.[].databaseId') ]]
git switch -c "$branch"
cp "$root/template/.github/factory/scout.sh" .github/factory/scout.sh
cp "$root/template/.github/workflows/factory-scout.yml" .github/workflows/factory-scout.yml
mkdir -p src
printf '%s\n' 'const normal = "TODO(factory): Scout check 78, real comment after a string (sandbox test, close me)";' 'const multiline = `' '// TODO(factory): Scout check 78, real comment after a string (sandbox test, close me)' '`;' '// TODO(factory): Scout check 78, real comment after a string (sandbox test, close me)' 'void normal; void multiline;' > src/exploratory-scout-20261031.js
npm_config_cache="$root/.scratch/npm-cache" npm ci --ignore-scripts > "$evidence/npm-ci.log" 2>&1
npm test > "$evidence/sandbox-test.log" 2>&1
git add .github/factory/scout.sh .github/workflows/factory-scout.yml src/exploratory-scout-20261031.js
git -c user.name='Exploratory test' -c user.email='exploratory@example.invalid' commit -qm 'Add isolated scout exploration fixture'
git push -u origin "$branch"
for n in 1 2; do
  gh workflow run factory-scout.yml -R "$repo" --ref "$branch"
  run_id=
  for i in {1..30}; do
    run_id=$(gh run list -R "$repo" --workflow factory-scout.yml --branch "$branch" --limit 1 --json databaseId --jq '.[0].databaseId // empty')
    if [[ -n "$run_id" && "$run_id" != "${previous:-}" ]]; then break; fi
    sleep 2
  done
  [[ -n "$run_id" && "$run_id" != "${previous:-}" ]]
  echo "run $n: https://github.com/$repo/actions/runs/$run_id"
  gh run watch "$run_id" -R "$repo" --exit-status --interval 5
  gh run view "$run_id" -R "$repo" --log > "$evidence/scout-run-$n.log"
  gh api "repos/$repo/actions/runs/$run_id/jobs" --jq '.jobs[] | {name,conclusion}'
  previous=$run_id
done
run_id=
