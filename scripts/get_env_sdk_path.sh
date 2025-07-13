#!/bin/bash

function get_env_sdk_path() {
    cd $(dirname "$0")
    cd ..
    echo $(pwd)/env
}
