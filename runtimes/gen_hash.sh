#!/bin/bash

source /env/bin/activate || exit 1

REQUIREMENTS_HASH=$(pip freeze --local | sort | md5sum | awk '{ print $1}')
APP_HASH=$(find /deploy ! -path '**.git**' ! -path '/deploy/env' ! -path '*__pycache__*' -type f -print0 | sort -z | xargs -0 md5sum | md5sum | awk '{ print $1}')
echo
echo
echo DATALLOG_REQUIREMENTS_HASH=$REQUIREMENTS_HASH
echo DATALLOG_APP_HASH=$APP_HASH