#!/bin/bash

source /env/bin/activate || exit 1

pip freeze --local | sort | md5sum | awk '{ print $1}'

find /deploy ! -path '**.git**' ! -path '/deploy/env' ! -path '*__pycache__*' -type f -print0 | sort -z | xargs -0 md5sum | md5sum | awk '{ print $1}'