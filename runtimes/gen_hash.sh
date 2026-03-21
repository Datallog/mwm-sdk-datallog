#!/bin/bash

# Check if uv is available
USE_UV=false
if command -v uv >/dev/null 2>&1; then
    USE_UV=true
    UV_BIN="$(command -v uv)"
elif [ -f "/usr/local/bin/uv" ]; then
    USE_UV=true
    UV_BIN="/usr/local/bin/uv"
fi

function run_pip_freeze {
    if [ "$USE_UV" = true ]; then
        "$UV_BIN" pip freeze --python /env/bin/python | sort
    else
        /env/bin/python -m pip freeze | sort
    fi
}

REQUIREMENTS_HASH=$(run_pip_freeze | md5sum | awk '{ print $1}')
APP_HASH=$(find /project -path '*/.git*' -prune -o -path '/project/env*' -prune -o -path '*__pycache__*' -prune -o -type f -print0 | sort -z | xargs -0r md5sum | md5sum | awk '{ print $1}')
echo
echo
echo DATALLOG_REQUIREMENTS_HASH=$REQUIREMENTS_HASH
echo DATALLOG_APP_HASH=$APP_HASH
