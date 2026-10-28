# Encrypted offsite backup preparation

This procedure backs up existing DB/file snapshots. It never sends signing messages,
changes contract state, updates signing URLs, or changes network rules.

Use `scripts/esign_backup/encrypt_site_backup.sh` after a successful single-site
`bench backup --with-files --compress`. It requires the matching database, public
files, private files, and site-config snapshot. An incomplete latest set fails
instead of uploading an older snapshot silently.

```sh
SITE_NAME=tenant.example.test \
SEAL_KEY_SUBDIR=esign-keys/tenant \
AGE_RECIPIENTS=/etc/hrms-backup/recipients.txt \
OUT_DIR=/var/lib/hrms-backup/encrypted \
bash scripts/esign_backup/encrypt_site_backup.sh
```

The seal subdirectory is relative to the bench directory. Both `seal.key` and
`seal.crt` must exist. Keep any seal passphrase file needed for recovery in that
same protected key directory, or arrange a separate encrypted backup for it.
Do not assume a successful file archive alone proves a working signature key.

The script streams two separate tar archives through age public-key encryption:

- `*-data.tar.age`: compressed DB dump and public/private file snapshots.
- `*-keys.tar.age`: the matching site configuration and the selected seal directory.
- `*.sha256`: ciphertext checksums with relative filenames.

Existing backups remain untouched. The script does not enable a timer, upload,
delete originals, alter retention, or print key contents. It refuses to overwrite
an existing encrypted snapshot. Recovery identities must stay off the server and
outside the S3 bucket, with a separately secured offline copy.

## S3 permissions and retention

Use a private versioned bucket with all four public-access blocks and SSE-S3 or
stronger default encryption. Additionally encrypt before upload; SSE alone does
not separate the recovery key from the cloud account.

The backup identity needs only `s3:PutObject`, `s3:GetObject`, and `s3:ListBucket`.
Object resources must be explicit backup-folder ARNs, never a global `*`.
`ListBucket` uses the bucket ARN and an `s3:prefix` condition for those folders.
No ACL, bucket-policy, delete, administrator, or signing-edge permissions belong
in this identity. Use explicit AES256 on uploads when the policy requires it.

Let bucket lifecycle manage retention; do not give the uploader delete rights.
Document current-version and noncurrent-version expiry separately. Do not enable
automatic backup completion reporting until the first round-trip restore works.

## First restore acceptance

1. Upload with the restricted backup identity, then download the exact same object.
2. Compare ciphertext SHA256 with the local archive and decrypt on the recovery PC.
3. Check the DB gzip, public/private tar archives, matching config, and seal key/cert.
4. Import into a disposable database with no production connection and no workers,
   scheduler, SMS sender, email sender, or public listener. Compare table counts and
   verify recovered files and key/cert pairing. Never restore into the live tenant.
5. Attempt deletion of that test object with the same backup identity. Require
   `AccessDenied`, then confirm the object is still readable. An allowed delete is
   a failed permission check, not a successful backup verification.
6. Record object key/version, checksums, restore and denial evidence, and gaps.
   Only then wire an encrypted uploader into the daily backup schedule.
