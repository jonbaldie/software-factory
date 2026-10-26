#!/usr/bin/env bash
# A conditional caller must not suppress errexit inside the configured command.
# Keep handled failures (if, ||, etc.) as ordinary Bash semantics, not string parsing.
set -eo pipefail
bash --noprofile --norc -eo pipefail -c "$1" 2>&1 | tee "$2"
