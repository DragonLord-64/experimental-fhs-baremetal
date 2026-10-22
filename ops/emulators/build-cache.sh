#!/usr/bin/env bash
# Build only the bounded native-response cache; no cluster writes.
set -euo pipefail
cd "$(dirname "$0")"
[[ $(hostname) == dragon-lord-Virtual-Machine ]] || exit 1
mkdir -p .runtime/go-cache .runtime/go-mod
docker run --rm --memory=512m --cpus=1 --user "$(id -u):$(id -g)" \
 -e GOMAXPROCS=1 -e GOCACHE=/work/.runtime/go-cache -e GOMODCACHE=/work/.runtime/go-mod \
 -v "$PWD:/work" -w /work/cisco \
 golang:1.24.2-alpine3.21@sha256:7772cb5322baa875edd74705556d08f0eeca7b9c4b5367754ce3f2f00041ccee \
 sh -c 'go test -mod=readonly ./cache && CGO_ENABLED=0 go build -mod=readonly -trimpath -ldflags="-s -w" -o cache/cache-worker ./cache'
docker build -f cisco/cache/Runtime.Dockerfile -t fhs-lab/native-cache:1 cisco/cache
