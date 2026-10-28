"""Offline failure-path tests; no AWS calls or notifications."""
from __future__ import annotations
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import daily_offsite as job


class DailyBackupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.prefix = "20261028_020000-example_org"
        self.config = {"credentials_file": str(self.root / "aws.json"), "expected_identity": "arn:test:backup", "bench_path": "/bench", "site_name": "example.org", "container": "test", "out_dir": str(self.root), "state_dir": str(self.root), "state_file": str(self.root / "success.json"), "bucket": "test-bucket"}
        (self.root / "aws.json").write_text('{}')
        self.data = self.root / f"{self.prefix}-data.tar.age"
        self.keys = self.root / f"{self.prefix}-keys.tar.age"
        self.data.write_bytes(b"synthetic encrypted data")
        self.keys.write_bytes(b"synthetic encrypted keys")
        (self.root / f"{self.prefix}.sha256").write_text("".join(f"{job.checksum(p)}  {p.name}\n" for p in [self.data, self.keys]))
        self.actions: list[list[str]] = []

    def tearDown(self) -> None:
        self.temp.cleanup()

    def fake(self, command: list[str], env: dict[str, str] | None = None, timeout: int = 7200) -> str:
        self.actions.append(command)
        if command[:2] == ["aws", "sts"]:
            return json.dumps({"Arn": self.config["expected_identity"]})
        if "find" in command:
            return f"{self.prefix}-database.sql.gz\n"
        if "stat" in command:
            return str(time.time())
        if command[:3] == ["aws", "s3api", "put-object"]:
            self.assertIn("AES256", command)
            return json.dumps({"VersionId": "test-version"})
        if command[:3] == ["aws", "s3api", "get-object"]:
            destination = Path(command[-3])
            destination.write_bytes((self.root / destination.name).read_bytes())
            return json.dumps({"ServerSideEncryption": "AES256"})
        raise AssertionError(f"Unexpected command: {command[0]}")

    def test_roundtrip_and_separate_key_prefix(self) -> None:
        with patch.object(job, "run", side_effect=self.fake):
            report = job.upload(self.config, time.time(), True)
        self.assertEqual(len(report["objects"]), 3)
        self.assertEqual(report["status"], "verified")
        uploaded = [row[row.index("--key") + 1] for row in self.actions if "put-object" in row]
        self.assertEqual(sum(key.startswith("keys/") for key in uploaded), 1)
        self.assertEqual(sum(key.startswith("daily/") for key in uploaded), 2)
        self.assertFalse(any("delete-object" in row for row in self.actions))
        self.assertTrue(Path(self.config["state_file"]).exists())

    def test_mismatched_identity_stops_before_docker(self) -> None:
        with patch.object(job, "run", return_value='{"Arn":"arn:test:wrong"}') as call:
            with self.assertRaisesRegex(RuntimeError, "identity mismatch"):
                job.upload(self.config, time.time(), True)
        self.assertEqual(call.call_count, 1)

    def test_stale_snapshot_never_uploads(self) -> None:
        def stale(command: list[str], env: dict[str, str] | None = None, timeout: int = 7200) -> str:
            return str(time.time() - 86400) if "stat" in command else self.fake(command, env, timeout)
        with patch.object(job, "run", side_effect=stale):
            with self.assertRaisesRegex(RuntimeError, "stale"):
                job.upload(self.config, time.time(), True)
        self.assertFalse(any("put-object" in row for row in self.actions))

    def test_tampered_archive_never_uploads(self) -> None:
        self.keys.write_bytes(b"tampered")
        with patch.object(job, "run", side_effect=self.fake):
            with self.assertRaisesRegex(RuntimeError, "checksum mismatch"):
                job.upload(self.config, time.time(), True)
        self.assertFalse(any("put-object" in row for row in self.actions))

    def test_download_failure_never_marks_success(self) -> None:
        def failing(command: list[str], env: dict[str, str] | None = None, timeout: int = 7200) -> str:
            if "get-object" in command:
                raise RuntimeError("synthetic network failure")
            return self.fake(command, env, timeout)
        with patch.object(job, "run", side_effect=failing):
            with self.assertRaisesRegex(RuntimeError, "network failure"):
                job.upload(self.config, time.time(), True)
        self.assertFalse(Path(self.config["state_file"]).exists())


if __name__ == "__main__":
    unittest.main()
