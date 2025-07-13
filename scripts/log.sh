#!/bin/bash

log_debug() {
    if [ "$DATALLLOG_LOG_LEVEL" == "debug" ]; then
        echo "DEBUG: $1"
    fi
}

log_info() {
    if [ "$DATALLLOG_LOG_LEVEL" != "error" ]; then
        echo "$1"
    fi
}

log_warn() {
    if [ "$DATALLLOG_LOG_LEVEL" != "error" ]; then
        echo "WARNING: $1"
    fi
    echo "WARNING: $1" >&2
}

log_error() {
    echo "ERROR: $1" >&2
}
