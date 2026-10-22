#!/usr/bin/env bash
# Compatibility entry point: start the persistent lab, then run smoke checks.
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "$0")" && pwd)
"$script_dir/lifecycle.sh" up
"$script_dir/lifecycle.sh" test
