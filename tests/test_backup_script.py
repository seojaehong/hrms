"""
test_backup_script.py — 백업 스크립트 구조 검증 테스트

실제 백업/복구를 실행하지 않고 스크립트의 구조적 요구사항을 확인합니다.

참고: hrms/tests/ 는 Frappe 런타임이 필요하므로 순수 unittest는
      tests/ (top-level) 에 위치합니다. 기존 tests/test_korea_integration.py
      와 동일한 패턴입니다.

실행:
    python3 -m pytest tests/test_backup_script.py -v
    # 또는
    python3 -m unittest tests.test_backup_script -v
"""

import pathlib
import re
import unittest

# ── 스크립트 경로 ──────────────────────────────────────
REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
BACKUP_SCRIPT = REPO_ROOT / "scripts" / "backup_korea_hrms.sh"
RESTORE_SCRIPT = REPO_ROOT / "scripts" / "restore_korea_hrms.sh"
DRILL_SCRIPT = REPO_ROOT / "scripts" / "backup_drill.sh"
SYSTEMD_SERVICE = REPO_ROOT / "scripts" / "systemd" / "hrms-backup.service"
SYSTEMD_TIMER = REPO_ROOT / "scripts" / "systemd" / "hrms-backup.timer"


def _read(path: pathlib.Path) -> str:
    """스크립트 내용을 문자열로 반환."""
    return path.read_text(encoding="utf-8")


class TestScriptFilesExist(unittest.TestCase):
    """모든 스크립트 파일이 존재하는지 확인."""

    def test_backup_script_exists(self):
        self.assertTrue(BACKUP_SCRIPT.exists(), f"파일 없음: {BACKUP_SCRIPT}")

    def test_restore_script_exists(self):
        self.assertTrue(RESTORE_SCRIPT.exists(), f"파일 없음: {RESTORE_SCRIPT}")

    def test_drill_script_exists(self):
        self.assertTrue(DRILL_SCRIPT.exists(), f"파일 없음: {DRILL_SCRIPT}")

    def test_systemd_service_exists(self):
        self.assertTrue(SYSTEMD_SERVICE.exists(), f"파일 없음: {SYSTEMD_SERVICE}")

    def test_systemd_timer_exists(self):
        self.assertTrue(SYSTEMD_TIMER.exists(), f"파일 없음: {SYSTEMD_TIMER}")


class TestBackupScriptStructure(unittest.TestCase):
    """backup_korea_hrms.sh 구조 요구사항."""

    def setUp(self):
        self.content = _read(BACKUP_SCRIPT)

    def test_has_bash_shebang(self):
        self.assertTrue(
            self.content.startswith("#!/bin/bash"),
            "스크립트가 #!/bin/bash 로 시작해야 합니다.",
        )

    def test_has_set_euo_pipefail(self):
        self.assertIn(
            "set -euo pipefail",
            self.content,
            "set -euo pipefail 이 누락되었습니다.",
        )

    def test_has_lc_all(self):
        self.assertIn(
            "LC_ALL=C",
            self.content,
            "LC_ALL=C 설정이 누락되었습니다 (정렬 일관성 보장).",
        )

    def test_uses_bench_backup(self):
        self.assertIn(
            "bench backup",
            self.content,
            "bench backup 명령을 사용해야 합니다 (raw mysqldump 금지).",
        )

    def test_uses_with_files_flag(self):
        self.assertIn(
            "--with-files",
            self.content,
            "bench backup --with-files 플래그가 필요합니다.",
        )

    def test_has_bench_path_variable(self):
        self.assertIn(
            "BENCH_PATH",
            self.content,
            "BENCH_PATH 환경변수가 정의되어야 합니다.",
        )

    def test_has_site_name_variable(self):
        self.assertIn(
            "SITE_NAME",
            self.content,
            "SITE_NAME 환경변수가 정의되어야 합니다.",
        )

    def test_has_backup_dir_variable(self):
        self.assertIn(
            "BACKUP_DIR",
            self.content,
            "BACKUP_DIR 환경변수가 정의되어야 합니다.",
        )

    def test_has_upload_option(self):
        self.assertIn(
            "--upload",
            self.content,
            "--upload 옵션 처리가 필요합니다.",
        )

    def test_upload_graceful_when_bucket_not_set(self):
        # BACKUP_S3_BUCKET이 없을 때 WARN만 출력하고 종료하지 않아야 함
        self.assertIn(
            "BACKUP_S3_BUCKET",
            self.content,
            "BACKUP_S3_BUCKET 체크가 필요합니다.",
        )

    def test_has_local_retention_cleanup(self):
        # find + mtime 패턴으로 오래된 파일 삭제 (멀티라인 허용)
        self.assertTrue(
            re.search(r"find.*-mtime.*\+", self.content, re.DOTALL),
            "로컬 보관 정책 (find -mtime +N) 정리 로직이 필요합니다.",
        )

    def test_has_timestamp_in_dest_path(self):
        self.assertIn(
            "TIMESTAMP",
            self.content,
            "백업 경로에 타임스탬프(TIMESTAMP)를 사용해야 합니다.",
        )

    def test_has_metadata_output(self):
        self.assertIn(
            "backup_meta.json",
            self.content,
            "백업 메타데이터(backup_meta.json) 기록이 필요합니다.",
        )

    def test_bench_path_existence_check(self):
        # 디렉터리 존재 확인 패턴
        self.assertTrue(
            re.search(r'-d.*BENCH_PATH|BENCH_PATH.*-d', self.content),
            "BENCH_PATH 존재 여부를 확인해야 합니다.",
        )


