"""
test_tenant_provisioning.py — 멀티 테넌트 프로비저닝 스크립트 구조 검증

이 테스트는 Frappe 없이 순수 Python(unittest)으로 실행됩니다.
실제 bench 명령어, Cloudflare API, cloudflared는 호출하지 않습니다.

실행:
    python -m pytest hrms/tests/test_tenant_provisioning.py -v
    또는
    python -m unittest hrms.tests.test_tenant_provisioning -v
"""

import ast
import importlib.util
import json
import os
import pathlib
import stat
import sys
import unittest

# 저장소 루트 계산 (hrms/tests/ → ../../)
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts" / "provisioning"
CONFIG_DIR = REPO_ROOT / "config"
DOCS_OPS_DIR = REPO_ROOT / "docs" / "operations"


# ─── 유틸 ────────────────────────────────────────────────────────────────────

def _read_text(path: pathlib.Path) -> str:
    with path.open("r", encoding="utf-8") as f:
        return f.read()


def _parse_py(path: pathlib.Path) -> ast.Module:
    """Python 파일을 ast.parse로 컴파일. 문법 오류 시 AssertionError."""
    src = _read_text(path)
    return ast.parse(src, filename=str(path))


def _function_names(tree: ast.Module) -> list[str]:
    return [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]


def _is_executable(path: pathlib.Path) -> bool:
    return bool(path.stat().st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))


# ─── create_tenant.sh 검증 ───────────────────────────────────────────────────

class TestCreateTenantSh(unittest.TestCase):
    SCRIPT = SCRIPTS_DIR / "create_tenant.sh"

    def setUp(self):
        self.assertTrue(self.SCRIPT.exists(), f"파일 없음: {self.SCRIPT}")
        self.content = _read_text(self.SCRIPT)

    def test_file_exists(self):
        self.assertTrue(self.SCRIPT.is_file())

    def test_shebang(self):
        first_line = self.content.splitlines()[0]
        self.assertTrue(
            first_line.startswith("#!/bin/bash"),
            "첫 줄이 #!/bin/bash여야 합니다"
        )

    def test_set_euo_pipefail(self):
        self.assertIn(
            "set -euo pipefail", self.content,
            "set -euo pipefail 필수"
        )

    def test_bench_new_site(self):
        self.assertIn("bench new-site", self.content)

    def test_install_erpnext(self):
        self.assertIn("install-app erpnext", self.content)

    def test_install_hrms(self):
        self.assertIn("install-app hrms", self.content)

    def test_cloudflare_dns_invocation(self):
        self.assertIn("cloudflare_dns_add.py", self.content)

    def test_cloudflared_ingress_invocation(self):
        self.assertIn("cloudflared_ingress_add.py", self.content)

    def test_host_name_set(self):
        self.assertIn("host_name", self.content)

    def test_multi_site_json_updated(self):
        self.assertIn("multi_site.json", self.content)

    def test_dry_run_flag(self):
        self.assertIn("--dry-run", self.content)

    def test_admin_email_arg(self):
        self.assertIn("admin_email", self.content.lower())

    def test_cloudflare_api_token_env_var(self):
        self.assertIn("CLOUDFLARE_API_TOKEN", self.content)

    def test_cloudflared_tunnel_id_env_var(self):
        self.assertIn("CLOUDFLARED_TUNNEL_ID", self.content)

    def test_bench_path_env_var(self):
        self.assertIn("BENCH_PATH", self.content)

    def test_arg_count_validation(self):
        # 인수 부족 시 에러 처리 확인
        self.assertRegex(self.content, r"\$#.*[<>]=?\s*[12]|argc|인수")

    def test_seed_demo_flag(self):
        self.assertIn("--seed-demo", self.content)

    def test_executable_bit(self):
        if self.SCRIPT.exists():
            self.assertTrue(
                _is_executable(self.SCRIPT),
                "create_tenant.sh에 실행 권한이 없습니다. chmod +x 필요"
            )


# ─── delete_tenant.sh 검증 ───────────────────────────────────────────────────

