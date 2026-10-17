#!/usr/bin/env bash
# Build the static site into ./site
set -euo pipefail
exec "$(dirname "$0")/build.py" "$@"
