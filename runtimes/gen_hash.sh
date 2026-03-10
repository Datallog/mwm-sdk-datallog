#!/bin/bash

UV_BIN="${UV_BIN:-/usr/local/bin/uv}"
if command -v uv >/dev/null 2>&1; then
    UV_BIN="$(command -v uv)"
fi

REQUIREMENTS_HASH=$("$UV_BIN" pip freeze --python /env/bin/python | sort | md5sum | awk '{ print $1}')
APP_HASH=$(find /project -path '*/.git*' -prune -o -path '/project/env*' -prune -o -path '*__pycache__*' -prune -o -type f -print0 | sort -z | xargs -0r md5sum | md5sum | awk '{ print $1}')
echo
echo
echo DATALLOG_REQUIREMENTS_HASH=$REQUIREMENTS_HASH
echo DATALLOG_APP_HASH=$APP_HASH
