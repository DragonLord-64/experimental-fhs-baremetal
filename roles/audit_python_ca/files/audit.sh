#!/bin/bash
# Read-only triage for the October 2026 eMudhra/emSign CA incident.
# Does not execute Python or import packages from inspected environments.
set -u
set -o pipefail

audit_bundle() {
    local bundle=$1 subjects core
    core="${bundle%/*}/core.py"
    if [[ ${bundle##*/} == cacert.pem && -r "$core" ]] &&
       grep -Eq "^DEBIAN_CA_CERTS_PATH = ['/\"]*/etc/ssl/certs/ca-certificates.crt['\"]" "$core" &&
       tail -n 16 "$core" | grep -Eq '^    return DEBIAN_CA_CERTS_PATH$'; then
        printf 'SYSTEM-CA override: %s (bundled PEM is unused by this patched certifi)\n' "$bundle"
        return 0
    fi
    if ! subjects=$(openssl crl2pkcs7 -nocrl -certfile "$bundle" |
                    openssl pkcs7 -print_certs -noout); then
        printf 'UNKNOWN: could not parse %s\n' "$bundle"
        return 2
    fi
    if [[ -z "$subjects" ]]; then
        printf 'UNKNOWN: no certificates decoded from %s\n' "$bundle"
        return 2
    fi
    if grep -Fq 'emSign ECC Root CA - G3' <<< "$subjects"; then
        printf 'REVIEW: removed emSign ECC Root CA - G3 is present in %s\n' "$bundle"
        return 1
    fi
    printf 'ROOT-ABSENT: %s\n' "$bundle"
}

main() {
    local version file rc find_pid findings=0 unknown=0 venvs=0 bundles=0
    local -a roots=()
    printf 'Read-only eMudhra/emSign audit; certificate presence is not proof of intrusion.\n'
    printf 'Scope: Ubuntu CA package; venv markers and pip/certifi metadata; named CA bundles.\n'

    if [[ -r /etc/os-release ]]; then
        . /etc/os-release
        printf 'OS: %s\n' "${PRETTY_NAME:-unknown}"
    fi
    version=$(dpkg-query -W -f='${Version}' ca-certificates 2>/dev/null) || version=missing
    printf 'ca-certificates: %s\n' "$version"
    if [[ ${ID:-} == ubuntu && ${VERSION_ID:-} == 24.04 && $version != missing ]]; then
        if dpkg --compare-versions "$version" ge 20260816ubuntu0.24.04.1; then
            printf 'PACKAGE-OK: meets Ubuntu 24.04 USN-8944-1 minimum.\n'
        else
            printf 'REVIEW: ca-certificates is below the Ubuntu 24.04 security minimum.\n'
            findings=$((findings + 1))
        fi
    else
        printf 'UNKNOWN: package-version gate is only defined here for Ubuntu 24.04.\n'
        unknown=$((unknown + 1))
    fi

    if [[ ! -r /etc/ssl/certs/ca-certificates.crt ]]; then
        printf 'UNKNOWN: system CA bundle missing or unreadable.\n'
        unknown=$((unknown + 1))
    fi
    for file in /etc/ssl/certs/ca-certificates.crt /opt /home /root /usr/local/lib /usr/lib; do
        [[ -e "$file" ]] && roots+=("$file")
    done
    while IFS= read -r -d '' file; do
        case "$file" in
            */pyvenv.cfg)
                printf 'VENV: %s\n' "${file%/pyvenv.cfg}"
                venvs=$((venvs + 1))
                ;;
            */METADATA)
                awk '/^Version:/ {print "VERSION: " FILENAME " -> " $2; exit}' "$file" || unknown=$((unknown + 1))
                ;;
            *)
                audit_bundle "$file"
                rc=$?
                bundles=$((bundles + 1))
                case "$rc" in
                    1) findings=$((findings + 1));;
                    2) unknown=$((unknown + 1));;
                esac
                ;;
        esac
    done < <(find "${roots[@]}" -type f \( -name pyvenv.cfg -o -name cacert.pem -o -name ca-certificates.crt -o -path '*/pip-*.dist-info/METADATA' -o -path '*/certifi-*.dist-info/METADATA' \) -print0)
    find_pid=$!
    wait "$find_pid" || unknown=$((unknown + 1))

    printf 'SUMMARY: %s venv markers, %s bundles, %s findings, %s unknown checks.\n' "$venvs" "$bundles" "$findings" "$unknown"
    printf 'An old Ubuntu pip version alone does not establish exposure: check SYSTEM-CA and the system bundle.\n'
    printf 'Does not cover containers, virtualenv seed archives, custom CA paths, symlink-only trees, runtime memory, or credential theft.\n'
    (( unknown == 0 )) || return 2
    (( findings == 0 )) || return 1
}

if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
    main "$@"
fi
