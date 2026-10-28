#!/bin/bash
# Encrypt one COMPLETE bench backup and its recovery keys in separate age archives.
# Does not run backup, delete originals, upload, change cron, or send messages.
# SITE_NAME and AGE_RECIPIENTS are required. Recovery identities stay OFF server.
set -Eeuo pipefail
trap 'echo "[ERROR] encryption stopped at line $LINENO; upload not performed" >&2' ERR
umask 077
SITE_NAME="${SITE_NAME:?SITE_NAME required}"
AGE_RECIPIENTS="${AGE_RECIPIENTS:?AGE_RECIPIENTS required}"
SEAL_KEY_SUBDIR="${SEAL_KEY_SUBDIR:?SEAL_KEY_SUBDIR required (relative to bench)}"
BENCH_CONTAINER="${BENCH_CONTAINER:-docker-frappe-1}"
BENCH_PATH="${BENCH_PATH:-/home/frappe/frappe-bench}"
OUT_DIR="${OUT_DIR:-/home/ubuntu/backups/hrms-offsite}"
[[ "$SITE_NAME" =~ ^[a-zA-Z0-9][a-zA-Z0-9.-]+$ ]] || { echo '[ERROR] invalid site' >&2; exit 2; }
[[ "$SEAL_KEY_SUBDIR" =~ ^esign-keys/[a-zA-Z0-9_-]+$ ]] || { echo '[ERROR] invalid seal key subdirectory' >&2; exit 2; }
command -v age >/dev/null
command -v docker >/dev/null
[[ -f "$AGE_RECIPIENTS" ]] || { echo '[ERROR] missing recipients' >&2; exit 2; }
if grep -q 'AGE-SECRET-KEY' "$AGE_RECIPIENTS"; then
    echo '[ERROR] recovery identity must not be on backup server' >&2; exit 2
fi
grep -Eq '^age1[0-9a-z]+$' "$AGE_RECIPIENTS" || { echo '[ERROR] missing age recipient' >&2; exit 2; }
BACKUPS="$BENCH_PATH/sites/$SITE_NAME/private/backups"
# Bench filenames start with YYYYMMDD_HHMMSS; lexical sorting picks the latest snapshot.
DATABASE=$(docker exec "$BENCH_CONTAINER" find "$BACKUPS" -maxdepth 1 -type f -name '*-database.sql.gz' -printf '%f\n' | LC_ALL=C sort | tail -1)
[[ -n "$DATABASE" ]] || { echo '[ERROR] no database backup' >&2; exit 2; }
[[ "$DATABASE" =~ ^[a-zA-Z0-9_.-]+-database\.sql\.gz$ ]] || { echo '[ERROR] unsafe backup name' >&2; exit 2; }
PREFIX="${DATABASE%-database.sql.gz}"
for file in "$DATABASE" "$PREFIX-files.tgz" "$PREFIX-private-files.tgz" "$PREFIX-site_config_backup.json"; do
    docker exec "$BENCH_CONTAINER" test -s "$BACKUPS/$file" || { echo '[ERROR] incomplete backup set' >&2; exit 2; }
done
# Do not silently omit the seal private key or certificate.
docker exec "$BENCH_CONTAINER" test -s "$BENCH_PATH/$SEAL_KEY_SUBDIR/seal.key"
docker exec "$BENCH_CONTAINER" test -s "$BENCH_PATH/$SEAL_KEY_SUBDIR/seal.crt"
mkdir -p "$OUT_DIR"
chmod 700 "$OUT_DIR"
DATA="$OUT_DIR/$PREFIX-data.tar.age"
KEYS="$OUT_DIR/$PREFIX-keys.tar.age"
[[ ! -e "$DATA" && ! -e "$KEYS" ]] || { echo '[ERROR] destination exists; will not overwrite' >&2; exit 2; }
STAGE=$(mktemp -d "$OUT_DIR/.encrypt.XXXXXXXX")
trap 'rm -rf -- "$STAGE"' EXIT
docker exec "$BENCH_CONTAINER" tar -C "$BACKUPS" -cf - "$DATABASE" "$PREFIX-files.tgz" "$PREFIX-private-files.tgz" \
    | age -R "$AGE_RECIPIENTS" -o "$STAGE/data.age"
# Keys include snapshot config (DB password, encryption/HMAC keys) plus seal material.
# Never place a plaintext key bundle on the host disk or in the data archive.
docker exec "$BENCH_CONTAINER" tar -C "$BENCH_PATH" -cf - "$SEAL_KEY_SUBDIR" "sites/$SITE_NAME/private/backups/$PREFIX-site_config_backup.json" \
    | age -R "$AGE_RECIPIENTS" -o "$STAGE/keys.age"
mv -- "$STAGE/data.age" "$DATA"
mv -- "$STAGE/keys.age" "$KEYS"
(cd "$OUT_DIR" && sha256sum "$(basename "$DATA")" "$(basename "$KEYS")" > "$PREFIX.sha256")
echo '[OK] encrypted data + key archives created; originals retained; upload not performed'
