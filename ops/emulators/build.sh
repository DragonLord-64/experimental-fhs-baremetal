#!/usr/bin/env bash
# Serial VM build, bounded compiler; does not deploy pods.
set -euo pipefail
cd "$(dirname "$0")"
[[ $(hostname) == dragon-lord-Virtual-Machine ]] || { echo 'Run on dragonvm only.' >&2; exit 1; }
python3 fixture.py --write
mkdir -p .runtime/go-cache .runtime/go-mod
# Run as the workspace owner; build artifacts never become root-owned.
docker run --rm --memory=512m --cpus=1 --user "$(id -u):$(id -g)" \
  -e GOMAXPROCS=1 -e GOCACHE=/work/.runtime/go-cache -e GOMODCACHE=/work/.runtime/go-mod \
  -v "$PWD:/work" -w /work/cisco \
  golang:1.24.2-alpine3.21@sha256:7772cb5322baa875edd74705556d08f0eeca7b9c4b5367754ce3f2f00041ccee \
  sh -c 'go test -mod=readonly ./... && CGO_ENABLED=0 go build -mod=readonly -trimpath -ldflags="-s -w" -o sender .'
docker build -f cisco/Runtime.Dockerfile -t fhs-lab/cisco-emulator:1 cisco

./build-cache.sh
