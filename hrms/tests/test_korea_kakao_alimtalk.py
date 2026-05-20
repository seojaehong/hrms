"""카카오 알림톡 발송 path 테스트.

Frappe 없이 standalone 실행 가능 (FakeFrappe 패턴 사용).
실제 HTTP 호출 없이 mock transport 로 Solapi 응답을 시뮬레이션.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import types
import unittest


# ---------------------------------------------------------------------------
# Fake Frappe 설정 — Frappe bench 없이 테스트 실행
# ---------------------------------------------------------------------------


class FakeFrappeError(Exception):
	pass


class FakeDB:
	def __init__(self):
		self.employee_phones: dict[str, str] = {}
		# (doctype, name) -> {field: value}
		self._records: dict[tuple[str, str], dict[str, str]] = {}

	def get_value(self, doctype, name, field):
		if doctype == "Employee":
			# cell_number 우선 반환
			if field == "cell_number":
				return self.employee_phones.get(name)
			if field in ("custom_kakao_phone", "custom_mobile_number"):
				return None
		record = self._records.get((doctype, name), {})
		return record.get(field)

	def set_record(self, doctype, name, field, value):
		self._records.setdefault((doctype, name), {})[field] = value

	def exists(self, doctype, filters):
		return False

	def get_table_columns(self, doctype):
		return []


class FakeLogger:
	def info(self, msg):
		pass

	def warning(self, msg):
		pass

	def error(self, msg):
		pass


class FakeFrappeModule(types.SimpleNamespace):
	def __init__(self):
		super().__init__()
		self.db = FakeDB()
		self._ = lambda value: value
		self.whitelist = lambda *args, **kwargs: (lambda fn: fn)
		self.throw = self._throw
		self.log_error = lambda *args, **kwargs: None
		self.local = types.SimpleNamespace(form_dict={}, request=None)
		self.conf = types.SimpleNamespace()
		self._comments = []

	def _throw(self, message, exc=None):
		raise FakeFrappeError(message)

	def logger(self, name):
		return FakeLogger()

	def get_doc(self, payload):
		self._comments.append(payload)
		return types.SimpleNamespace(insert=lambda ignore_permissions=False: payload)


def _load_module(rel_path: str, module_name: str):
	"""프로젝트 루트 기준 상대 경로로 모듈 로드."""
	root = pathlib.Path(__file__).resolve().parents[2]
	module_path = root / rel_path
	spec = importlib.util.spec_from_file_location(module_name, module_path)
	mod = importlib.util.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(mod)
	return mod


# ---------------------------------------------------------------------------
# 테스트 케이스
# ---------------------------------------------------------------------------


class TestKakaoAlimtalkSend(unittest.TestCase):
	def setUp(self):
		self.fake_frappe = FakeFrappeModule()
		sys.modules["frappe"] = self.fake_frappe
		# notification 모듈 로드 (패키지 import path 없이 직접 로드)
		self.mod = _load_module(
			"hrms/regional/south_korea/kakao_notification.py",
			"test_kakao_notification_module",
		)

	def tearDown(self):
		sys.modules.pop("frappe", None)
		# 캐시된 모듈 제거 (다음 setUp 에서 재로드 보장)
		for key in list(sys.modules.keys()):
			if "test_kakao_notification" in key:
				sys.modules.pop(key, None)

	# ------------------------------------------------------------------
	# 1. credentials 없으면 dry_run 자동
	# ------------------------------------------------------------------
	def test_no_credentials_triggers_dry_run(self):
		"""SOLAPI_API_KEY 없으면 dry_run=True, sent=False 반환."""
		import os  # noqa: PLC0415

		os.environ.pop("SOLAPI_API_KEY", None)
		os.environ.pop("SOLAPI_API_SECRET", None)

		result = self.mod.send_kakao_alimtalk(
			pf_id="PF_TEST",
			template_id="korea_wage_statement",
			to="01012345678",
			template_variables={"employee_name": "홍길동", "period": "2026-04", "total_amount": "3,000,000", "link": "https://example.com"},
			human_approved=True,
		)

		self.assertTrue(result["dry_run"], "credentials 없으면 dry_run 이어야 한다")
		self.assertFalse(result["sent"], "dry_run 시 sent=False")
		self.assertEqual(result["contract_type"], "korea_kakao_alimtalk_send_v1")
		self.assertEqual(result["runtime_action"], "kakao_alimtalk_send")
		self.assertIn("no_credentials", result["reason"])

	# ------------------------------------------------------------------
	# 2. human_approved=False → fail-closed
	# ------------------------------------------------------------------
	def test_human_approved_false_fail_closed(self):
		"""human_approved=False 이면 발송 없이 fail-closed dict 반환."""
		result = self.mod.send_kakao_alimtalk(
			pf_id="PF_TEST",
			template_id="korea_wage_statement",
			to="01012345678",
			template_variables={},
			human_approved=False,
		)

		self.assertFalse(result["sent"])
		self.assertFalse(result["human_approval_verified"])
		self.assertEqual(result["contract_type"], "korea_kakao_alimtalk_send_v1")
		self.assertEqual(result["runtime_action"], "kakao_alimtalk_send")
		self.assertEqual(result["reason"], "human_approval_required")
		self.assertIsNone(result["message_id"])

	# ------------------------------------------------------------------
	# 3. dry_run=True 명시 (credentials 있어도 발송 X)
	# ------------------------------------------------------------------
	def test_explicit_dry_run_skips_send(self):
		"""dry_run=True 이면 credentials 있어도 발송 없이 반환."""
		import os  # noqa: PLC0415

		os.environ["SOLAPI_API_KEY"] = "test_key"
		os.environ["SOLAPI_API_SECRET"] = "test_secret"

		try:
			result = self.mod.send_kakao_alimtalk(
				pf_id="PF_TEST",
				template_id="korea_wage_statement",
				to="01099999999",
				template_variables={"employee_name": "이순신", "period": "2026-05", "total_amount": "5,000,000", "link": ""},
				human_approved=True,
				dry_run=True,
			)
			self.assertTrue(result["dry_run"])
			self.assertFalse(result["sent"])
			self.assertEqual(result["contract_type"], "korea_kakao_alimtalk_send_v1")
		finally:
			os.environ.pop("SOLAPI_API_KEY", None)
			os.environ.pop("SOLAPI_API_SECRET", None)

	# ------------------------------------------------------------------
	# 4. 반환 dict 필드 완전성 검증 (fail-closed 경로)
	# ------------------------------------------------------------------
	def test_contract_envelope_complete_on_fail_closed(self):
		"""fail-closed 경우에도 contract 필드 전체가 존재해야 한다."""
		result = self.mod.send_kakao_alimtalk(
			pf_id="PF",
			template_id="korea_leave_approved",
			to="01055556666",
			template_variables={},
			human_approved=False,
		)

		required_keys = {
			"contract_type",
			"runtime_action",
			"sent",
			"dry_run",
			"message_id",
			"to",
			"template_id",
			"human_approval_verified",
			"reason",
		}
		for key in required_keys:
			self.assertIn(key, result, f"계약 필드 누락: {key}")

	# ------------------------------------------------------------------
	# 5. template_variables #{var} 치환 검증
	# ------------------------------------------------------------------
	def test_template_variable_substitution(self):
		"""preview 에서 #{var} 이 올바르게 치환되는지 확인."""
		result = self.mod.preview_kakao_alimtalk(
			pf_id="PF_TEST",
			template_id="korea_wage_statement",
			to="01012345678",
			template_variables={
				"employee_name": "김민준",
				"period": "2026-05",
				"total_amount": "3,500,000",
				"link": "https://app.example.com/salary/SS-001",
			},
		)

		content = result["rendered_content"]
		self.assertIn("김민준", content)
		self.assertIn("2026-05", content)
		self.assertIn("3,500,000", content)
		self.assertIn("https://app.example.com/salary/SS-001", content)
		# 치환되지 않은 #{...} 없어야 함
		self.assertNotIn("#{", content)
		self.assertEqual(result["missing_variables"], [])

	# ------------------------------------------------------------------
	# 6. 미입력 변수 탐지
	# ------------------------------------------------------------------
	def test_missing_variables_detected(self):
		"""일부 변수 누락 시 missing_variables 에 포함되는지 확인."""
		result = self.mod.preview_kakao_alimtalk(
			pf_id="PF_TEST",
			template_id="korea_wage_statement",
			to="01012345678",
			template_variables={
				"employee_name": "박지현",
				# period, total_amount, link 누락
			},
		)

		missing = result["missing_variables"]
		self.assertIn("period", missing)
		self.assertIn("total_amount", missing)
		self.assertIn("link", missing)

	# ------------------------------------------------------------------
	# 7. Solapi mock transport — 성공 응답
	# ------------------------------------------------------------------
	def test_solapi_mock_transport_success(self):
		"""mock transport 로 Solapi 성공 응답을 시뮬레이션."""
		import os  # noqa: PLC0415

		os.environ["SOLAPI_API_KEY"] = "test_key"
		os.environ["SOLAPI_API_SECRET"] = "test_secret"

		def mock_transport(url: str, headers: dict, body: bytes) -> dict:
			return {"messageId": "MSG-2026-0001", "statusCode": "2000", "statusMessage": "정상"}

		try:
			result = self.mod.send_kakao_alimtalk(
				pf_id="PF_WINNERS",
				template_id="korea_wage_statement",
				to="01011112222",
				template_variables={
					"employee_name": "최영희",
					"period": "2026-05",
					"total_amount": "2,800,000",
					"link": "https://hrms.example.com/SS-0042",
				},
				human_approved=True,
				dry_run=False,
				_transport=mock_transport,
			)

			self.assertTrue(result["sent"])
			self.assertFalse(result["dry_run"])
			self.assertEqual(result["message_id"], "MSG-2026-0001")
			self.assertEqual(result["contract_type"], "korea_kakao_alimtalk_send_v1")
			self.assertTrue(result["human_approval_verified"])
			self.assertIsNone(result["reason"])
		finally:
			os.environ.pop("SOLAPI_API_KEY", None)
			os.environ.pop("SOLAPI_API_SECRET", None)

	# ------------------------------------------------------------------
	# 8. Solapi mock transport — 오류 응답
	# ------------------------------------------------------------------
	def test_solapi_mock_transport_error(self):
		"""mock transport 가 RuntimeError 를 일으키면 sent=False, reason 설정."""
		import os  # noqa: PLC0415

		os.environ["SOLAPI_API_KEY"] = "test_key"
		os.environ["SOLAPI_API_SECRET"] = "test_secret"

		def failing_transport(url: str, headers: dict, body: bytes) -> dict:
			raise RuntimeError("Solapi HTTP 400: invalid_pf_id")

		try:
			result = self.mod.send_kakao_alimtalk(
				pf_id="INVALID_PF",
				template_id="korea_wage_statement",
				to="01099990000",
				template_variables={
					"employee_name": "정호준",
					"period": "2026-05",
					"total_amount": "1,000,000",
					"link": "",
				},
				human_approved=True,
				dry_run=False,
				_transport=failing_transport,
			)

			self.assertFalse(result["sent"])
			self.assertIsNotNone(result["reason"])
			self.assertIn("send_error", result["reason"])
			# contract envelope 유지
			self.assertEqual(result["contract_type"], "korea_kakao_alimtalk_send_v1")
		finally:
			os.environ.pop("SOLAPI_API_KEY", None)
			os.environ.pop("SOLAPI_API_SECRET", None)

	# ------------------------------------------------------------------
	# 9. list_alimtalk_templates — 최소 5개 템플릿
	# ------------------------------------------------------------------
	def test_list_alimtalk_templates_minimum_count(self):
		"""템플릿 카탈로그에 최소 5개 이상 존재해야 한다."""
		templates = self.mod.list_alimtalk_templates()
		self.assertIsInstance(templates, list)
		self.assertGreaterEqual(len(templates), 5, "최소 5개 표준 템플릿 필요")

	# ------------------------------------------------------------------
	# 10. list_alimtalk_templates — 구조 검증
	# ------------------------------------------------------------------
	def test_list_alimtalk_templates_structure(self):
		"""각 템플릿이 필수 필드를 가지고 있고 #{var} 형식이 일치하는지 확인."""
		templates = self.mod.list_alimtalk_templates()
		for tmpl in templates:
			with self.subTest(template_id=tmpl.get("template_id")):
				self.assertIn("template_id", tmpl)
				self.assertIn("title", tmpl)
				self.assertIn("content", tmpl)
				self.assertIn("variables", tmpl)

				# content 에서 #{var} 추출한 변수가 variables 목록에 있는지 확인
				import re  # noqa: PLC0415

				found_vars = re.findall(r"#\{(\w+)\}", tmpl["content"])
				declared_vars = set(tmpl["variables"])
				for var in found_vars:
					self.assertIn(
						var,
						declared_vars,
						f"content 의 #{{{var}}} 이 variables 에 없음 (template: {tmpl['template_id']})",
					)

	# ------------------------------------------------------------------
	# 11. preview contract 필드 완전성
	# ------------------------------------------------------------------
	def test_preview_contract_fields(self):
		"""preview 반환값에 계약 필드가 모두 있어야 한다."""
		result = self.mod.preview_kakao_alimtalk(
			pf_id="PF_TEST",
			template_id="korea_payroll_closing",
			to="01033334444",
			template_variables={},
		)

		required_keys = {
			"contract_type",
			"runtime_action",
			"pf_id",
			"template_id",
			"to",
			"rendered_content",
			"missing_variables",
			"template_variables",
		}
		for key in required_keys:
			self.assertIn(key, result, f"preview 계약 필드 누락: {key}")
		self.assertEqual(result["runtime_action"], "kakao_alimtalk_preview")

	# ------------------------------------------------------------------
	# 12. message_id 추출 — result 배열 형식
	# ------------------------------------------------------------------
	def test_extract_message_id_from_result_array(self):
		"""Solapi 응답이 result 배열 형식일 때 messageId 추출."""
		response = {"result": [{"messageId": "MSG-LIST-001", "statusCode": "2000"}]}
		message_id = self.mod._extract_message_id(response)
		self.assertEqual(message_id, "MSG-LIST-001")

	# ------------------------------------------------------------------
	# 13. message_id 추출 — 직접 필드 형식
	# ------------------------------------------------------------------
	def test_extract_message_id_direct_field(self):
		"""Solapi 응답이 messageId 직접 포함 시 추출."""
		response = {"messageId": "MSG-DIRECT-002", "statusCode": "2000"}
		message_id = self.mod._extract_message_id(response)
		self.assertEqual(message_id, "MSG-DIRECT-002")

	# ------------------------------------------------------------------
	# 14. human_approved=False 와 dry_run=True 동시: fail-closed 우선
	# ------------------------------------------------------------------
	def test_human_approved_false_takes_priority_over_dry_run(self):
		"""human_approved=False 이면 dry_run=True 여도 fail-closed 가 우선."""
		result = self.mod.send_kakao_alimtalk(
			pf_id="PF_TEST",
			template_id="korea_wage_statement",
			to="01077778888",
			template_variables={},
			human_approved=False,
			dry_run=True,
		)

		self.assertFalse(result["sent"])
		self.assertFalse(result["human_approval_verified"])
		self.assertEqual(result["reason"], "human_approval_required")

	# ------------------------------------------------------------------
	# 15. get_kakao_credentials — 환경변수에서 올바르게 읽기
	# ------------------------------------------------------------------
	def test_get_kakao_credentials_from_env(self):
		"""환경변수 설정 시 credentials dict 반환."""
		import os  # noqa: PLC0415

		os.environ["SOLAPI_API_KEY"] = "my_api_key"
		os.environ["SOLAPI_API_SECRET"] = "my_api_secret"
		try:
			creds = self.mod.get_kakao_credentials()
			self.assertIsNotNone(creds)
			self.assertEqual(creds["api_key"], "my_api_key")
			self.assertEqual(creds["api_secret"], "my_api_secret")
		finally:
			os.environ.pop("SOLAPI_API_KEY", None)
			os.environ.pop("SOLAPI_API_SECRET", None)

	# ------------------------------------------------------------------
	# 16. get_kakao_credentials — 키 없으면 None
	# ------------------------------------------------------------------
	def test_get_kakao_credentials_returns_none_without_env(self):
		"""환경변수 없으면 None 반환."""
		import os  # noqa: PLC0415

		os.environ.pop("SOLAPI_API_KEY", None)
		os.environ.pop("SOLAPI_API_SECRET", None)
		creds = self.mod.get_kakao_credentials()
		self.assertIsNone(creds)

	# ------------------------------------------------------------------
	# 17. enhanced dry-run — 비용 추정 필드
	# ------------------------------------------------------------------
	def test_enhanced_dry_run_includes_cost_estimate(self):
		"""dry_run=True 응답에 cost_estimate_krw 필드가 포함되어야 한다."""
		import os  # noqa: PLC0415

		os.environ.pop("SOLAPI_API_KEY", None)
		os.environ.pop("SOLAPI_API_SECRET", None)

		result = self.mod.send_kakao_alimtalk(
			pf_id="PF_TEST",
			template_id="korea_wage_statement",
			to="01012345678",
			template_variables={
				"employee_name": "홍길동",
				"period": "2026-05",
				"total_amount": "3,000,000",
				"link": "https://example.com",
			},
			human_approved=True,
			dry_run=True,
		)

		self.assertTrue(result["dry_run"])
		self.assertFalse(result["sent"])
		self.assertIn("cost_estimate_krw", result)
		self.assertEqual(result["cost_estimate_krw"], 8.4)

	# ------------------------------------------------------------------
	# 18. enhanced dry-run — mock_response Solapi 형식 + messageId 추출 가능
	# ------------------------------------------------------------------
	def test_enhanced_dry_run_mock_response_parseable_by_extract_message_id(self):
		"""dry-run mock_response 는 _extract_message_id() 로 messageId 추출 가능해야 한다."""
		import os  # noqa: PLC0415

		os.environ.pop("SOLAPI_API_KEY", None)
		os.environ.pop("SOLAPI_API_SECRET", None)

		result = self.mod.send_kakao_alimtalk(
			pf_id="PF_TEST",
			template_id="korea_leave_approved",
			to="01098765432",
			template_variables={
				"employee_name": "이순신",
				"leave_type": "연차",
				"from_date": "2026-06-01",
				"to_date": "2026-06-03",
				"leave_days": "3",
				"approver_name": "김부장",
			},
			human_approved=True,
			dry_run=True,
		)

		self.assertIn("mock_response", result)
		mock_resp = result["mock_response"]
		# mock_response 가 실제 Solapi 응답 형식과 동일해야 함
		self.assertIn("messageId", mock_resp)
		self.assertIn("statusCode", mock_resp)
		self.assertEqual(mock_resp["statusCode"], "2000")
		# _extract_message_id() 로 파싱 가능한지 자가 검증
		extracted = self.mod._extract_message_id(mock_resp)
		self.assertIsNotNone(extracted)
		self.assertTrue(extracted.startswith("DRY-RUN-"))

	# ------------------------------------------------------------------
	# 19. enhanced dry-run — PII 마스킹 (masked_to)
	# ------------------------------------------------------------------
	def test_enhanced_dry_run_pii_masking_in_masked_to(self):
		"""dry-run 응답에 masked_to 필드가 포함되고, 전화번호가 마스킹되어야 한다."""
		import os  # noqa: PLC0415

		os.environ.pop("SOLAPI_API_KEY", None)
		os.environ.pop("SOLAPI_API_SECRET", None)

		result = self.mod.send_kakao_alimtalk(
			pf_id="PF_TEST",
			template_id="korea_wage_statement",
			to="01012345678",
			template_variables={
				"employee_name": "박민수",
				"period": "2026-05",
				"total_amount": "2,500,000",
				"link": "https://example.com",
			},
			human_approved=True,
			dry_run=True,
		)

		self.assertIn("masked_to", result)
		masked = result["masked_to"]
		# 실제 번호가 노출되지 않아야 함
		self.assertNotIn("12345678", masked)
		self.assertIn("****", masked)
		# 원본 to 필드는 유지 (호출자가 필요할 수 있음)
		self.assertEqual(result["to"], "01012345678")

	# ------------------------------------------------------------------
	# 20. enhanced dry-run — 기존 계약 필드 유지 (호환성 회귀)
	# ------------------------------------------------------------------
	def test_enhanced_dry_run_preserves_existing_contract_fields(self):
		"""enhanced dry-run 이 기존 계약 필드를 모두 유지해야 한다 (호환성 회귀)."""
		import os  # noqa: PLC0415

		os.environ.pop("SOLAPI_API_KEY", None)
		os.environ.pop("SOLAPI_API_SECRET", None)

		result = self.mod.send_kakao_alimtalk(
			pf_id="PF_TEST",
			template_id="korea_wage_statement",
			to="01099990000",
			template_variables={
				"employee_name": "최민준",
				"period": "2026-05",
				"total_amount": "4,000,000",
				"link": "https://example.com",
			},
			human_approved=True,
			dry_run=True,
		)

		# 기존 계약 필드 — 변경 금지
		required_legacy_keys = {
			"contract_type",
			"runtime_action",
			"sent",
			"dry_run",
			"message_id",
			"to",
			"template_id",
			"human_approval_verified",
			"reason",
		}
		for key in required_legacy_keys:
			self.assertIn(key, result, f"기존 계약 필드 누락: {key}")
		self.assertEqual(result["contract_type"], "korea_kakao_alimtalk_send_v1")
		self.assertEqual(result["runtime_action"], "kakao_alimtalk_send")
		self.assertFalse(result["sent"])
		self.assertTrue(result["dry_run"])
		self.assertIsNone(result["message_id"])
		self.assertTrue(result["human_approval_verified"])

	# ------------------------------------------------------------------
	# 21. _build_mock_solapi_response — 호출당 고유 messageId 생성
	# ------------------------------------------------------------------
	def test_mock_solapi_response_generates_unique_message_ids(self):
		"""_build_mock_solapi_response 는 호출할 때마다 다른 messageId 를 생성해야 한다."""
		resp1 = self.mod._build_mock_solapi_response(template_id="korea_wage_statement")
		resp2 = self.mod._build_mock_solapi_response(template_id="korea_wage_statement")
		self.assertNotEqual(resp1["messageId"], resp2["messageId"])
		# 두 응답 모두 _extract_message_id 로 파싱 가능
		self.assertIsNotNone(self.mod._extract_message_id(resp1))
		self.assertIsNotNone(self.mod._extract_message_id(resp2))


