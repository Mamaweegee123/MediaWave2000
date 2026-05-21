#!/bin/bash

cd "$(dirname "$0")"

export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8

source venv/bin/activate

python channelsurfer2000.py