class TestRestoreScriptStructure(unittest.TestCase):
    """restore_korea_hrms.sh 구조 요구사항."""

    def setUp(self):
        self.content = _read(RESTORE_SCRIPT)

    def test_has_bash_shebang(self):
        self.assertTrue(self.content.startswith("#!/bin/bash"))

    def test_has_set_euo_pipefail(self):
        self.assertIn("set -euo pipefail", self.content)

    def test_has_lc_all(self):
        self.assertIn("LC_ALL=C", self.content)

    def test_requires_confirmation_prompt(self):
        # read -rp で사용자 확인 요청
        self.assertTrue(
            re.search(r'read\s+-r?p\s+', self.content) or
            re.search(r'read\s+-[a-z]*p[a-z]*\s+', self.content),
            "복구 전 사용자 확인 프롬프트 (read -rp) 가 필요합니다.",
        )

    def test_confirmation_requires_uppercase_yes(self):
        # "YES" 대문자로 확인 (오타 방지)
        self.assertIn(
            '"YES"',
            self.content,
            '확인 입력값은 "YES" (대문자) 여야 합니다.',
        )

    def test_has_bench_restore(self):
        self.assertIn(
            "bench restore",
            self.content,
            "bench restore 명령을 사용해야 합니다.",
        )

    def test_has_bench_migrate(self):
        self.assertIn(
            "bench migrate",
            self.content,
            "복원 후 bench migrate를 실행해야 합니다.",
        )

    def test_has_backup_dir_argument(self):
        self.assertIn(
            "--backup-dir",
            self.content,
            "--backup-dir 인자가 필요합니다.",
        )

    def test_has_site_argument(self):
        self.assertIn(
            "--site",
            self.content,
            "--site 인자가 필요합니다.",
        )

    def test_has_sql_file_search(self):
        self.assertIn(
            ".sql.gz",
            self.content,
            "SQL 덤프 파일(.sql.gz) 검색 로직이 필요합니다.",
        )

    def test_validates_backup_dir_exists(self):
        self.assertTrue(
            re.search(r'-d.*BACKUP_DIR_ARG|BACKUP_DIR_ARG.*-d', self.content),
            "백업 디렉터리 존재 여부를 확인해야 합니다.",
        )


