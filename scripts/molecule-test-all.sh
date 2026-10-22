#!/usr/bin/env bash
# Review note: fail through the validated entry point instead of silently finding no scenarios.
# Only manage_users has a validated end-to-end scenario at present.
set -euo pipefail
exec "$(dirname "$0")/test-manage-users.sh" "$@"
