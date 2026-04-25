#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/workspaces/frappe-hrms
exec docker compose -f docker/docker-compose.yml down
