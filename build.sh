#!/usr/bin/env bash
# shellcheck shell=bash
# build.sh
# Copyright (C) 2026 Qompass AI, All rights reserved
# ----------------------------------------
set -euo pipefail
env -u PIP_EXTRA_INDEX_URL \
    -u PIP_INDEX_URL \
    -u PIP_FIND_LINKS \
    ~/.local/bin/buildozer android debug 2>&1 | tee ~/buildozer_debug.log
