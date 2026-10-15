#!/bin/sh
set -eu

compose_file="${COMPOSE_FILE:-compose.yaml}"
state_dir="${CQC_DEPLOY_STATE_DIR:-.cqc-deploy-state}"
if [ -f "$state_dir/pending" ]; then
    echo "[ERROR] Unresolved deployment; recover it before preserving new images." >&2
    exit 1
fi

# Build overwrites service tags. Keep the running images addressable before that
# happens, including with Docker's containerd image store.
container_ids="$(docker-compose -f "$compose_file" ps -q)"
for container_id in $container_ids; do
    project="$(docker inspect --format='{{index .Config.Labels "com.docker.compose.project"}}' "$container_id")"
    service="$(docker inspect --format='{{index .Config.Labels "com.docker.compose.service"}}' "$container_id")"
    image="$(docker inspect --format='{{.Image}}' "$container_id")"
    test -n "$project"
    test -n "$service"
    # One tag per project/service bounds retained images across deployments.
    docker image tag "$image" "cqc-rollback/$project/$service:previous"
done
