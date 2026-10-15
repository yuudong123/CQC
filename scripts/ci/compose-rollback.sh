#!/bin/sh
set -eu

state_dir="${CQC_DEPLOY_STATE_DIR:-.cqc-deploy-state}"

if [ ! -f "$state_dir/pending" ]; then
    echo "No pending deployment; previous containers were not changed."
    exit 0
fi
if [ ! -s "$state_dir/rollback.json" ] || [ ! -s "$state_dir/project" ]; then
    echo "[ERROR] First deployment failed; there is no previous deployment to restore." >&2
    exit 1
fi

export COMPOSE_PROJECT_NAME="$(cat "$state_dir/project")"
export COMPOSE_FILE="$state_dir/rollback.json"
# Pinned local images preserved before Build, with the old runtime configuration.
docker-compose -f "$COMPOSE_FILE" up -d --no-build --remove-orphans
export HEALTH_SERVICES="$(docker-compose -f "$COMPOSE_FILE" config --services)"
CQC_FORCE_HEALTH_FAILURE=0 sh scripts/ci/verify-compose-health.sh
# Keep the protected snapshot and pending marker if recovery fails.
rm -f "$state_dir/pending" "$state_dir/rollback.json" "$state_dir/project"
echo "Previous deployment restored and healthy."
