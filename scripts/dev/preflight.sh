#!/usr/bin/env bash
# Pre-push preflight for this repository. The global pre-push hook
# (~/.githooks/pre-push) runs scripts/dev/preflight.sh when a repository ships
# one. Needs git and the installed Library runtime (ccore).
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

# Toolchain currency gate (`ccore toolchains check`). A failure
# prints the check's JSON envelope and blocks the push.
toolchain_status=0
toolchain_report="$(ccore toolchains check)" || toolchain_status=$?
if [ "$toolchain_status" -ne 0 ]; then
  printf '%s\n' "$toolchain_report" >&2
  exit "$toolchain_status"
fi
