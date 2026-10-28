#!/bin/bash
set -euo pipefail
umask 077
source /etc/safeclaw-sign/origin.env
if [[ "$(basename "${RENEWED_LINEAGE:?Certbot lineage required}")" != "${ORIGIN_CERT_NAME:?required}" ]]; then
    echo '[INFO] Other certificate renewal: signing origin unchanged'
    exit 0
fi
for item in fullchain.pem privkey.pem; do
    install -o root -g 101 -m 640 "$(readlink -f "$RENEWED_LINEAGE/$item")" "/etc/safeclaw-sign/runtime/$item"
done
docker run --rm --network none --user 101:101 --cap-drop ALL --read-only \
    --tmpfs /tmp:uid=101,gid=101,mode=0700 \
    -v /etc/safeclaw-sign/nginx.conf:/etc/nginx/nginx.conf:ro \
    -v /etc/safeclaw-sign/runtime:/run/origin:ro \
    --entrypoint nginx "$ORIGIN_IMAGE" -t
if systemctl is-active --quiet safeclaw-sign-origin.service; then
    docker exec safeclaw-sign-origin nginx -s reload
else
    systemctl start safeclaw-sign-origin.service
fi
echo '[OK] Signing origin certificate deployed'
