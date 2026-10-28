#!/usr/bin/env python3
"""Run the existing local backup, then encrypt and verify its S3 offsite copy."""
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str], env: dict[str, str] | None = None, timeout: int = 7200) -> str:
    result = subprocess.run(command, env=env, text=True, capture_output=True, timeout=timeout)
    if result.returncode:
        # Commands may handle credentials or private filenames: never echo raw stderr.
        raise RuntimeError(f"{Path(command[0]).name} failed (exit {result.returncode}); output withheld")
    return result.stdout


def notify(config: dict[str, str], test: bool) -> None:
    text = ("[TEST] SafeClaw encrypted S3 backup failure-alert test. No production failure occurred."
            if test else "[ALERT] SafeClaw daily backup/offsite verification failed. Check the protected server backup log; the run was not marked successful.")
    output = run(["sudo", "-Hu", config["local_user"], config["notifier"], "message", "send", "--channel", "telegram", "--account", "default", "--target", config["alert_target"], "--message", text, "--json"], timeout=60)
    decoder = json.JSONDecoder()
    receipt: dict[str, object] | None = None
    for index, char in enumerate(output):
        if char != "{":
            continue
        try:
            candidate, _ = decoder.raw_decode(output[index:])
        except ValueError:
            continue
        if isinstance(candidate, dict) and isinstance(candidate.get("payload"), dict):
            payload = candidate["payload"]
            if payload.get("ok") is True and payload.get("messageId"):
                receipt = {"status": "accepted_by_telegram", "message_id": str(payload["messageId"]), "test": test,
                           "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat()}
                break
    if receipt is None:
        raise RuntimeError("Notifier returned no successful Telegram receipt; output withheld")
    Path(config["state_dir"], "last-alert.json").write_text(json.dumps(receipt, indent=2) + "\n")


def upload(config: dict[str, str], started: float, upload_only: bool) -> dict[str, object]:
    env = os.environ.copy()
    credentials = json.loads(Path(config["credentials_file"]).read_text())
    env.update(credentials)
    env.update({"AWS_EC2_METADATA_DISABLED": "true", "AWS_PAGER": "", "AWS_MAX_ATTEMPTS": "2"})
    identity = json.loads(run(["aws", "sts", "get-caller-identity", "--output", "json"], env))
    if identity["Arn"] != config["expected_identity"]:
        raise RuntimeError("Backup IAM identity mismatch")
    backup_dir = f'{config["bench_path"]}/sites/{config["site_name"]}/private/backups'
    container = config["container"]
    candidates = run(["docker", "exec", container, "find", backup_dir, "-maxdepth", "1", "-type", "f", "-name", "*-database.sql.gz", "-printf", "%f\\n"]).splitlines()
    if not candidates:
        raise RuntimeError("No database backup exists")
    database = sorted(candidates)[-1]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+-database\.sql\.gz", database):
        raise RuntimeError("Unsafe snapshot name")
    prefix = database.removesuffix("-database.sql.gz")
    modified = float(run(["docker", "exec", container, "stat", "-c", "%Y", f"{backup_dir}/{database}"]).strip())
    cutoff = started - (21600 if upload_only else 120)
    if modified < cutoff or modified > time.time() + 120:
        raise RuntimeError("Snapshot is stale or has an invalid clock; no upload")
    out_dir = Path(config["out_dir"])
    archives = [out_dir / f"{prefix}-data.tar.age", out_dir / f"{prefix}-keys.tar.age"]
    manifest = out_dir / f"{prefix}.sha256"
    if not any(path.exists() for path in [*archives, manifest]):
        encryption_env = env | {"SITE_NAME": config["site_name"], "BENCH_CONTAINER": container,
                                "BENCH_PATH": config["bench_path"], "SEAL_KEY_SUBDIR": config["seal_key_subdir"],
                                "AGE_RECIPIENTS": config["recipients_file"], "OUT_DIR": str(out_dir)}
        run(["/bin/bash", config["encrypt_script"]], encryption_env)
    if not all(path.is_file() and path.stat().st_size for path in [*archives, manifest]):
        raise RuntimeError("Incomplete encrypted backup set")
    for line in manifest.read_text().splitlines():
        digest, filename = line.split(maxsplit=1)
        path = out_dir / filename.strip()
        if path not in archives or checksum(path) != digest:
            raise RuntimeError("Encrypted manifest checksum mismatch")
    if len(manifest.read_text().splitlines()) != 2:
        raise RuntimeError("Expected two archive checksums")
    state_path = Path(config["state_file"])
    previous = json.loads(state_path.read_text()) if state_path.exists() else {}
    if previous.get("snapshot") == prefix and previous.get("status") == "verified":
        return previous | {"already_verified": True}
    day = dt.datetime.fromtimestamp(modified, dt.timezone.utc).strftime("%Y%m%d")
    objects: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="s3-cipher-check-", dir=config["state_dir"]) as scratch:
        for source in [*archives, manifest]:
            folder = "keys" if source == archives[1] else "daily"
            key = f"{folder}/{day}/{source.name}"
            digest = checksum(source)
            result = json.loads(run(["aws", "s3api", "put-object", "--bucket", config["bucket"], "--key", key,
                                     "--body", str(source), "--server-side-encryption", "AES256", "--metadata", f"sha256={digest}", "--output", "json"], env))
            destination = Path(scratch) / source.name
            fetched = json.loads(run(["aws", "s3api", "get-object", "--bucket", config["bucket"], "--key", key, str(destination), "--output", "json"], env))
            matches = checksum(destination) == digest
            if not matches or fetched.get("ServerSideEncryption") != "AES256" or not result.get("VersionId"):
                raise RuntimeError("S3 checksum/encryption/version verification failed")
            objects.append({"key": key, "bytes": source.stat().st_size, "sha256": digest, "version_id": result["VersionId"], "download_matches": True})
    report: dict[str, object] = {"status": "verified", "snapshot": prefix, "objects": objects,
                                 "completed_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "plaintext_uploaded": False}
    temporary = state_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n")
    temporary.replace(state_path)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--upload-only", action="store_true", help="Verify a recent existing snapshot without running local cleanup")
    parser.add_argument("--test-failure", action="store_true", help="Exercise failure notification without running backup or uploading")
    args = parser.parse_args()
    os.umask(0o077)
    config = json.loads(args.config.read_text())
    Path(config["state_dir"]).mkdir(parents=True, exist_ok=True, mode=0o700)
    with Path(config["lock_file"]).open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another daily backup is running") from None
        started = time.time()
        try:
            if args.test_failure:
                raise RuntimeError("Injected notification test")
            if not args.upload_only:
                # Keep the original script/user/retention behavior; never use its plaintext --upload option.
                run(["sudo", "-Hu", config["local_user"], "/bin/bash", config["local_backup_script"]])
            report = upload(config, started, args.upload_only)
            print(json.dumps({"status": report["status"], "objects": len(report["objects"]), "already_verified": report.get("already_verified", False)}), flush=True)
        except Exception as exc:
            print(f"[ERROR] {type(exc).__name__}: {exc}", flush=True)
            try:
                notify(config, args.test_failure)
                print("[ALERT] notification delivered", flush=True)
            except Exception as alert_exc:
                print(f"[ALERT-ERROR] {alert_exc}", flush=True)
                raise
            if not args.test_failure:
                raise


if __name__ == "__main__":
    main()