class TestDeleteTenantSh(unittest.TestCase):
    SCRIPT = SCRIPTS_DIR / "delete_tenant.sh"

    def setUp(self):
        self.assertTrue(self.SCRIPT.exists(), f"파일 없음: {self.SCRIPT}")
        self.content = _read_text(self.SCRIPT)

    def test_file_exists(self):
        self.assertTrue(self.SCRIPT.is_file())

    def test_shebang(self):
        first_line = self.content.splitlines()[0]
        self.assertTrue(first_line.startswith("#!/bin/bash"))

    def test_set_euo_pipefail(self):
        self.assertIn("set -euo pipefail", self.content)

    def test_backup_before_delete(self):
        """백업 명령어가 drop-site보다 먼저 나타나야 합니다."""
        backup_pos = self.content.find("backup")
        drop_pos = self.content.find("drop-site")
        self.assertGreater(backup_pos, -1, "backup 명령어 없음")
        self.assertGreater(drop_pos, -1, "drop-site 명령어 없음")
        self.assertLess(backup_pos, drop_pos, "백업이 삭제보다 먼저 실행되어야 합니다")

    def test_no_skip_backup_flag(self):
        """--skip-backup 플래그가 없어야 합니다 (안전 규칙)."""
        self.assertNotIn("--skip-backup", self.content)

    def test_confirmation_prompt(self):
        """사용자 확인 프롬프트 (read 명령어)가 있어야 합니다."""
        self.assertIn("read", self.content)

    def test_with_files_backup(self):
        self.assertIn("--with-files", self.content)

    def test_bench_drop_site(self):
        self.assertIn("drop-site", self.content)

    def test_multi_site_json_status_deleted(self):
        self.assertIn("deleted", self.content)
        self.assertIn("multi_site.json", self.content)

    def test_dry_run_flag(self):
        self.assertIn("--dry-run", self.content)

    def test_mariadb_root_password_env_var(self):
        """MARIADB_ROOT_PASSWORD 환경변수가 필요합니다."""
        self.assertIn("MARIADB_ROOT_PASSWORD", self.content)

    def test_mariadb_password_validated_early(self):
        """MARIADB_ROOT_PASSWORD 검증이 site 삭제 전에 나와야 합니다."""
        validation_pos = self.content.find("MARIADB_ROOT_PASSWORD")
        drop_pos = self.content.find("drop-site")
        self.assertGreater(validation_pos, -1, "MARIADB_ROOT_PASSWORD 없음")
        self.assertGreater(drop_pos, -1, "drop-site 없음")
        self.assertLess(validation_pos, drop_pos, "MARIADB_ROOT_PASSWORD 검증이 drop-site보다 먼저여야 합니다")

    def test_executable_bit(self):
        if self.SCRIPT.exists():
            self.assertTrue(
                _is_executable(self.SCRIPT),
                "delete_tenant.sh에 실행 권한이 없습니다. chmod +x 필요"
            )


# ─── cloudflare_dns_add.py 검증 ──────────────────────────────────────────────

class TestCloudflareDnsAdd(unittest.TestCase):
    SCRIPT = SCRIPTS_DIR / "cloudflare_dns_add.py"

    def setUp(self):
        self.assertTrue(self.SCRIPT.exists(), f"파일 없음: {self.SCRIPT}")
        self.content = _read_text(self.SCRIPT)
        self.tree = _parse_py(self.SCRIPT)

    def test_file_exists(self):
        self.assertTrue(self.SCRIPT.is_file())

    def test_syntax_valid(self):
        # _parse_py가 성공하면 문법 오류 없음
        self.assertIsInstance(self.tree, ast.Module)

    def test_no_external_dependencies(self):
        """requests, httpx 등 외부 라이브러리 import가 없어야 합니다."""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertNotIn(alias.name, ("requests", "httpx", "aiohttp"))
            elif isinstance(node, ast.ImportFrom):
                self.assertNotIn(node.module or "", ("requests", "httpx", "aiohttp"))

    def test_cloudflare_api_token_env_var(self):
        self.assertIn("CLOUDFLARE_API_TOKEN", self.content)

    def test_cname_type(self):
        self.assertIn("CNAME", self.content)

    def test_cfargotunnel_target(self):
        self.assertIn("cfargotunnel.com", self.content)

    def test_idempotent_already_exists(self):
        """record already exists 처리가 있어야 합니다."""
        self.assertIn("already exists", self.content)

    def test_zone_lookup(self):
        self.assertIn("zone", self.content.lower())

    def test_get_zone_id_function(self):
        funcs = _function_names(self.tree)
        self.assertIn("get_zone_id", funcs)

    def test_add_cname_function(self):
        funcs = _function_names(self.tree)
        self.assertIn("add_cname", funcs)

    def test_main_function(self):
        funcs = _function_names(self.tree)
        self.assertIn("main", funcs)

    def test_safeclaw_kr_default_zone(self):
        self.assertIn("safeclaw.kr", self.content)

    def test_arg_count_check(self):
        self.assertIn("len(argv)", self.content)


# ─── cloudflared_ingress_add.py 검증 ─────────────────────────────────────────

class TestCloudflaredIngressAdd(unittest.TestCase):
    SCRIPT = SCRIPTS_DIR / "cloudflared_ingress_add.py"

    def setUp(self):
        self.assertTrue(self.SCRIPT.exists(), f"파일 없음: {self.SCRIPT}")
        self.content = _read_text(self.SCRIPT)
        self.tree = _parse_py(self.SCRIPT)

    def test_file_exists(self):
        self.assertTrue(self.SCRIPT.is_file())

    def test_syntax_valid(self):
        self.assertIsInstance(self.tree, ast.Module)

    def test_yaml_import(self):
        self.assertIn("yaml", self.content)

    def test_config_yml_path(self):
        self.assertIn(".cloudflared", self.content)

    def test_insert_before_catch_all(self):
        """catch-all 직전 삽입 로직이 있어야 합니다."""
        self.assertIn("http_status:404", self.content)
        # catch-all 직전 삽입 함수
        funcs = _function_names(self.tree)
        self.assertIn("insert_before_catch_all", funcs)

    def test_idempotent_already_exists(self):
        self.assertIn("already_exists", self.content)

    def test_sighup(self):
        self.assertIn("SIGHUP", self.content)

    def test_reload_cloudflared_function(self):
        funcs = _function_names(self.tree)
        self.assertIn("reload_cloudflared", funcs)

    def test_load_config_function(self):
        funcs = _function_names(self.tree)
        self.assertIn("load_config", funcs)

    def test_save_config_function(self):
        funcs = _function_names(self.tree)
        self.assertIn("save_config", funcs)

    def test_main_function(self):
        funcs = _function_names(self.tree)
        self.assertIn("main", funcs)

    def test_cloudflared_config_path_env_var(self):
        self.assertIn("CLOUDFLARED_CONFIG_PATH", self.content)


