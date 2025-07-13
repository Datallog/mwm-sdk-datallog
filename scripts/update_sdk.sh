#!/bin/bash
cd $(dirname "$0")/../scripts

# curl git gcc make zlib1g-dev

source ./log.sh
source ./get_env_sdk_path.sh

function update_sdk() {
    git pull origin master
    if [ $? -ne 0 ]; then
        log_error "Failed to update the SDK repository. Please check your network connection or repository access."
        exit 1
    fi
    log_info "SDK repository updated successfully."
}
