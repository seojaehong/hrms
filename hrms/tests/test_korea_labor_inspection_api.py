#!/usr/bin/env python3
"""Direct-run tests for Korea labor inspection checklist API wrapper (framework-free)."""

from __future__ import annotations

import importlib.util
import pathlib
import unittest

MODULE_PATH = (
	pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "labor_inspection_api.py"
)

REQUIRED_FIELDS = ("id", "category", "item", "legal_basis", "risk", "automated_check")


def load_module():
	spec = importlib.util.spec_from_file_location("korea_labor_inspection_api", MODULE_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


class TestLaborInspectionApi(unittest.TestCase):
	def setUp(self):
		self.mod = load_module()

	def test_list_inspection_checklist_api_returns_15_items(self):
		items = self.mod.list_inspection_checklist_api()

		self.assertIsInstance(items, list)
		self.assertEqual(len(items), 15)

	def test_items_have_required_fields(self):
		items = self.mod.list_inspection_checklist_api()

		for item in items:
			for field in REQUIRED_FIELDS:
				self.assertIn(field, item, f"missing field {field} in {item.get('id')}")
			self.assertIsInstance(item["evidence_needed"], list)
			self.assertGreater(len(item["evidence_needed"]), 0)
			self.assertIsInstance(item["risk"], dict)
			self.assertIn("type", item["risk"])

	def test_matches_core_loader_output(self):
		core_path = MODULE_PATH.parent / "labor_inspection_checklist.py"
		core_spec = importlib.util.spec_from_file_location("korea_labor_inspection_checklist_core", core_path)
		core = importlib.util.module_from_spec(core_spec)
		assert core_spec.loader is not None
		core_spec.loader.exec_module(core)

		self.assertEqual(self.mod.list_inspection_checklist_api(), core.load_labor_inspection_checklist())

	def test_json_safe(self):
		import json

		items = self.mod.list_inspection_checklist_api()
		json.dumps(items, ensure_ascii=False)

	def test_no_frappe_whitelist_error_without_frappe(self):
		# 모듈 로드 자체가 frappe 없이 성공해야 한다 (조건부 import 컨벤션 확인)
		self.assertFalse(self.mod._FRAPPE_AVAILABLE)


if __name__ == "__main__":
	unittest.main()
