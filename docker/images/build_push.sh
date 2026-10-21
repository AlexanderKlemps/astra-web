#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: build_push.sh [TAG] [DOCKERHUB_REPOSITORY]

Build the ASTRA base image for linux/amd64, tag it, and push it to Docker Hub.
Defaults: TAG=astra-py314-2026-10-09, DOCKERHUB_REPOSITORY=alexanderklemps/astra-web

Authenticate first with: docker login --username YOUR_DOCKERHUB_USERNAME
Uses the selected Docker context (or the DOCKER_CONTEXT environment variable).
The image contains ASTRA; DESY's redistribution terms apply.
EOF
}

if [[ "${1:-}" == --help || "${1:-}" == -h ]]; then
    usage
    exit 0
fi
if (( $# > 2 )); then
    usage >&2
    exit 2
fi

tag="${1:-astra-py314-2026-10-09}"
repository="${2:-alexanderklemps/astra-web}"
if [[ ! "$tag" =~ ^[a-zA-Z0-9_][a-zA-Z0-9_.-]{0,127}$ ]]; then
    printf 'Invalid image tag: %s\n' "$tag" >&2
    exit 2
fi
if [[ ! "$repository" =~ ^[a-z0-9][a-z0-9._-]*/[a-z0-9][a-z0-9._-]*$ ]]; then
    printf 'Expected a Docker Hub repository in username/repository format: %s\n' "$repository" >&2
    exit 2
fi
command -v docker >/dev/null 2>&1 || { printf 'Docker CLI is required.\n' >&2; exit 1; }

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
local_image="astra-web-base:${tag}"
remote_image="docker.io/${repository}:${tag}"

printf 'Building %s for linux/amd64\n' "$local_image"
docker build --pull --platform linux/amd64 \
    --file "${script_dir}/astra-web.Dockerfile" \
    --tag "$local_image" \
    "$script_dir"

printf 'Tagging %s\n' "$remote_image"
docker tag "$local_image" "$remote_image"

printf 'Pushing %s\n' "$remote_image"
docker push "$remote_image"
printf 'Published %s\n' "$remote_image"
