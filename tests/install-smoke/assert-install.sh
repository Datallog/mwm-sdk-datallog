#!/usr/bin/env bash
set -euo pipefail

export HOME="${HOME:-/root}"
export USER="${USER:-root}"
export PATH="${HOME}/.local/bin:${PATH}"

test -d "${HOME}/.datallog"
test -d "${HOME}/.datallog/.git"
test -x "${HOME}/.datallog/bin/datallog"
test -f "${HOME}/.bashrc"
test -f "${HOME}/.bash_profile"
grep -q 'export DATALLOG_ROOT="$HOME/.datallog"' "${HOME}/.bashrc"
grep -q 'export DATALLOG_ROOT="$HOME/.datallog"' "${HOME}/.bash_profile"
command -v uv >/dev/null

if [[ -n "${EXPECT_CONTAINER_ENGINE:-}" ]]; then
    grep -q "\"container_engine\": \"${EXPECT_CONTAINER_ENGINE}\"" "${HOME}/.datallog/settings.json"
fi

echo "Installer smoke test passed for ${TEST_NAME:?}"
