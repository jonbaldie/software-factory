#!/usr/bin/env bash
# Installs or upgrades the software factory in the GitHub repo you run it from.
# https://github.com/jonbaldie/software-factory
#
#   curl -fsSL https://raw.githubusercontent.com/jonbaldie/software-factory/v1/install.sh | bash
#
# Safe to rerun. It leaves committing to you.
set -euo pipefail

SOURCE_REPO=jonbaldie/software-factory

usage() {
  cat <<'EOF'
Usage: install.sh [--test-command CMD] [--setup-command CMD] [--ref REF]

Run it from a clone of your GitHub repo. When piping from curl, pass options after `bash -s --`.

  --test-command CMD   Command that runs your tests. Detected as `npm test` when
                       package.json has a test script.
  --setup-command CMD  Command to run before the agent and the tests, such as
                       `npm ci`. Detected as `npm ci` when package-lock.json exists.
                       Pass '' to clear it.
  --ref REF            software-factory version to install. Defaults to the
                       copy next to this script, or v1.
EOF
}

die() {
  echo "install.sh: $*" >&2
  exit 1
}

# The templates next to this script, when it's run from a clone of software-factory.
script_dir=""
if [ -n "${BASH_SOURCE[0]:-}" ] && [ -d "$(dirname "${BASH_SOURCE[0]}")/template" ]; then
  script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
fi
tmp=""
trap '[ -z "$tmp" ] || rm -rf "$tmp"' EXIT

# Everything runs from main, so `curl | bash` reads the whole script before any command can read stdin.
main() {
  local ref="" test_command="" setup_command="" setup_given=false
  while [ $# -gt 0 ]; do
    case "$1" in
      --test-command) [ $# -ge 2 ] || die "--test-command needs a value"; test_command=$2; shift 2 ;;
      --setup-command) [ $# -ge 2 ] || die "--setup-command needs a value"; setup_command=$2; setup_given=true; shift 2 ;;
      --ref) [ $# -ge 2 ] || die "--ref needs a value"; ref=$2; shift 2 ;;
      -h | --help) usage; exit 0 ;;
      *) usage >&2; exit 2 ;;
    esac
  done

  command -v gh >/dev/null || die "install the GitHub CLI first: https://cli.github.com"
  gh auth status >/dev/null 2>&1 || die "log in to the GitHub CLI first: gh auth login"
  local root repo
  root=$(git rev-parse --show-toplevel 2>/dev/null) || die "run this from a clone of your GitHub repo"
  cd "$root"
  repo=$(gh repo view --json nameWithOwner -q .nameWithOwner) || die "couldn't find this clone's GitHub repo"

  # Work out the variables before changing anything, so a missing test command stops the install cleanly.
  local current_test current_setup
  current_test=$(gh variable get FACTORY_TEST_COMMAND --repo "$repo" 2>/dev/null || true)
  current_setup=$(gh variable get FACTORY_SETUP_COMMAND --repo "$repo" 2>/dev/null || true)
  if [ -z "$test_command" ]; then
    if [ -n "$current_test" ]; then
      test_command=$current_test
    elif [ -f package.json ] && grep -Eq '"test"[[:space:]]*:' package.json; then
      test_command="npm test"
    else
      die "couldn't detect how to run your tests. Rerun with --test-command 'your test command'."
    fi
  fi
  if ! $setup_given; then
    if [ -n "$current_setup" ]; then
      setup_command=$current_setup
    elif [ -f package-lock.json ]; then
      setup_command="npm ci"
    fi
  fi

  local src
  if [ -z "$ref" ] && [ -n "$script_dir" ]; then
    src=$script_dir
    echo "Installing the software factory into $repo from $src"
  else
    ref=${ref:-v1}
    echo "Installing the software factory into $repo from $SOURCE_REPO@$ref"
    tmp=$(mktemp -d)
    gh api "repos/$SOURCE_REPO/tarball/$ref" >"$tmp/factory.tar.gz" || die "couldn't download $SOURCE_REPO@$ref"
    tar -xzf "$tmp/factory.tar.gz" -C "$tmp" --strip-components 1
    src=$tmp
  fi

  echo
  echo "Files"
  (cd "$src/template" && find .github -type f) | sort | while IFS= read -r file; do
    local state=updated
    if [ ! -f "$file" ]; then
      state=added
    elif cmp -s "$src/template/$file" "$file"; then
      state=unchanged
    fi
    mkdir -p "$(dirname "$file")"
    cp "$src/template/$file" "$file"
    printf '  %-10s %s\n' "$state" "$file"
  done

  echo
  echo "Labels"
  local name color description
  while IFS='|' read -r name color description; do
    gh label create "$name" --repo "$repo" --color "$color" --description "$description" --force </dev/null >/dev/null
    echo "  $name"
  done <<'EOF'
