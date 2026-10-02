#!/bin/sh
set -eu

compose_file="${COMPOSE_FILE:-compose.yaml}"
health_services="${HEALTH_SERVICES:-mysql inference backend simulator logistics-mongodb logistics-api logistics-web}"
attempts="${HEALTH_ATTEMPTS:-24}"
interval="${HEALTH_INTERVAL_SECONDS:-5}"

if [ "${CQC_FORCE_HEALTH_FAILURE:-false}" = "1" ] || \
   [ "${CQC_FORCE_HEALTH_FAILURE:-false}" = "true" ]; then
    echo "[EXPECTED TEST FAILURE] CQC_FORCE_HEALTH_FAILURE enabled" >&2
    exit 1
fi

for service in $health_services; do
    container_id="$(docker-compose -f "$compose_file" ps -q "$service")"
    if [ -z "$container_id" ]; then
        echo "[ERROR] $service container not found" >&2
        exit 1
    fi

    healthy=false
    i=1
    while [ "$i" -le "$attempts" ]; do
        status="$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' "$container_id")"
        echo "[$i/$attempts] $service health status: $status"
        if [ "$status" = healthy ]; then
            healthy=true
            break
        fi
        if [ "$status" = unhealthy ]; then
            echo "[ERROR] $service became unhealthy" >&2
            exit 1
        fi
        sleep "$interval"
        i=$((i + 1))
    done

    if [ "$healthy" != true ]; then
        echo "[ERROR] $service did not become healthy" >&2
        exit 1
    fi
done
