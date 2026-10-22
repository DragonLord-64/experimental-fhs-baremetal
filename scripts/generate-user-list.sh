#!/usr/bin/env bash
#=====================================================================
# generate_fhs_users_yaml.sh
#
# Usage:
#   ./generate_fhs_users_yaml.sh <ssh‑key‑dir> [output.yaml]
#
#   * <ssh‑key‑dir>  – directory that contains the public‑key files
#   * [output.yaml] – optional file to write the YAML to.
#                     If omitted the YAML is printed to STDOUT.
#
# The script produces:
#
# fhs_users:
#   - name: alice
#     ssh_keys:
#       - "ssh-ed25519 AAAA… alice@host"
#
#=====================================================================

set -euo pipefail          # fail fast, protect against undefined vars

# --------------------------------------------------------------------
# Escape only the characters that need escaping inside a double‑quoted
# YAML scalar: backslash and double‑quote.
# --------------------------------------------------------------------
yaml_escape() {
    local raw=$1
    # First escape backslashes, then double quotes.
    printf '%s' "$raw" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'
}
# --------------------------------------------------------------------

# --------------------------- Argument handling -----------------------
if (( $# < 1 )); then
    echo "Usage: $0 <ssh-key-dir> [output.yaml]" >&2
    exit 1
fi

KEYDIR="${1%/}"                # strip a possible trailing slash
OUTFILE="${2:-}"               # empty → write to STDOUT

if [[ ! -d "$KEYDIR" ]]; then
    echo "Error: '$KEYDIR' is not a directory." >&2
    exit 1
fi

# Redirect stdout to the output file if one was given.
if [[ -n "$OUTFILE" ]]; then
    exec >"$OUTFILE"
fi

# --------------------------------------------------------------------
# Begin the YAML document
# --------------------------------------------------------------------
printf "fhs_users:\n"

# Make the glob expand to an empty list instead of the pattern itself.
shopt -s nullglob

for keyfile in "$KEYDIR"/*; do
    [[ -f "$keyfile" ]] || continue               # skip non‑regular files

    # ----------------- 1️⃣  Derive the user name --------------------
    filename=$(basename -- "$keyfile")
    name="${filename%.*}"                          # strip the last extension

    # ----------------- 2️⃣  Read the key ---------------------------
    # Use `tr -d '\n'` to remove a trailing newline (most public‑key
    # files end with one).  This keeps the YAML on a single line.
    raw_key=$(tr -d '\n' <"$keyfile")

    # ----------------- 3️⃣  Escape it for YAML ----------------------
    esc_key=$(yaml_escape "$raw_key")

    # ----------------- 4️⃣  Emit the entry -------------------------
    printf "  - name: %s\n    ssh_keys:\n      - \"%s\"\n" "$name" "$esc_key"
done