needs-triage|c5def5|Maintainer needs to evaluate this issue
needs-info|d876e3|Waiting on reporter for more information
ready-for-agent|0e8a16|Fully specified. Adding this starts the factory
ready-for-human|b60205|Requires human implementation
wontfix|ffffff|Will not be actioned
agent:working|fbca04|The implementer agent is on it
agent:review|1d76db|Reviewer agent is checking this PR
agent:changes-requested|d93f0b|Fixer agent is addressing review feedback
agent:approved|0e8a16|Reviewer approved; factory merged it
agent:failed|000000|A factory stage crashed. See the linked run
EOF
  # The category labels pick the implementer's method. Most repos have them from GitHub's defaults, so they're only created when missing.
  local existing
  existing=$(gh label list --repo "$repo" --limit 1000 --json name -q '.[].name')
  while IFS='|' read -r name color description; do
    if grep -qix "$name" <<<"$existing"; then
      echo "  $name (already there)"
    else
      gh label create "$name" --repo "$repo" --color "$color" --description "$description" </dev/null >/dev/null
      echo "  $name"
    fi
  done <<'EOF'
bug|d73a4a|Something isn't working
enhancement|a2eeef|New feature or request
EOF

  echo
  echo "Actions"
  local permissions_ok=true default_permissions
  if [ "$(gh api "repos/$repo/actions/permissions/workflow" -q .can_approve_pull_request_reviews 2>/dev/null)" = true ]; then
    echo "  already allowed to create and approve pull requests"
  elif default_permissions=$(gh api "repos/$repo/actions/permissions/workflow" -q .default_workflow_permissions 2>/dev/null) &&
    gh api -X PUT "repos/$repo/actions/permissions/workflow" \
      -f default_workflow_permissions="$default_permissions" -F can_approve_pull_request_reviews=true >/dev/null 2>&1; then
    echo "  now allowed to create and approve pull requests"
  else
    permissions_ok=false
    echo "  ! couldn't allow Actions to create and approve pull requests. This needs admin access, and an organisation setting can block it."
  fi

  echo
  echo "Variables"
  if [ "$test_command" != "$current_test" ]; then
    gh variable set FACTORY_TEST_COMMAND --repo "$repo" --body "$test_command" </dev/null
  fi
  echo "  FACTORY_TEST_COMMAND = $test_command"
  if [ -n "$setup_command" ]; then
    if [ "$setup_command" != "$current_setup" ]; then
      gh variable set FACTORY_SETUP_COMMAND --repo "$repo" --body "$setup_command" </dev/null
    fi
    echo "  FACTORY_SETUP_COMMAND = $setup_command"
  else
    if [ -n "$current_setup" ]; then
      gh variable delete FACTORY_SETUP_COMMAND --repo "$repo" </dev/null
    fi
    echo "  FACTORY_SETUP_COMMAND (none)"
  fi

  echo
  echo "Secrets"
  local harness secrets secret_ok=false wanted=OPENROUTER_API_KEY
  harness=$(gh variable get FACTORY_HARNESS --repo "$repo" 2>/dev/null || true)
  secrets=$(gh secret list --repo "$repo" --json name -q '.[].name' 2>/dev/null || true)
  if [ "$harness" = claude ]; then
    wanted=ANTHROPIC_API_KEY
    if grep -Eqx 'ANTHROPIC_API_KEY|CLAUDE_CODE_OAUTH_TOKEN' <<<"$secrets"; then secret_ok=true; fi
  elif grep -qx OPENROUTER_API_KEY <<<"$secrets"; then
    secret_ok=true
  fi
  if $secret_ok; then
    echo "  the agent's API key is set"
  else
    echo "  ! $wanted is missing"
  fi

  local step=1
  echo
  echo "Next"
  if ! $secret_ok; then
    echo "  $step. Add the agent's API key. Give it its own credit limit. This prompts for the value:"
    echo "       gh secret set $wanted --repo $repo"
    step=$((step + 1))
  fi
  if ! $permissions_ok; then
    echo "  $step. Ask an admin to tick Settings → Actions → General → Allow GitHub Actions to create and approve pull requests."
    step=$((step + 1))
  fi
  echo "  $step. Review the changes and commit them. Then push them to the default branch, or merge them in a pull request"
  echo "     if the branch is protected. The workflows only run from the default branch."
  step=$((step + 1))
  echo "  $step. Add the ready-for-agent label to a fully specified issue."
}

main "$@"
