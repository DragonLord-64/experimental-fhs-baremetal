#!/usr/bin/env bash
# Shared dragonvm / future CI entry point. Requires the isolated test toolchain.
set -euo pipefail
# Review note: give each run separate ownership, reports and Ansible state to avoid collisions.
repo=$(cd "$(dirname "$0")/../../.." && pwd)
export FHS_MOLECULE_NAME="fhs-users-$(date +%s)-$(python3 -c 'import secrets; print(secrets.token_hex(4))')"
export FHS_MOLECULE_IMAGE='ubuntu@sha256:68ee22004a9109b44973313b02ff7b1de250f1de0f5ecb628d73f579aaff33ac'
report="$repo/build/reports/molecule/$FHS_MOLECULE_NAME"
mkdir -p "$report"
export ANSIBLE_LOCAL_TEMP="$report/ansible-tmp"
export ANSIBLE_HOME="$report/ansible-home"
export XDG_CACHE_HOME="$report/cache"
export ANSIBLE_COLLECTIONS_PATH="${FHS_TEST_COLLECTIONS:-$repo/build/molecule-collections}"
export MOLECULE_EPHEMERAL_DIRECTORY="$report/ephemeral"
export ANSIBLE_NOCOLOR=1
export ANSIBLE_FORKS=2
# Review note: cleanup checks ownership and records leftovers, preserving any unrelated container.
cleanup() {
    status=$?
    trap - EXIT INT TERM
    set +e
    owner=$(docker inspect --format '{{ index .Config.Labels "org.fhs.molecule.run" }}' "$FHS_MOLECULE_NAME" 2>/dev/null)
    if [[ "$owner" == "$FHS_MOLECULE_NAME" ]]; then
        docker inspect --format 'name={{.Name}} privileged={{.HostConfig.Privileged}} mounts={{json .Mounts}} memory={{.HostConfig.Memory}} cpus={{.HostConfig.NanoCpus}} pids={{.HostConfig.PidsLimit}}' "$FHS_MOLECULE_NAME" >> "$report/cleanup.log"
        docker rm -f "$FHS_MOLECULE_NAME" >> "$report/cleanup.log" 2>&1 || status=1
    elif [[ -n "$owner" ]]; then
        echo 'Refusing cleanup: ownership mismatch' >> "$report/cleanup.log"
        status=1
    fi
    docker ps -aq --filter "label=org.fhs.molecule.run=$FHS_MOLECULE_NAME" > "$report/remaining-containers.txt" || status=1
    [[ ! -s "$report/remaining-containers.txt" ]] || status=1
    printf 'exit=%s\n' "$status" >> "$report/cleanup.log"
    exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
# Review note: pull the pinned image before inspection so an uncached runner can start safely.
{
    git -C "$repo" rev-parse HEAD
    molecule --version
    ansible --version
    docker version --format 'client={{.Client.Version}} server={{.Server.Version}}'
    timeout --signal=TERM --kill-after=10s 180s docker pull "$FHS_MOLECULE_IMAGE"
    docker image inspect "$FHS_MOLECULE_IMAGE" --format '{{json .RepoDigests}}'
} > "$report/versions.txt"
export FHS_SDK_FIXTURE_DEB="$report/sdk-fixture.deb"
python3 "$repo/ops/role-tests/cleanup/make_sdk_fixture.py" "$FHS_SDK_FIXTURE_DEB"
cd "$repo/ops/role-tests/manage_users"
printf 'Evidence: %s\n' "$report"
# Review note: bound the full lifecycle while pipefail preserves a failing Molecule exit status.
timeout --signal=TERM --kill-after=30s 900s molecule test -s default 2>&1 | tee "$report/test.log"
