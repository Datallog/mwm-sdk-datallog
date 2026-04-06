#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${repo_root}"

container_cli="${CONTAINER_CLI:-docker}"

CONTAINER_CLI="${container_cli}" bash tests/install-smoke/run-case.sh ubuntu-26.04 ubuntu:26.04 apt
CONTAINER_CLI="${container_cli}" bash tests/install-smoke/run-case.sh linuxmint ubuntu:26.04 apt
CONTAINER_CLI="${container_cli}" bash tests/install-smoke/run-case.sh fedora fedora:latest dnf podman
CONTAINER_CLI="${container_cli}" bash tests/install-smoke/run-case.sh arch archlinux:latest pacman
