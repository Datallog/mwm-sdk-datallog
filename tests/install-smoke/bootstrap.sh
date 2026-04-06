#!/usr/bin/env bash
set -euo pipefail

case "${BOOTSTRAP_FAMILY:?}" in
apt)
    apt-get update
    apt-get install -y --no-install-recommends bash ca-certificates curl sudo
    ;;
dnf)
    dnf install -y bash ca-certificates curl shadow-utils sudo
    dnf clean all
    ;;
pacman)
    pacman -Syu --noconfirm --needed bash ca-certificates curl shadow sudo
    pacman -Scc --noconfirm || true
    ;;
*)
    echo "Unsupported BOOTSTRAP_FAMILY: ${BOOTSTRAP_FAMILY}" >&2
    exit 1
    ;;
esac
