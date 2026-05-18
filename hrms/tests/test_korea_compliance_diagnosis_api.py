#!/usr/bin/env python3
"""Direct-run tests for Korea compliance diagnosis preview API."""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "compliance_diagnosis_api.py"
CORE_PATH = pathlib.Path(__file__).resolve().parents[1] / "regional" / "south_korea" / "compliance_checklist.py"


def load_module(path: pathlib.Path, name: str):
	spec = importlib.util.spec_from_file_location(name, path)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


class TestKoreaComplianceDiagnosisApi(unittest.TestCase):
	def setUp(self):
		self.api = load_module(MODULE_PATH, "korea_compliance_diagnosis_api")
		self.core = load_module(CORE_PATH, "korea_compliance_checklist")
		self.items = self.core.evaluate_compliance_checklist(
			self.core.build_compliance_checklist(
				period_start=dt.date(2026, 5, 1),
				period_end=dt.date(2026, 5, 31),
			),
			completed_codes={"payslip-issue"},
			today=dt.date(2026, 7, 2),
		)

	def test_preview_api_accepts_json_payloads_without_frappe_mutation(self):
		items = [dict(item) for item in self.items]
		payload = self.api.preview_korea_compliance_diagnosis(
			items=json.dumps(items),
			evidence=json.dumps({"payslip-issue": ["Salary Slip SAL-2026-05-001"]}),
			reviewer="Labor Attorney Review Queue",
		)

		self.assertEqual(payload["contract_type"], "korea_compliance_diagnosis_preview_v1")
		self.assertEqual(payload["diagnosis"]["contract_type"], "korea_compliance_diagnosis_v1")
		self.assertEqual(payload["diagnosis"]["reviewer"], "Labor Attorney Review Queue")
		self.assertEqual(payload["runtime_action"], "preview_only")
		self.assertTrue(payload["requires_runtime_apply"])
		self.assertEqual(items, self.items)

	def test_preview_api_can_build_items_from_period_inputs(self):
		payload = self.api.preview_korea_compliance_diagnosis(
			period_start="2026-05-01",
			period_end="2026-05-31",
			completed_codes=json.dumps(["payroll-close"]),
			today="2026-06-11",
			evidence=json.dumps({"payroll-close": ["Payroll Entry PE-2026-05"]}),
		)

		self.assertEqual(payload["contract_type"], "korea_compliance_diagnosis_preview_v1")
		self.assertEqual(payload["source"]["period_start"], "2026-05-01")
		self.assertEqual(payload["source"]["period_end"], "2026-05-31")
		self.assertEqual(payload["diagnosis"]["summary"], {"Completed": 1, "Open": 1, "Overdue": 2})
		by_code = {finding["code"]: finding for finding in payload["diagnosis"]["findings"]}
		self.assertEqual(by_code["payroll-close"]["evidence_status"], "attached")
		self.assertEqual(by_code["payslip-issue"]["severity"], "critical")

	def test_preview_api_rejects_mutually_ambiguous_sources(self):
		with self.assertRaisesRegex(ValueError, "provide either items or period_start/period_end"):
			self.api.preview_korea_compliance_diagnosis(
				items=self.items,
				period_start="2026-05-01",
				period_end="2026-05-31",
			)

		with self.assertRaisesRegex(ValueError, "items or period_start/period_end is required"):
			self.api.preview_korea_compliance_diagnosis()

	def test_preview_api_rejects_invalid_json_and_non_list_items(self):
		with self.assertRaisesRegex(ValueError, "JSON payload is invalid"):
			self.api.preview_korea_compliance_diagnosis(items='[{"code":')

		with self.assertRaisesRegex(ValueError, "items must be a list"):
			self.api.preview_korea_compliance_diagnosis(items=json.dumps({"code": "payroll-close"}))

	def test_preview_api_rejects_invalid_dates_and_completed_codes_shape(self):
		with self.assertRaisesRegex(ValueError, "period_start must be an ISO date"):
			self.api.preview_korea_compliance_diagnosis(period_start="2026/05/01", period_end="2026-05-31")

		with self.assertRaisesRegex(ValueError, "period_start and period_end are both required"):
			self.api.preview_korea_compliance_diagnosis(period_start="2026-05-01")

		with self.assertRaisesRegex(ValueError, "completed_codes must be a list"):
			self.api.preview_korea_compliance_diagnosis(
				period_start="2026-05-01",
				period_end="2026-05-31",
				completed_codes="payroll-close",
			)

		with self.assertRaisesRegex(ValueError, "completed_codes entries must be strings"):
			self.api.preview_korea_compliance_diagnosis(
				period_start="2026-05-01",
				period_end="2026-05-31",
				completed_codes=json.dumps([{"bad": 1}]),
			)

	def test_preview_api_rejects_malformed_evidence_shape_as_validation_error(self):
		with self.assertRaisesRegex(ValueError, "evidence values must be lists"):
			self.api.preview_korea_compliance_diagnosis(
				items=self.items,
				evidence={"payroll-close": "doc-123"},
			)

	def test_checklist_doc_name_requires_frappe_runtime_in_direct_mode(self):
		with self.assertRaisesRegex(RuntimeError, "Frappe runtime is required"):
			self.api.preview_korea_compliance_diagnosis(items="KOREA-CHECKLIST-0001")


if __name__ == "__main__":
	unittest.main()
