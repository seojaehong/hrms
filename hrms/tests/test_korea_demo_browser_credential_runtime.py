#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import os
import pathlib
import sys
import types
import unittest
from unittest.mock import patch

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "demo_seed.py"


class FakeDB:
	def exists(self, doctype, filters=None):
		if doctype == "User" and filters == "demo.hr.manager@node.pe.kr":
			return True
		if doctype == "Employee" and filters == {"user_id": "demo.hr.manager@node.pe.kr", "status": "Active"}:
			return True
		return False


class FakeFrappe(types.ModuleType):
	def __init__(self):
		super().__init__("frappe")
		self.db = FakeDB()

	def get_doc(self, *args, **kwargs):
		raise AssertionError("get_doc should not be called by credential runtime test")

	def new_doc(self, *args, **kwargs):
		raise AssertionError("new_doc should not be called by credential runtime test")


class TestKoreaDemoBrowserCredentialRuntime(unittest.TestCase):
	def load_module(self):
		old_modules = {name: sys.modules.get(name) for name in ["frappe", "frappe.utils", "frappe.utils.password"]}
		fake_frappe = FakeFrappe()
		fake_utils = types.ModuleType("frappe.utils")
		fake_utils.getdate = lambda value=None: value
		fake_password = types.ModuleType("frappe.utils.password")
		fake_password.update_password = lambda username, password: None
		sys.modules["frappe"] = fake_frappe
		sys.modules["frappe.utils"] = fake_utils
		sys.modules["frappe.utils.password"] = fake_password
		try:
			spec = importlib.util.spec_from_file_location("korea_demo_seed_runtime_test", MODULE_PATH)
			module = importlib.util.module_from_spec(spec)
			assert spec.loader is not None
			spec.loader.exec_module(module)
			return module
		finally:
			for name, old in old_modules.items():
				if old is None:
					sys.modules.pop(name, None)
				else:
					sys.modules[name] = old

	def test_approved_demo_browser_credential_reads_password_from_env_without_kwarg(self):
		module = self.load_module()
		calls = []
		module.update_password = lambda username, password: calls.append((username, password))

		with patch.dict(os.environ, {"FRAPPE_BROWSER_PASSWORD": "runtime-secret"}, clear=False):
			result = module.ensure_demo_browser_credential(human_approved=True)

		self.assertEqual(calls, [("demo.hr.manager@node.pe.kr", "runtime-secret")])
		self.assertEqual(result["contract_type"], "korea_demo_browser_credential_runtime_apply_v1")
		self.assertFalse(result["requires_runtime_apply"])
		self.assertTrue(result["human_approval_verified"])
		self.assertTrue(result["credential_ready_for_browser_verifier"])
		self.assertEqual(result["password_env_var"], "FRAPPE_BROWSER_PASSWORD")
		self.assertNotIn("runtime-secret", str(result))

	def test_approved_demo_browser_credential_rejects_missing_env_password(self):
		module = self.load_module()
		with patch.dict(os.environ, {}, clear=True):
			with self.assertRaisesRegex(ValueError, "FRAPPE_BROWSER_PASSWORD"):
				module.ensure_demo_browser_credential(human_approved=True)


if __name__ == "__main__":
	unittest.main()
