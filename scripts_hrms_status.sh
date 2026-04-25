#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/workspaces/frappe-hrms

docker compose -f docker/docker-compose.yml ps

echo '---'
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep -E 'NAMES|docker-(frappe|mariadb|redis)-1' || true

echo '---'
docker logs --tail 60 docker-frappe-1 || true
