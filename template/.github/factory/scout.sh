#!/usr/bin/env bash
set -eo pipefail

echo "## 🔭 Scouted TODOs" >> "$GITHUB_STEP_SUMMARY"
# Every issue title, open or closed, however old. `gh issue list` caps at a limit and lists newest first,
# so the oldest tickets would drop out. The REST list includes PRs, which have a pull_request key.
existing=$(gh api --paginate "repos/$GH_REPO/issues?state=all&per_page=100" \
  --jq '.[] | select(.pull_request | not) | .title')
in_js_string() {
  local s=$1 quote= prev= c rest i
  for ((i = 0; i < ${#s}; i++)); do
    c=${s:i:1}
    if [[ -n $quote ]]; then
      if [[ $c == '\' ]]; then
        i=$((i + 1))
      elif [[ $c == "$quote" ]]; then
        quote=
      fi
    elif [[ $c$prev == '//' ]]; then
      return 1
    elif [[ $c == / && ${s:i+1:1} == '*' ]]; then
      rest=${s:i+2}
      [[ $rest == *'*/'* ]] || return 1
      rest=${rest#*'*/'}
      i=$((${#s} - ${#rest} - 1))
      c=
    elif [[ $c == '`' || ( $c == [\"\'] && $prev != [[:alnum:]_\$] ) ]]; then
      quote=$c
    fi
    prev=$c
  done
  [[ -n $quote ]]
}
# -z ends the path and line number with NULs, so a path may contain colons. -I skips binary files, whose
# "Binary file X matches" line has no NULs and would throw the reads out of step.
{ git grep -z -n -I -F 'TODO(factory):' -- ':(exclude,icase)*.md' ':(exclude,icase)*.markdown' ':!.github' || true; } |
while IFS= read -r -d '' file && IFS= read -r -d '' line && IFS= read -r hit; do
  opener=${hit%%TODO(factory):*}
  title=${hit#*TODO(factory):}
  if [[ $file =~ \.[cCmM]?[jJtT][sS][xX]?$ ]]; then
    while in_js_string "$opener" && [[ $title == *'TODO(factory):'* ]]; do
      opener+="TODO(factory):${title%%TODO(factory):*}"
      title=${title#*TODO(factory):}
    done
    if in_js_string "$opener"; then
      echo "- Skipped TODO in a string at $file:$line." >> "$GITHUB_STEP_SUMMARY"
      continue
    fi
  fi
  title=${title#"${title%%[![:space:]]*}"}
  [[ $opener == *'/*'* ]] && title=${title%%'*/'*}
  [[ $opener == *'<!--'* ]] && title=${title%%'-->'*}
  title=${title%"${title##*[![:space:]]}"}
  if [[ -z $title ]]; then
    echo "- Skipped blank TODO at $file:$line (no text)." >> "$GITHUB_STEP_SUMMARY"
    continue
  fi
  if grep -Fxq -- "$title" <<<"$existing"; then
    echo "- Already filed: $title" >> "$GITHUB_STEP_SUMMARY"
    continue
  fi
  # Percent-encode the path so a space doesn't end GitHub's autolink. Slashes and colons stay as they are;
  # a literal "%2F" in a name is already "%252F" by then.
  path=$(jq -rn --arg p "$file" '$p | @uri | gsub("%2F"; "/") | gsub("%3A"; ":")')
  printf 'Found by the scout at %s/%s/blob/%s/%s#L%s. Delete that `TODO(factory):` comment as part of the change.\n' \
    "$GITHUB_SERVER_URL" "$GH_REPO" "$GITHUB_SHA" "$path" "$line" > "$RUNNER_TEMP/body.md"
  url=$(gh issue create --title "$title" --body-file "$RUNNER_TEMP/body.md" --label needs-triage)
  existing="$existing"$'\n'"$title"
  echo "- Filed $url: $title" >> "$GITHUB_STEP_SUMMARY"
  # Labels added with GITHUB_TOKEN don't trigger workflows, so start triage explicitly.
  if ! gh workflow run factory-triage.yml -f issue="${url##*/}"; then
    echo "- Couldn't start triage for $url. Remove and re-add \`needs-triage\` there to start it." >> "$GITHUB_STEP_SUMMARY"
    exit 1
  fi
done