class TestDrillScriptStructure(unittest.TestCase):
    """backup_drill.sh 구조 요구사항."""

    def setUp(self):
        self.content = _read(DRILL_SCRIPT)

    def test_has_bash_shebang(self):
        self.assertTrue(self.content.startswith("#!/bin/bash"))

    def test_has_set_euo_pipefail(self):
        self.assertIn("set -euo pipefail", self.content)

    def test_has_lc_all(self):
        self.assertIn("LC_ALL=C", self.content)

    def test_blocks_prod_equals_test_site(self):
        # 운영 사이트 == 테스트 사이트 시 즉시 종료
        self.assertTrue(
            re.search(r'SITE_NAME.*==.*TEST_SITE_NAME|TEST_SITE_NAME.*==.*SITE_NAME', self.content),
            "운영 사이트 == 테스트 사이트 차단 로직이 필요합니다.",
        )

    def test_exits_on_prod_equals_test(self):
        # 차단 로직 내에 exit 1
        block_match = re.search(
            r'(SITE_NAME.*==.*TEST_SITE_NAME|TEST_SITE_NAME.*==.*SITE_NAME).*?exit\s+1',
            self.content,
            re.DOTALL,
        )
        self.assertIsNotNone(
            block_match,
            "운영/테스트 사이트 동일 시 exit 1로 종료해야 합니다.",
        )

    def test_uses_separate_test_site_name(self):
        self.assertIn(
            "TEST_SITE_NAME",
            self.content,
            "TEST_SITE_NAME 변수를 사용해야 합니다.",
        )

    def test_has_bench_restore(self):
        self.assertIn("bench restore", self.content)

    def test_has_bench_migrate(self):
        self.assertIn("bench migrate", self.content)

    def test_has_data_validation(self):
        # Employee 레코드 수 검증
        self.assertTrue(
            re.search(r'tabEmployee|Employee.*COUNT|COUNT.*Employee', self.content),
            "복원 후 Employee 레코드 수 검증 로직이 필요합니다.",
        )

    def test_has_pass_fail_reporting(self):
        self.assertIn("[PASS]", self.content, "[PASS] 결과 출력이 필요합니다.")
        self.assertIn("[FAIL]", self.content, "[FAIL] 결과 출력이 필요합니다.")

    def test_has_drill_log(self):
        self.assertIn(
            "DRILL_LOG",
            self.content,
            "드릴 로그 파일 경로 변수(DRILL_LOG)가 필요합니다.",
        )

    def test_has_keep_test_site_option(self):
        self.assertIn(
            "--keep-test-site",
            self.content,
            "--keep-test-site 옵션이 필요합니다.",
        )

    def test_cleans_up_test_site_by_default(self):
        # bench drop-site 명령이 있어야 함
        self.assertIn(
            "drop-site",
            self.content,
            "드릴 완료 후 테스트 사이트 drop-site 정리가 필요합니다.",
        )


class TestSystemdFiles(unittest.TestCase):
    """systemd 서비스/타이머 파일 구조 요구사항."""

    def test_service_has_type_oneshot(self):
        content = _read(SYSTEMD_SERVICE)
        self.assertIn("Type=oneshot", content, "service Type=oneshot 이 필요합니다.")

    def test_service_calls_backup_script(self):
        content = _read(SYSTEMD_SERVICE)
        self.assertIn(
            "backup_korea_hrms.sh",
            content,
            "service가 backup_korea_hrms.sh를 실행해야 합니다.",
        )

    def test_timer_has_oncalendar(self):
        content = _read(SYSTEMD_TIMER)
        self.assertIn("OnCalendar=", content, "timer OnCalendar 설정이 필요합니다.")

    def test_timer_runs_at_02(self):
        content = _read(SYSTEMD_TIMER)
        self.assertTrue(
            re.search(r'02:00', content),
            "timer가 02:00에 실행되도록 설정되어야 합니다.",
        )

    def test_timer_has_persistent(self):
        content = _read(SYSTEMD_TIMER)
        self.assertIn(
            "Persistent=true",
            content,
            "timer Persistent=true 설정이 필요합니다 (놓친 실행 복구).",
        )

    def test_service_has_user(self):
        content = _read(SYSTEMD_SERVICE)
        self.assertIn("User=", content, "service User= 설정이 필요합니다.")


class TestDocumentationExists(unittest.TestCase):
    """운영 문서 존재 여부 확인."""

    def test_backup_recovery_doc_exists(self):
        doc_path = REPO_ROOT / "docs" / "operations" / "backup_recovery.md"
        self.assertTrue(doc_path.exists(), f"문서 없음: {doc_path}")

    def test_doc_covers_rto_rpo(self):
        doc_path = REPO_ROOT / "docs" / "operations" / "backup_recovery.md"
        content = doc_path.read_text(encoding="utf-8")
        self.assertIn("RTO", content, "문서에 RTO 목표가 명시되어야 합니다.")
        self.assertIn("RPO", content, "문서에 RPO 목표가 명시되어야 합니다.")

    def test_doc_covers_s3_setup(self):
        doc_path = REPO_ROOT / "docs" / "operations" / "backup_recovery.md"
        content = doc_path.read_text(encoding="utf-8")
        self.assertIn(
            "S3",
            content,
            "문서에 S3/B2 셋업 섹션이 있어야 합니다.",
        )

    def test_doc_covers_disaster_recovery_scenarios(self):
        doc_path = REPO_ROOT / "docs" / "operations" / "backup_recovery.md"
        content = doc_path.read_text(encoding="utf-8")
        self.assertIn(
            "시나리오",
            content,
            "문서에 재해 복구 시나리오가 있어야 합니다.",
        )


if __name__ == "__main__":
    unittest.main()
