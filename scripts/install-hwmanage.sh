#!/usr/bin/env bash
# Link the repository command into the provisioning container's PATH.
set -euo pipefail

if (( $# > 1 )); then
    echo "Usage: $0 [bindir]" >&2
    exit 2
fi

script_path=$(readlink -f -- "${BASH_SOURCE[0]}")
source_path="$(dirname -- "$script_path")/hwmanage"
bindir=${1:-/usr/local/bin}
if [[ ! -x "$source_path" ]]; then
    echo "hwmanage is missing or not executable: $source_path" >&2
    exit 1
fi
mkdir -p -- "$bindir"
link_path="$bindir/hwmanage"
if [[ -L "$link_path" ]] && [[ $(readlink -f -- "$link_path") == "$source_path" ]]; then
    echo "Already installed: $link_path -> $source_path"
elif [[ -e "$link_path" || -L "$link_path" ]]; then
    echo "Refusing to overwrite: $link_path" >&2
    exit 1
else
    ln -s -- "$source_path" "$link_path"
    echo "Installed: $link_path -> $source_path"
fi
