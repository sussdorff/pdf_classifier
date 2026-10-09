#!/usr/bin/env bash
# Pre-push preflight for this repository. The global pre-push hook
# (~/.githooks/pre-push) runs scripts/dev/preflight.sh when a repository ships
# one. Needs git and python3 only.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

# Toolchain currency gate (.agents/standards/toolchains/check.md). A failure
# prints the check's JSON envelope and blocks the push.
toolchain_status=0
toolchain_report="$(python3 .agents/standards/toolchains/scripts/check_toolchain_versions.py)" || toolchain_status=$?
if [ "$toolchain_status" -ne 0 ]; then
  printf '%s\n' "$toolchain_report" >&2
  exit "$toolchain_status"
fi
