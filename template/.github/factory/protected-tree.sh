#!/usr/bin/env bash
set -euo pipefail
export GIT_NO_REPLACE_OBJECTS=1

history_digest() {
  git -c core.commitGraph=false rev-list --parents "$1" | sha256sum | cut -d' ' -f1
}

case "${1:-}" in
  capture-revision)
    git rev-parse --verify "$2^{tree}"
    ;;
  capture-history)
    history=$(history_digest "$2") || exit 1
    printf '%s\n' "$history"
    ;;
  capture-index)
    conflicts=$(git diff --name-only --diff-filter=U -- .github) || exit 1
    if [ -n "$conflicts" ]; then
      echo "Protected files have merge conflicts" >&2
      exit 1
    fi
    tmp=$(mktemp -d)
    trap 'rm -rf "$tmp"' EXIT
    export GIT_INDEX_FILE="$tmp/index"
    git read-tree --empty
    env -u GIT_INDEX_FILE git ls-files --stage -z -- .github | git update-index -z --index-info
    git write-tree
    ;;
  clean)
    status=$(git status --porcelain -- .github) || exit 1
    [ -z "$status" ]
    ;;
  verify)
    if [ "$#" -ne 2 ] && [ "$#" -ne 4 ]; then exit 2; fi
    baseline=$2
    if [ "$#" -eq 4 ]; then
      history=$(history_digest "$3") || exit 1
      [ "$history" = "$4" ] || exit 1
      trusted_merge_base=$(git -c core.commitGraph=false merge-base HEAD "$3") || exit 1
      git -c core.commitGraph=false merge-base --is-ancestor "$trusted_merge_base" "$3" || exit 1
      actual=$(git cat-file commit "$trusted_merge_base" | git hash-object -t commit --stdin) || exit 1
      [ "$actual" = "$trusted_merge_base" ] || exit 1
      baseline=$trusted_merge_base
    fi
    root=$(git rev-parse --verify "$baseline^{tree}")
    verify_tree() {
      local actual
      actual=$(git cat-file tree "$1" | git hash-object -t tree --stdin) || return 1
      [ "$actual" = "$1" ]
    }
    verify_tree "$root"
    objects=$(git ls-tree -r -t --format='%(objecttype) %(objectname)' "$root" -- .github)
    while read -r type oid; do
      if [ "$type" = tree ]; then verify_tree "$oid"; fi
    done <<< "$objects"
    if git diff --cached --quiet "$baseline" -- .github; then exit 0; fi
    git diff --cached --name-only "$baseline" -- .github
    exit 1
    ;;
  *)
    echo "Usage: protected-tree.sh capture-revision REV | capture-history REV | capture-index | clean | verify TREE [START HISTORY]" >&2
    exit 2
    ;;
esac
