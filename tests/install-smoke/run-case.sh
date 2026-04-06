#!/usr/bin/env bash
set -euo pipefail

container_cli="${CONTAINER_CLI:-docker}"

if [[ $# -lt 3 ]]; then
    echo "usage: $0 <name> <base-image> <bootstrap-family> [expect-container-engine]" >&2
    exit 1
fi

if ! command -v "${container_cli}" >/dev/null 2>&1; then
    echo "Container CLI not found: ${container_cli}" >&2
    exit 1
fi

name="$1"
base_image="$2"
bootstrap_family="$3"
expect_container_engine="${4:-}"

declare -a build_args=(
    --build-arg "BASE_IMAGE=${base_image}"
    --build-arg "BOOTSTRAP_FAMILY=${bootstrap_family}"
    --build-arg "TEST_NAME=${name}"
)

if [[ -n "${expect_container_engine}" ]]; then
    build_args+=(--build-arg "EXPECT_CONTAINER_ENGINE=${expect_container_engine}")
fi

case "${name}" in
ubuntu-26.04)
    ;;
linuxmint)
    # Linux Mint does not have an official base image, so this case uses Ubuntu
    # and overrides /etc/os-release to exercise the installer's Mint branch.
    build_args+=(
        --build-arg 'OS_RELEASE_NAME=Linux Mint'
        --build-arg 'OS_RELEASE_ID=linuxmint'
        --build-arg 'OS_RELEASE_PRETTY_NAME=Linux Mint'
        --build-arg 'OS_RELEASE_VERSION_CODENAME=resolute'
        --build-arg 'OS_RELEASE_UBUNTU_CODENAME=resolute'
    )
    ;;
fedora)
    ;;
arch)
    ;;
*)
    echo "Unknown install smoke test case: ${name}" >&2
    exit 1
    ;;
esac

if [[ "${container_cli}" == "docker" ]] && docker buildx version >/dev/null 2>&1; then
    docker buildx build \
        --pull \
        --load \
        -f tests/install-smoke/Dockerfile \
        -t "datallog-install-smoke:${name}" \
        "${build_args[@]}" \
        .
else
    "${container_cli}" build \
        --pull \
        -f tests/install-smoke/Dockerfile \
        -t "datallog-install-smoke:${name}" \
        "${build_args[@]}" \
        .
fi
