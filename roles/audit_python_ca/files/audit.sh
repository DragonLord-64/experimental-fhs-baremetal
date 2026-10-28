#!/bin/bash
# Read-only triage for the October 2026 eMudhra/emSign CA incident.
# Does not execute Python or import packages from inspected environments.
set -u
set -o pipefail

environment_for() {
    local file=$1 parent
    parent=${file%/*}
    while [[ -n "$parent" && "$parent" != / ]]; do
        if [[ -f "$parent/pyvenv.cfg" ]]; then
            printf '%s\n' "$parent"
            return
        fi
        parent=${parent%/*}
    done
    case "$file" in
        */.cache/virtualenv/*) printf 'virtualenv seed cache\n';;
        /usr/lib/*|/usr/local/lib/*) printf 'system Python packages\n';;
        *) printf 'stored certificate/package files\n';;
    esac
}

audit_bundle() {
    local bundle=$1 subjects core environment
    environment=$(environment_for "$bundle")
    core="${bundle%/*}/core.py"
    if [[ ${bundle##*/} == cacert.pem && -r "$core" ]] &&
       grep -Eq "^DEBIAN_CA_CERTS_PATH = ['/\"]*/etc/ssl/certs/ca-certificates.crt['\"]" "$core" &&
       tail -n 16 "$core" | grep -Eq '^    return DEBIAN_CA_CERTS_PATH$'; then
        printf 'SYSTEM CA: %s\n  File: %s\n' "$environment" "$bundle"
        printf '  Ubuntu-patched certifi ignores this bundled PEM and uses the separately checked system CA store.\n'
        return 0
    fi
    if ! subjects=$(openssl crl2pkcs7 -nocrl -certfile "$bundle" |
                    openssl pkcs7 -print_certs -noout); then
        printf 'Unreadable or invalid certificate bundle\n  File: %s\n' "$bundle"
        printf '  Meaning: the certificate contents could not be checked.\n'
        printf '  Next step: repair the file or its read permissions, then rerun the audit.\n'
        return 2
    fi
    if [[ -z "$subjects" ]]; then
        printf 'Empty certificate bundle\n  File: %s\n' "$bundle"
        printf '  Meaning: OpenSSL decoded no certificates; absence of the removed root is unverified.\n'
        printf '  Next step: review or repair the bundle, then rerun the audit.\n'
        return 2
    fi
    if grep -Fq 'emSign ECC Root CA - G3' <<< "$subjects"; then
        case "$bundle" in
            */.cache/virtualenv/*)
                printf 'Old virtualenv seed bundle\n  Location: %s\n' "$bundle"
                printf '  Meaning: a cached seed contains the removed root and may copy it into future environments.\n'
                printf '  Next step: update the virtualenv tool, refresh its seed packages and retire the stale cached image.\n'
                ;;
            */pip/_vendor/certifi/cacert.pem)
                printf 'pip still bundles the removed CA root\n  Environment: %s\n  File: %s\n' "$environment" "$bundle"
                printf '  Meaning: pip using this bundle can trust certificates chained through the affected CA.\n'
                printf '  Next step: securely bootstrap pip >=26.2.2 in this environment using a verified wheel or a patched Python runtime.\n'
                ;;
            */certifi/cacert.pem)
                printf 'Application certifi still bundles the removed CA root\n  Environment: %s\n  File: %s\n' "$environment" "$bundle"
                printf '  Meaning: applications using this certifi bundle can still trust the affected CA, even when pip is patched.\n'
                printf '  Next step: upgrade certifi >=2026.10.19 here; update the project lock/constraints so provisioning does not restore it.\n'
                ;;
            *)
                printf 'Certificate bundle contains the removed CA root\n  File: %s\n' "$bundle"
                printf '  Meaning: clients configured to use this bundle may still trust the affected CA.\n'
                printf '  Next step: update the package supplying this bundle and review custom trust-store configuration.\n'
                ;;
        esac
        printf '  A stored bundle may be inactive; this is a review finding, not evidence of credential theft.\n'
        return 1
    fi
    printf 'ROOT ABSENT: %s\n  The removed emSign root was not found in this decoded bundle.\n' "$bundle"
}

