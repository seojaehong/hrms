#!/bin/bash

set -eo pipefail

: "${HRMS_APP_SOURCE:=/workspace/hrms-source}"

if [ ! -f "$HRMS_APP_SOURCE/pyproject.toml" ] || [ ! -d "$HRMS_APP_SOURCE/hrms" ]; then
    echo "HRMS_APP_SOURCE does not point to a mounted HRMS workspace: $HRMS_APP_SOURCE" >&2
    exit 1
fi

git config --global --add safe.directory "$HRMS_APP_SOURCE/.git"

sync_hrms_app_from_mounted_source() {
    if [ ! -d "apps/hrms/.git" ]; then
        echo "Installed HRMS app checkout is missing or not a git repository" >&2
        exit 1
    fi

    git -C apps/hrms fetch --force "$HRMS_APP_SOURCE"
    git -C apps/hrms reset --hard FETCH_HEAD
    git -C apps/hrms clean -fd
}

if [ -d "/home/frappe/frappe-bench/apps/frappe" ]; then
    echo "Bench already exists, syncing HRMS app from mounted source"
    cd frappe-bench
    sync_hrms_app_from_mounted_source
    bench start
else
    echo "Creating new bench..."
fi

export PATH="${NVM_DIR}/versions/node/v${NODE_VERSION_DEVELOP}/bin/:${PATH}"

bench init --skip-redis-config-generation frappe-bench

cd frappe-bench

# Use containers instead of localhost
bench set-mariadb-host mariadb
bench set-redis-cache-host redis://redis:6379
bench set-redis-queue-host redis://redis:6379
bench set-redis-socketio-host redis://redis:6379

# Remove redis, watch from Procfile
sed -i '/redis/d' ./Procfile
sed -i '/watch/d' ./Procfile

bench get-app erpnext
bench get-app "$HRMS_APP_SOURCE"

bench new-site hrms.localhost \
--force \
--mariadb-root-password 123 \
--admin-password admin \
--no-mariadb-socket

bench --site hrms.localhost install-app hrms
bench --site hrms.localhost set-config developer_mode 1
bench --site hrms.localhost enable-scheduler
bench --site hrms.localhost clear-cache
bench use hrms.localhost

bench start