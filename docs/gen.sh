#!/usr/bin/env bash
# shellcheck shell=bash
set -euo pipefail

pdoc \
    --output-dir docs/html \
    --docformat google \
    core config gui mobile main
