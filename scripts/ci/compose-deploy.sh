#!/bin/sh
set -eu
umask 077

compose_file="${COMPOSE_FILE:-compose.yaml}"
state_dir="${CQC_DEPLOY_STATE_DIR:-.cqc-deploy-state}"
mkdir -p "$state_dir"
chmod 700 "$state_dir"

if [ -f "$state_dir/pending" ]; then
    echo "[ERROR] Unresolved deployment; recover it before deploying again." >&2
    exit 1
fi

# Read the previous deployment from Docker, not the incoming compose.yaml.
# Never echo inspect/config output: it includes runtime credentials.
container_ids="$(docker-compose -f "$compose_file" ps -q)"
if [ -n "$container_ids" ]; then
    first_id=$(printf '%s\n' "$container_ids" | head -n 1)
    project="$(docker inspect --format='{{index .Config.Labels "com.docker.compose.project"}}' "$first_id")"
    test -n "$project"
    container_ids="$(docker ps -aq --filter "label=com.docker.compose.project=$project")"
    test -n "$container_ids"
    printf '%s\n' "$project" > "$state_dir/project"
    # Send code from the client; the host daemon cannot mount Jenkins's workspace.
    snapshot_script="$(cat scripts/ci/snapshot-compose.py)"
    # Intentional splitting: Docker IDs cannot contain spaces.
    docker inspect $container_ids > "$state_dir/inspect.json"
    if ! docker run --rm -i python:3.11-slim \
        python -c "$snapshot_script" \
        < "$state_dir/inspect.json" > "$state_dir/rollback.json.tmp"; then
        rm -f "$state_dir/inspect.json" "$state_dir/rollback.json.tmp"
        exit 1
    fi
    rm -f "$state_dir/inspect.json"
    mv "$state_dir/rollback.json.tmp" "$state_dir/rollback.json"
else
    # Fresh deployment: no previous containers can be restored.
    rm -f "$state_dir/project" "$state_dir/rollback.json"
fi

# Marker precedes the first mutation; Jenkins unsuccessful handles cancellation.
touch "$state_dir/pending"
docker-compose -f "$compose_file" up -d --no-build --remove-orphans