# ---------------------------------------------------------------------------
# 디스패처 테스트
# ---------------------------------------------------------------------------


class TestKakaoNotificationDispatcher(unittest.TestCase):
	def setUp(self):
		self.fake_frappe = FakeFrappeModule()
		sys.modules["frappe"] = self.fake_frappe
		# kakao_notification 먼저 로드
		self.notif_mod = _load_module(
			"hrms/regional/south_korea/kakao_notification.py",
			"test_kakao_notification_dispatcher_dep",
		)
		sys.modules["hrms.regional.south_korea.kakao_notification"] = self.notif_mod
		# dispatcher 로드 (kakao_notification 에 의존)
		self.dispatcher_mod = _load_module(
			"hrms/regional/south_korea/notification_dispatcher.py",
			"test_kakao_notification_dispatcher",
		)

	def tearDown(self):
		sys.modules.pop("frappe", None)
		for key in list(sys.modules.keys()):
			if key == "hrms.regional.south_korea.kakao_notification" or "test_kakao_notification" in key or "test_kakao_dispatcher" in key:
				sys.modules.pop(key, None)

	def test_salary_slip_submit_no_phone_skips_gracefully(self):
		"""직원 전화번호 없으면 Comment 삽입 없이 종료."""
		doc = types.SimpleNamespace(
			name="SS-0001",
			employee="EMP-0001",
			employee_name="김직원",
			net_pay=3000000,
			start_date="2026-05-01",
			end_date="2026-05-31",
		)
		# 전화번호 없음
		self.dispatcher_mod.on_salary_slip_submit(doc)
		self.assertEqual(len(self.fake_frappe._comments), 0)

	def test_salary_slip_submit_with_phone_inserts_comment(self):
		"""직원 전화번호 있으면 발송 대기 Comment 기록."""
		self.fake_frappe.db.employee_phones["EMP-0002"] = "01012341234"

		doc = types.SimpleNamespace(
			name="SS-0002",
			employee="EMP-0002",
			employee_name="이직원",
			net_pay=4200000,
			start_date="2026-05-01",
			end_date="2026-05-31",
		)
		self.dispatcher_mod.on_salary_slip_submit(doc)
		self.assertEqual(len(self.fake_frappe._comments), 1)
		comment = self.fake_frappe._comments[0]
		self.assertEqual(comment["reference_doctype"], "Salary Slip")
		self.assertEqual(comment["reference_name"], "SS-0002")
		self.assertIn("카카오 알림톡 발송 대기", comment["content"])
		self.assertIn("korea_wage_statement", comment["content"])

	def test_leave_application_approve_not_approved_skips(self):
		"""Leave Application 상태가 Approved 아니면 Comment 없음."""
		doc = types.SimpleNamespace(
			name="LEAVE-0001",
			doctype="Leave Application",
			employee="EMP-0001",
			employee_name="박직원",
			status="Open",
			leave_type="연차",
			from_date="2026-06-01",
			to_date="2026-06-01",
			total_leave_days=1,
			leave_approver="admin@example.com",
		)
		self.dispatcher_mod.on_leave_application_approve(doc)
		self.assertEqual(len(self.fake_frappe._comments), 0)

	def test_leave_application_approve_inserts_comment(self):
		"""Leave Application Approved + 전화번호 있으면 Comment 기록."""
		self.fake_frappe.db.employee_phones["EMP-0003"] = "01098765432"
		# DB 의 previous status 는 Open (미승인 상태) → 전환 감지
		self.fake_frappe.db.set_record("Leave Application", "LEAVE-0002", "status", "Open")

		doc = types.SimpleNamespace(
			name="LEAVE-0002",
			doctype="Leave Application",
			employee="EMP-0003",
			employee_name="최직원",
			status="Approved",
			leave_type="연차",
			from_date="2026-06-10",
			to_date="2026-06-11",
			total_leave_days=2,
			leave_approver="hr@example.com",
		)
		self.dispatcher_mod.on_leave_application_approve(doc)
		self.assertEqual(len(self.fake_frappe._comments), 1)
		comment = self.fake_frappe._comments[0]
		self.assertEqual(comment["reference_doctype"], "Leave Application")
		self.assertEqual(comment["reference_name"], "LEAVE-0002")
		self.assertIn("korea_leave_approved", comment["content"])

	def test_leave_application_approve_no_duplicate_on_re_save(self):
		"""이미 Approved 인 Leave Application 재저장 시 Comment 중복 없음."""
		self.fake_frappe.db.employee_phones["EMP-0004"] = "01011112222"
		# DB 에 이미 Approved 로 저장된 상태
		self.fake_frappe.db.set_record("Leave Application", "LEAVE-0003", "status", "Approved")

		doc = types.SimpleNamespace(
			name="LEAVE-0003",
			doctype="Leave Application",
			employee="EMP-0004",
			employee_name="강직원",
			status="Approved",
			leave_type="병가",
			from_date="2026-07-01",
			to_date="2026-07-03",
			total_leave_days=3,
			leave_approver="hr@example.com",
		)
		# 같은 문서 두 번 저장 시뮬레이션
		self.dispatcher_mod.on_leave_application_approve(doc)
		self.dispatcher_mod.on_leave_application_approve(doc)
		# 중복 방지: Comment 는 0개여야 함 (이미 Approved 였으므로 전환 없음)
		self.assertEqual(len(self.fake_frappe._comments), 0)


if __name__ == "__main__":
	unittest.main()