# ─── config/multi_site.json 검증 ─────────────────────────────────────────────

class TestMultiSiteJson(unittest.TestCase):
    CONFIG = CONFIG_DIR / "multi_site.json"

    def setUp(self):
        self.assertTrue(self.CONFIG.exists(), f"파일 없음: {self.CONFIG}")
        with self.CONFIG.open("r", encoding="utf-8") as f:
            self.data = json.load(f)

    def test_file_exists(self):
        self.assertTrue(self.CONFIG.is_file())

    def test_valid_json(self):
        self.assertIsInstance(self.data, dict)

    def test_has_tenants_key(self):
        self.assertIn("tenants", self.data)
        self.assertIsInstance(self.data["tenants"], list)

    def test_has_routing_key(self):
        self.assertIn("routing", self.data)

    def test_routing_has_base_domain(self):
        self.assertIn("base_domain", self.data["routing"])
        self.assertIn("safeclaw.kr", self.data["routing"]["base_domain"])

    def test_has_quotas_key(self):
        self.assertIn("quotas", self.data)

    def test_quotas_has_plans(self):
        quotas = self.data["quotas"]
        for plan in ("starter", "professional", "enterprise"):
            self.assertIn(plan, quotas, f"quotas에 '{plan}' 플랜 없음")

    def test_quota_fields(self):
        for plan, quota in self.data["quotas"].items():
            self.assertIn("max_employees", quota, f"{plan} quota에 max_employees 없음")


# ─── docs/operations/multi_tenant.md 검증 ────────────────────────────────────

class TestMultiTenantDoc(unittest.TestCase):
    DOC = DOCS_OPS_DIR / "multi_tenant.md"

    def setUp(self):
        self.assertTrue(self.DOC.exists(), f"파일 없음: {self.DOC}")
        self.content = _read_text(self.DOC)

    def test_file_exists(self):
        self.assertTrue(self.DOC.is_file())

    def test_has_step_by_step_section(self):
        self.assertIn("Step-by-Step", self.content)

    def test_has_backup_section(self):
        self.assertIn("백업", self.content)

    def test_has_delete_section(self):
        self.assertIn("삭제", self.content)

    def test_has_migration_section(self):
        self.assertIn("마이그레이션", self.content)

    def test_has_data_isolation_description(self):
        self.assertIn("격리", self.content)

    def test_has_plan_table(self):
        for plan in ("starter", "professional", "enterprise"):
            self.assertIn(plan, self.content)

    def test_references_create_tenant_sh(self):
        self.assertIn("create_tenant.sh", self.content)

    def test_references_delete_tenant_sh(self):
        self.assertIn("delete_tenant.sh", self.content)

    def test_references_cloudflare(self):
        self.assertIn("Cloudflare", self.content)

    def test_references_cloudflared(self):
        self.assertIn("cloudflared", self.content)


# ─── 통합: 스크립트 간 일관성 ────────────────────────────────────────────────

class TestCrossScriptConsistency(unittest.TestCase):
    """스크립트들이 동일한 상수/경로를 참조하는지 확인."""

    def _read(self, path: pathlib.Path) -> str:
        return _read_text(path)

    def test_base_domain_consistent(self):
        """모든 스크립트가 hrms.safeclaw.kr을 사용해야 합니다."""
        for name in ("create_tenant.sh", "delete_tenant.sh",
                     "cloudflare_dns_add.py", "cloudflared_ingress_add.py"):
            content = self._read(SCRIPTS_DIR / name)
            self.assertIn(
                "safeclaw.kr", content,
                f"{name}에 safeclaw.kr 없음"
            )

    def test_multi_site_json_path_in_bash_scripts(self):
        """bash 스크립트들이 multi_site.json을 참조해야 합니다."""
        for name in ("create_tenant.sh", "delete_tenant.sh"):
            content = self._read(SCRIPTS_DIR / name)
            self.assertIn(
                "multi_site.json", content,
                f"{name}에 multi_site.json 참조 없음"
            )

    def test_cloudflare_env_var_consistent(self):
        """CLOUDFLARE_API_TOKEN이 DNS 스크립트와 create script 양쪽에 있어야 합니다."""
        for name in ("create_tenant.sh", "cloudflare_dns_add.py"):
            content = self._read(SCRIPTS_DIR / name)
            self.assertIn("CLOUDFLARE_API_TOKEN", content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
