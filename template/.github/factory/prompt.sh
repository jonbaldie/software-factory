#!/usr/bin/env bash
# Build shared prompt sections on stdout, using only trusted factory files.
set -euo pipefail
stage=$1
number=$2
case "$stage" in
  implement|review|fix) ;;
  *) echo "Unknown prompt stage: $stage" >&2; exit 1 ;;
esac
if [ -z "${TEST_COMMAND:-}" ]; then
  echo "::error::Set the FACTORY_TEST_COMMAND repository variable to the command that runs your tests." >&2
  exit 1
fi

if [ "$stage" = implement ]; then
  # Implement runs on the default branch, before switching to any saved work.
  prompts=$(cd "$(dirname "$0")" && pwd)
  issues=$number
else
  # Neither the helper nor its inputs may come from the PR's checkout.
  base=$(gh pr view "$number" --json baseRefName -q .baseRefName)
  prompts="$RUNNER_TEMP/factory"
  mkdir "$prompts"
  git archive "origin/$base:.github/factory" | tar -x -C "$prompts"
  issues=$(gh pr view "$number" --json closingIssuesReferences -q '.closingIssuesReferences[].number')
fi
labels=$(for n in $issues; do gh issue view "$n" --json labels -q '.labels[].name'; done)
cat "$prompts/$stage.md"
# One category rule for implementer, reviewer and fixer; bug takes precedence.
for category in bug enhancement; do
  if grep -qix "$category" <<<"$labels"; then echo; cat "$prompts/$category.md"; break; fi
done
printf '\n## Test command\n\n```sh\n%s\n```\n\n' "$TEST_COMMAND"
for n in $issues; do
  gh issue view "$n" --json number,title,body,comments | jq -r -f "$prompts/ticket.jq"
done