print_section() {
    local title=$1 entry
    shift
    printf '\n%s\n' "$title"
    if (( $# == 0 )); then
        printf '  None.\n'
    else
        for entry do printf '%s\n' "$entry"; done
    fi
}

main() {
    local version file rc find_pid bundle_report package_version context result index
    local findings=0 unknown=0 venvs=0 bundles=0 os_name=unknown
    local -a roots=() findings_report=() unknown_report=() system_report=() env_report=() package_report=() passed_report=()
    if [[ -r /etc/os-release ]]; then
        . /etc/os-release
        os_name=${PRETTY_NAME:-unknown}
    fi
    version=$(dpkg-query -W -f='${Version}' ca-certificates 2>/dev/null) || version=missing
    system_report+=("OS: $os_name" "ca-certificates: $version")
    if [[ ${ID:-} == ubuntu && ${VERSION_ID:-} == 24.04 && $version != missing ]]; then
        if dpkg --compare-versions "$version" ge 20260816ubuntu0.24.04.1; then
            system_report+=("CA package: meets Ubuntu 24.04 USN-8944-1 minimum (20260816ubuntu0.24.04.1).")
        else
            findings_report+=($'Ubuntu system CA package needs updating\n  Installed: '"$version"$'\n  Meaning: the package predates Ubuntu 24.04\x27s certificate incident fix.\n  Next step: update ca-certificates to at least 20260816ubuntu0.24.04.1.')
            findings=$((findings + 1))
        fi
    else
        unknown_report+=("Unsupported OS or missing CA package: package-version validation is defined for Ubuntu 24.04 only. Review the matching vendor advisory.")
        unknown=$((unknown + 1))
    fi
    if [[ ! -r /etc/ssl/certs/ca-certificates.crt ]]; then
        unknown_report+=("System CA bundle is missing or unreadable: /etc/ssl/certs/ca-certificates.crt. Repair it before relying on system-CA overrides.")
        unknown=$((unknown + 1))
    fi
    for file in /etc/ssl/certs/ca-certificates.crt /opt /home /root /usr/local/lib /usr/lib; do
        [[ -e "$file" ]] && roots+=("$file")
    done
    while IFS= read -r -d '' file; do
        case "$file" in
            */pyvenv.cfg)
                env_report+=("${file%/pyvenv.cfg}")
                venvs=$((venvs + 1))
                ;;
            */METADATA)
                if package_version=$(awk '/^Version:/ {print $2; exit}' "$file") && [[ -n "$package_version" ]]; then
                    context=${file%/METADATA}
                    context=${context##*/}
                    context=${context%%-*}
                    package_report+=("$(environment_for "$file"): $context $package_version")
                else
                    unknown_report+=("Could not read a package version from $file. Review the package metadata.")
                    unknown=$((unknown + 1))
                fi
                ;;
            *)
                bundle_report=$(audit_bundle "$file")
                rc=$?
                bundles=$((bundles + 1))
                case "$rc" in
                    0) passed_report+=("$bundle_report");;
                    1) findings_report+=("$bundle_report"); findings=$((findings + 1));;
                    *) unknown_report+=("$bundle_report"); unknown=$((unknown + 1));;
                esac
                ;;
        esac
    done < <(find "${roots[@]}" -type f \( -name pyvenv.cfg -o -name cacert.pem -o -name ca-certificates.crt -o -path '*/pip-*.dist-info/METADATA' -o -path '*/certifi-*.dist-info/METADATA' \) -print0)
    find_pid=$!
    if ! wait "$find_pid"; then
        unknown_report+=("Filesystem discovery was incomplete. Review search errors/permissions and rerun; the unsearched paths are not verified.")
        unknown=$((unknown + 1))
    fi
    result=PASS
    (( findings == 0 )) || result=FAIL
    (( unknown == 0 )) || result=INCOMPLETE
    printf 'Python / CA audit: October 2026 eMudhra/emSign incident\n'
    printf 'RESULT: %s | %s findings | %s incomplete checks | %s venvs | %s bundles\n' "$result" "$findings" "$unknown" "$venvs" "$bundles"
    print_section 'SYSTEM' "${system_report[@]}"
    printf '\nACTION REQUIRED\n'
    if (( findings == 0 )); then
        printf '  None found in the scanned scope.\n'
    else
        index=0
        for bundle_report in "${findings_report[@]}"; do
            index=$((index + 1))
            printf '\n[%s] %s\n' "$index" "$bundle_report"
        done
    fi
    print_section 'INCOMPLETE CHECKS (these also prevent a pass)' "${unknown_report[@]}"
    print_section 'ENVIRONMENTS FOUND' "${env_report[@]}"
    print_section 'PACKAGE VERSIONS (inventory, not a vulnerability verdict)' "${package_report[@]}"
    print_section 'SUCCESSFUL BUNDLE CHECKS' "${passed_report[@]}"
    printf '\nHOW TO READ THIS REPORT\n'
    printf 'SYSTEM CA means the Ubuntu-patched package uses the system store; old pip 24.0 alone is not a finding.\n'
    printf 'ROOT ABSENT means only that the known removed root was absent from that decoded bundle.\n'
    printf 'FAIL means at least one item needs remediation/review. INCOMPLETE means some checks could not finish. Both stop the playbook.\n'
    printf 'This report does not establish whether credentials were stolen.\n'
    printf '\nSCOPE AND LIMITS\n'
    printf 'Checks the system CA package, named bundles and venv metadata under /opt, /home, /root, /usr/local/lib and /usr/lib.\n'
    printf 'PASS means no known incident findings in those scanned locations; it is not a claim that every certificate on the host is safe.\n'
    printf 'Not covered: containers, custom CA paths, virtualenv wheel archives, symlink-only trees or certificates already loaded by running processes.\n'
    (( unknown == 0 )) || return 2
    (( findings == 0 )) || return 1
}

if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
    main "$@"
fi
