#!/bin/bash

function reset {
    rm -rf /env/*
    rm -rf /env/.*

    python3 -m venv /env || exit 1
    source /env/bin/activate || exit 1
    pip install -r /requirements.txt || exit 1
    pip freeze --local >/requirements.txt || exit 1
    exit 0
}

cd /env || exit 1
if [ ! -d "bin" ]; then
    python3 -m ensurepip || exit 1
    python3 -m venv . || exit 1
fi

source /env/bin/activate || reset

current_packages=$(pip freeze | sort | tr '\n' ' ')
requirements=$(cat /requirements.txt | sort | tr '\n' ' ')

if [ "$current_packages" != "$requirements" ]; then
    reset
fi

if [ "$1" == "packages" ]; then
    pip install "${@:2}"
fi

if [ "$1" == "requirements" ]; then
    pip install -r /new_requirements.txt
fi

pip install --upgrade datallog
pip freeze --local > /requirements.txt

exit 0
