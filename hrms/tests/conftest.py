"""
conftest.py — hrms/tests/ 전용 pytest 설정

이 파일은 Frappe 없이 순수 Python 테스트(test_tenant_provisioning.py 등)를
pytest로 실행할 수 있도록 frappe 모듈을 sys.modules에 선등록합니다.

Frappe 환경(실제 bench)에서 실행할 때는 이 mock이 무시됩니다.
"""

import sys
import types


def _maybe_stub_frappe() -> None:
    """frappe가 설치되지 않은 환경에서 stub 모듈을 주입합니다."""
    if "frappe" in sys.modules:
        return

    # 최소한의 stub — import frappe 만 통과시키면 됩니다.
    frappe_stub = types.ModuleType("frappe")
    sys.modules["frappe"] = frappe_stub

    # hrms/__init__.py 가 import frappe 후 다른 frappe 서브모듈을 쓰는 경우 대비
    for sub in ("frappe.utils", "frappe.model", "frappe.desk"):
        sys.modules.setdefault(sub, types.ModuleType(sub))


_maybe_stub_frappe()
