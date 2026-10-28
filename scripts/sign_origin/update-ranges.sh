#!/bin/bash
set -euo pipefail
umask 077
source /etc/safeclaw-sign/ops.env
exec /usr/bin/flock -n /run/safeclaw-sign-origin.lock /usr/bin/python3 \
    /usr/local/sbin/update-sign-origin-ranges.py \
    --out /var/lib/safeclaw-sign/ranges --apply \
    --nsg-id-file /etc/safeclaw-sign/nsg-id \
    --oci "${SIGN_OCI_CLI:?required}" --oci-config "${SIGN_OCI_CONFIG:?required}"
