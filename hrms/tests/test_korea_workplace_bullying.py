"""직장 내 괴롭힘 신고/조사/조치 워크플로우 단위 테스트.

근거 법령:
- 근로기준법 76조의2: 직장 내 괴롭힘 정의
- 근로기준법 76조의3: 사용자 조치 의무
- 산업안전보건법 41조의2: 고객 폭언 등에 대한 조치

Framework-free 코어(workplace_bullying.py)만 테스트합니다.
Frappe 없이 실행 가능합니다:
    python -m unittest hrms.tests.test_korea_workplace_bullying -v
또는 단순히:
    python hrms/tests/test_korea_workplace_bullying.py
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import pathlib
import sys
import unittest

# ---------------------------------------------------------------------------
# 경로 설정: Frappe 없이 workplace_bullying 직접 임포트
# ---------------------------------------------------------------------------

_MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[2]
    / "hrms"
    / "regional"
    / "south_korea"
    / "workplace_bullying.py"
)

spec = importlib.util.spec_from_file_location("workplace_bullying", _MODULE_PATH)
_wb = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(_wb)

# ---------------------------------------------------------------------------
# 테스트 픽스처 헬퍼
# ---------------------------------------------------------------------------

_WORKPLACE = "Winners_Seoul"
_INCIDENT_DATE = dt.date(2026, 4, 1)


def _make_report(**kwargs) -> dict:
    """기본 신고 접수 픽스처."""
    defaults = dict(
        reporter_anonymous=False,
        reporter_name="김피해자",
        reporter_contact="010-1234-5678",
        incident_date=_INCIDENT_DATE,
        incident_location="3층 회의실",
        incident_description="상사가 반복적으로 폭언 및 모욕적 발언을 함",
        alleged_perpetrator="이가해자",
        witnesses=["박증인"],
        evidence_attachments=None,
        workplace=_WORKPLACE,
    )
    defaults.update(kwargs)
    return _wb.create_bullying_report(**defaults)


def _to_investigating(report: dict) -> dict:
    """received → investigating 상태 전이 헬퍼."""
    return _wb.assign_investigator(
        report=report,
        investigator="HR_담당자",
        decided_by="HR_관리자",
        human_approved=True,
    )


def _to_concluded(report: dict, finding: str = "confirmed") -> dict:
    """investigating → concluded 상태 전이 헬퍼."""
    investigating = _to_investigating(report)
    return _wb.submit_investigation_finding(
        report=investigating,
        investigator="HR_담당자",
        finding=finding,
        investigation_notes="조사 결과 폭언 사실 확인됨",
        recommended_actions=["warning", "isolation"],
        decided_by="HR_관리자",
        human_approved=True,
    )


# ---------------------------------------------------------------------------
# 테스트 케이스
# ---------------------------------------------------------------------------


class TestCreateBullyingReport(unittest.TestCase):
    """신고 접수 — 기본 기능"""

    def test_returns_report_with_required_fields(self):
        report = _make_report()
        self.assertIn("report_id", report)
        self.assertTrue(report["report_id"].startswith("BR-"))
        self.assertEqual(report["status"], "received")
        self.assertEqual(report["workplace"], _WORKPLACE)
        self.assertEqual(report["incident_date"], "2026-04-01")
        self.assertIsInstance(report["audit_log"], list)
        self.assertEqual(len(report["audit_log"]), 1)
        self.assertEqual(report["audit_log"][0]["action"], "report_received")

    def test_named_report_stores_reporter_info(self):
        """실명 신고: reporter_name, reporter_contact 정상 저장."""
        report = _make_report(
            reporter_anonymous=False,
            reporter_name="김피해자",
            reporter_contact="010-9999-0000",
        )
        self.assertEqual(report["reporter_name"], "김피해자")
        self.assertEqual(report["reporter_contact"], "010-9999-0000")
        self.assertIsNone(report["reporter_hash"])
        self.assertFalse(report["reporter_anonymous"])

    def test_anonymous_report_omits_name_and_contact(self):
        """익명 신고: reporter_name / reporter_contact 저장 X, hash만 저장."""
        report = _make_report(
            reporter_anonymous=True,
            reporter_name="김피해자",
            reporter_contact="010-9999-0000",
        )
        self.assertIsNone(report["reporter_name"])
        self.assertIsNone(report["reporter_contact"])
        self.assertTrue(report["reporter_anonymous"])
        # hash는 존재해야 함
        self.assertIsNotNone(report["reporter_hash"])
        self.assertIsInstance(report["reporter_hash"], str)
        self.assertEqual(len(report["reporter_hash"]), 64)  # SHA-256 hex

    def test_anonymous_hash_is_deterministic(self):
        """동일 이름/연락처의 익명 신고는 동일 hash를 생성."""
        r1 = _make_report(reporter_anonymous=True, reporter_name="김A", reporter_contact="010-1111-2222")
        r2 = _make_report(reporter_anonymous=True, reporter_name="김A", reporter_contact="010-1111-2222")
        self.assertEqual(r1["reporter_hash"], r2["reporter_hash"])

    def test_anonymous_hash_differs_for_different_identities(self):
        """다른 신원의 익명 신고는 다른 hash."""
        r1 = _make_report(reporter_anonymous=True, reporter_name="김A", reporter_contact="010-1111-0000")
        r2 = _make_report(reporter_anonymous=True, reporter_name="이B", reporter_contact="010-2222-0000")
        self.assertNotEqual(r1["reporter_hash"], r2["reporter_hash"])

    def test_report_ids_are_unique(self):
        """신고마다 고유한 report_id 생성."""
        ids = {_make_report()["report_id"] for _ in range(50)}
        self.assertEqual(len(ids), 50)

    def test_witnesses_and_attachments_stored_as_lists(self):
        report = _make_report(witnesses=["박증인1", "최증인2"], evidence_attachments=["file-001"])
        self.assertEqual(report["witnesses"], ["박증인1", "최증인2"])
        self.assertEqual(report["evidence_attachments"], ["file-001"])

    def test_no_human_approved_required_for_immediate_receipt(self):
        """신고 접수는 human_approved 없이 즉시 처리 가능 — 피해자 보호 원칙."""
        # 예외 없이 성공해야 함
        report = _make_report()
        self.assertIsNotNone(report)

    def test_raises_if_incident_description_empty(self):
        with self.assertRaises(ValueError):
            _make_report(incident_description="")

    def test_raises_if_incident_location_empty(self):
        with self.assertRaises(ValueError):
            _make_report(incident_location="")

    def test_raises_if_workplace_empty(self):
        with self.assertRaises(ValueError):
            _make_report(workplace="")

    def test_raises_if_incident_date_not_date_object(self):
        with self.assertRaises(ValueError):
            _make_report(incident_date="2026-04-01")  # 문자열은 불허


class TestAssignInvestigator(unittest.TestCase):
    """조사관 지정"""

    def setUp(self):
        self.report = _make_report()

    def test_assigns_investigator_and_transitions_status(self):
        updated = _wb.assign_investigator(
            report=self.report,
            investigator="HR_담당자",
            decided_by="HR_관리자",
            human_approved=True,
        )
        self.assertEqual(updated["status"], "investigating")
        self.assertEqual(updated["investigator"], "HR_담당자")
        self.assertIsNotNone(updated["investigator_assigned_at"])
        # 감사 로그 추가 확인
        self.assertEqual(len(updated["audit_log"]), 2)
        self.assertEqual(updated["audit_log"][-1]["action"], "investigator_assigned")

    def test_requires_human_approved(self):
        """human_approved=True 없이는 조사관 지정 불가."""
        with self.assertRaises(ValueError) as ctx:
            _wb.assign_investigator(
                report=self.report,
                investigator="HR_담당자",
                decided_by="HR_관리자",
                human_approved=False,
            )
        self.assertIn("human_approved", str(ctx.exception))

    def test_cannot_assign_from_wrong_status(self):
        """investigating 상태에서 재지정 불가."""
        investigating = _to_investigating(self.report)
        with self.assertRaises(ValueError) as ctx:
            _wb.assign_investigator(
                report=investigating,
                investigator="다른_담당자",
                decided_by="HR_관리자",
                human_approved=True,
            )
        self.assertIn("received", str(ctx.exception))

    def test_original_report_not_mutated(self):
        """원본 report는 변경되지 않아야 함 (불변성)."""
        original_status = self.report["status"]
        _wb.assign_investigator(
            report=self.report,
            investigator="HR_담당자",
            decided_by="HR_관리자",
            human_approved=True,
        )
        self.assertEqual(self.report["status"], original_status)

    def test_raises_if_investigator_empty(self):
        with self.assertRaises(ValueError):
            _wb.assign_investigator(
                report=self.report,
                investigator="",
                decided_by="HR_관리자",
                human_approved=True,
            )


class TestSubmitInvestigationFinding(unittest.TestCase):
    """조사 결과 제출"""

    def setUp(self):
        self.report = _make_report()
        self.investigating = _to_investigating(self.report)

    def test_confirmed_finding_transitions_to_concluded(self):
        concluded = _wb.submit_investigation_finding(
            report=self.investigating,
            investigator="HR_담당자",
            finding="confirmed",
            investigation_notes="폭언 반복 확인됨",
            recommended_actions=["warning", "isolation"],
            decided_by="HR_관리자",
            human_approved=True,
        )
        self.assertEqual(concluded["status"], "concluded")
        self.assertEqual(concluded["finding"], "confirmed")
        self.assertIsNotNone(concluded["finding_submitted_at"])
        self.assertIn("warning", concluded["recommended_actions"])

    def test_unconfirmed_finding_transitions_to_concluded(self):
        concluded = _wb.submit_investigation_finding(
            report=self.investigating,
            investigator="HR_담당자",
            finding="unconfirmed",
            investigation_notes="증거 불충분",
            recommended_actions=[],
            decided_by="HR_관리자",
            human_approved=True,
        )
        self.assertEqual(concluded["status"], "concluded")
        self.assertEqual(concluded["finding"], "unconfirmed")

    def test_not_workplace_bullying_finding(self):
        concluded = _wb.submit_investigation_finding(
            report=self.investigating,
            investigator="HR_담당자",
            finding="not_workplace_bullying",
            investigation_notes="직장 내 괴롭힘 정의에 해당하지 않음 (근기법 76조의2)",
            recommended_actions=[],
            decided_by="HR_관리자",
            human_approved=True,
        )
        self.assertEqual(concluded["finding"], "not_workplace_bullying")

    def test_requires_human_approved(self):
        with self.assertRaises(ValueError) as ctx:
            _wb.submit_investigation_finding(
                report=self.investigating,
                investigator="HR_담당자",
                finding="confirmed",
                investigation_notes="확인됨",
                recommended_actions=[],
                decided_by="HR_관리자",
                human_approved=False,
            )
        self.assertIn("human_approved", str(ctx.exception))

    def test_invalid_finding_raises(self):
        with self.assertRaises(ValueError) as ctx:
            _wb.submit_investigation_finding(
                report=self.investigating,
                investigator="HR_담당자",
                finding="maybe",
                investigation_notes="모르겠음",
                recommended_actions=[],
                decided_by="HR_관리자",
                human_approved=True,
            )
        self.assertIn("finding", str(ctx.exception))

    def test_wrong_investigator_raises(self):
        """지정된 조사관이 아닌 경우 비밀유지 위반으로 거부."""
        with self.assertRaises(ValueError) as ctx:
            _wb.submit_investigation_finding(
                report=self.investigating,
                investigator="무관한_사람",  # 지정된 조사관 아님
                finding="confirmed",
                investigation_notes="확인됨",
                recommended_actions=[],
                decided_by="HR_관리자",
                human_approved=True,
            )
        self.assertIn("비밀유지", str(ctx.exception))

    def test_cannot_submit_from_received_status(self):
        """received 상태에서는 결과 제출 불가 (아직 조사 중이 아님)."""
        with self.assertRaises(ValueError) as ctx:
            _wb.submit_investigation_finding(
                report=self.report,  # received 상태
                investigator="HR_담당자",
                finding="confirmed",
                investigation_notes="확인됨",
                recommended_actions=[],
                decided_by="HR_관리자",
                human_approved=True,
            )
        self.assertIn("investigating", str(ctx.exception))

    def test_audit_log_records_finding(self):
        concluded = _wb.submit_investigation_finding(
            report=self.investigating,
            investigator="HR_담당자",
            finding="confirmed",
            investigation_notes="확인됨",
            recommended_actions=["warning"],
            decided_by="HR_관리자",
            human_approved=True,
        )
        last_log = concluded["audit_log"][-1]
        self.assertEqual(last_log["action"], "finding_submitted")
        self.assertEqual(last_log["details"]["finding"], "confirmed")


class TestApplyProtectiveAction(unittest.TestCase):
    """조치 적용 — 피해자 보호 및 가해자 징계"""

    def setUp(self):
        self.report = _make_report()
        self.concluded = _to_concluded(self.report, finding="confirmed")

    def test_isolation_action_applied_to_victim(self):
        """피해자 분리 조치 — confirmed 없이도 가능."""
        updated = _wb.apply_protective_action(
            report=self.concluded,
            action_type="isolation",
            target_employee="김피해자",
            action_description="가해자와 물리적 분리 조치",
            decided_by="HR_관리자",
            human_approved=True,
        )
        self.assertEqual(len(updated["protective_actions"]), 1)
        action = updated["protective_actions"][0]
        self.assertEqual(action["action_type"], "isolation")
        self.assertEqual(action["target_employee"], "김피해자")
        self.assertIsNotNone(action["applied_at"])
        # 감사 로그 확인
        last_log = updated["audit_log"][-1]
        self.assertEqual(last_log["action"], "protective_action_applied")

    def test_dismissal_allowed_after_confirmed_finding(self):
        """confirmed 판정 후 가해자 해고 가능 (근기법 76조의3 2항)."""
        updated = _wb.apply_protective_action(
            report=self.concluded,  # finding=="confirmed"
            action_type="dismissal",
            target_employee="이가해자",
            action_description="반복적 직장 내 괴롭힘으로 인한 징계해고",
            decided_by="대표이사",
            human_approved=True,
        )
        self.assertEqual(updated["protective_actions"][0]["action_type"], "dismissal")

    def test_suspension_allowed_after_confirmed_finding(self):
        updated = _wb.apply_protective_action(
            report=self.concluded,
            action_type="suspension",
            target_employee="이가해자",
            action_description="30일 정직 처분",
            decided_by="HR_관리자",
            human_approved=True,
        )
        self.assertEqual(updated["protective_actions"][0]["action_type"], "suspension")

    def test_reprimand_blocked_without_confirmed_finding(self):
        """unconfirmed 판정 후 견책 불가 (근기법 76조의3 2항)."""
        unconfirmed_report = _to_concluded(self.report, finding="unconfirmed")
        with self.assertRaises(ValueError) as ctx:
            _wb.apply_protective_action(
                report=unconfirmed_report,
                action_type="reprimand",
                target_employee="이가해자",
                action_description="견책 처분",
                decided_by="HR_관리자",
                human_approved=True,
            )
        self.assertIn("confirmed", str(ctx.exception))

    def test_dismissal_blocked_without_confirmed_finding(self):
        """unconfirmed 상태에서 해고 불가."""
        unconfirmed = _to_concluded(self.report, finding="unconfirmed")
        with self.assertRaises(ValueError) as ctx:
            _wb.apply_protective_action(
                report=unconfirmed,
                action_type="dismissal",
                target_employee="이가해자",
                action_description="해고 시도",
                decided_by="HR_관리자",
                human_approved=True,
            )
        self.assertIn("confirmed", str(ctx.exception))

    def test_requires_human_approved(self):
        with self.assertRaises(ValueError) as ctx:
            _wb.apply_protective_action(
                report=self.concluded,
                action_type="warning",
                target_employee="이가해자",
                action_description="경고 조치",
                decided_by="HR_관리자",
                human_approved=False,
            )
        self.assertIn("human_approved", str(ctx.exception))

    def test_invalid_action_type_raises(self):
        with self.assertRaises(ValueError) as ctx:
            _wb.apply_protective_action(
                report=self.concluded,
                action_type="flogging",  # 존재하지 않는 조치 유형
                target_employee="이가해자",
                action_description="불법 조치",
                decided_by="HR_관리자",
                human_approved=True,
            )
        self.assertIn("action_type", str(ctx.exception))

    def test_cannot_apply_from_received_status(self):
        """received 상태에서는 조치 불가."""
        with self.assertRaises(ValueError) as ctx:
            _wb.apply_protective_action(
                report=self.report,  # received 상태
                action_type="warning",
                target_employee="이가해자",
                action_description="경고",
                decided_by="HR_관리자",
                human_approved=True,
            )
        self.assertIn("investigating", str(ctx.exception))

    def test_multiple_actions_accumulate(self):
        """여러 조치를 순차적으로 적용할 수 있음."""
        updated1 = _wb.apply_protective_action(
            report=self.concluded,
            action_type="isolation",
            target_employee="김피해자",
            action_description="분리 조치",
            decided_by="HR_관리자",
            human_approved=True,
        )
        updated2 = _wb.apply_protective_action(
            report=updated1,
            action_type="warning",
            target_employee="이가해자",
            action_description="경고",
            decided_by="HR_관리자",
            human_approved=True,
        )
        self.assertEqual(len(updated2["protective_actions"]), 2)

    def test_action_during_investigating_status_is_allowed(self):
        """조사 중(investigating) 상태에서도 비징계성 조치 가능 (피해자 긴급 보호)."""
        investigating = _to_investigating(self.report)
        updated = _wb.apply_protective_action(
            report=investigating,
            action_type="isolation",
            target_employee="김피해자",
            action_description="조사 중 임시 분리",
            decided_by="HR_관리자",
            human_approved=True,
        )
        self.assertEqual(updated["protective_actions"][0]["action_type"], "isolation")


class TestConfidentialityAndPII(unittest.TestCase):
    """비밀유지 + PII 마스킹 (근기법 76조의3 4항)"""

    def test_redact_for_non_privileged_viewer_masks_pii(self):
        """일반 직원 열람 시 신고자 정보 마스킹."""
        report = _make_report(reporter_anonymous=False, reporter_name="김피해자", reporter_contact="010-1234-5678")
        redacted = _wb.redact_report_for_viewer(report, viewer_role="staff", viewer_id="박일반")
        self.assertEqual(redacted["reporter_name"], "[REDACTED]")
        self.assertEqual(redacted["reporter_contact"], "[REDACTED]")

    def test_redact_for_assigned_investigator_exposes_pii(self):
        """지정된 조사관은 신고자 정보 접근 가능."""
        report = _make_report(reporter_anonymous=False, reporter_name="김피해자", reporter_contact="010-1234-5678")
        investigating = _to_investigating(report)  # investigator="HR_담당자"
        redacted = _wb.redact_report_for_viewer(
            investigating,
            viewer_role="investigator_assigned",
            viewer_id="HR_담당자",
        )
        self.assertEqual(redacted["reporter_name"], "김피해자")
        self.assertEqual(redacted["reporter_contact"], "010-1234-5678")

    def test_redact_for_different_investigator_masks_pii(self):
        """다른 조사관은 신고자 정보 접근 불가."""
        report = _make_report(reporter_anonymous=False, reporter_name="김피해자")
        investigating = _to_investigating(report)  # investigator="HR_담당자"
        redacted = _wb.redact_report_for_viewer(
            investigating,
            viewer_role="investigator_assigned",
            viewer_id="무관한_조사관",  # 지정 조사관이 아님
        )
        self.assertEqual(redacted["reporter_name"], "[REDACTED]")

    def test_redact_for_hr_admin_exposes_pii(self):
        """HR 관리자는 신고자 정보 접근 가능."""
        report = _make_report(reporter_anonymous=False, reporter_name="김피해자")
        redacted = _wb.redact_report_for_viewer(report, viewer_role="hr_admin", viewer_id="인사팀장")
        self.assertEqual(redacted["reporter_name"], "김피해자")

    def test_anonymous_report_never_exposes_name(self):
        """익명 신고는 관리자도 원본 이름 조회 불가 (None이므로 REDACTED도 None)."""
        report = _make_report(reporter_anonymous=True, reporter_name="김피해자", reporter_contact="010-1234-5678")
        # 익명 신고에서 reporter_name 자체가 None으로 저장됨
        self.assertIsNone(report["reporter_name"])
        self.assertIsNone(report["reporter_contact"])
        # 해시는 저장됨
        self.assertIsNotNone(report["reporter_hash"])

    def test_confidentiality_violation_wrong_investigator_raises(self):
        """지정 조사관이 아닌 사람이 조사 결과를 제출하려 할 때 거부 — 비밀유지 위반."""
        report = _make_report()
        investigating = _to_investigating(report)  # investigator="HR_담당자"
        with self.assertRaises(ValueError) as ctx:
            _wb.submit_investigation_finding(
                report=investigating,
                investigator="불법접근자",  # 지정된 조사관 아님
                finding="confirmed",
                investigation_notes="무단 접근 시도",
                recommended_actions=[],
                decided_by="불법접근자",
                human_approved=True,
            )
        self.assertIn("비밀유지", str(ctx.exception))

    def test_redact_does_not_mutate_original(self):
        """redact_report_for_viewer는 원본 report를 변경하지 않아야 함."""
        report = _make_report(reporter_anonymous=False, reporter_name="김피해자")
        _ = _wb.redact_report_for_viewer(report, viewer_role="staff")
        self.assertEqual(report["reporter_name"], "김피해자")


class TestGetBullyingDashboard(unittest.TestCase):
    """관리자 대시보드 — 집계 데이터"""

    def _make_reports(self) -> list[dict]:
        """다양한 상태의 보고서 픽스처."""
        reports = []
        # 신고 1: confirmed + 조치 있음
        r1 = _to_concluded(_make_report(), finding="confirmed")
        r1 = _wb.apply_protective_action(
            report=r1, action_type="warning", target_employee="이가해자",
            action_description="경고", decided_by="HR", human_approved=True,
        )
        reports.append(r1)

        # 신고 2: unconfirmed
        r2 = _to_concluded(_make_report(), finding="unconfirmed")
        reports.append(r2)

        # 신고 3: investigating 상태
        r3 = _to_investigating(_make_report())
        reports.append(r3)

        # 신고 4: received 상태
        r4 = _make_report()
        reports.append(r4)

        # 신고 5: 다른 workplace (필터링되어야 함)
        r5 = _make_report(workplace="Other_Company")
        reports.append(r5)

        return reports

    def test_dashboard_returns_correct_totals(self):
        reports = self._make_reports()
        result = _wb.get_bullying_dashboard(
            reports=reports,
            workplace=_WORKPLACE,
            period_start=dt.date(2026, 1, 1),
            period_end=dt.date(2026, 12, 31),
        )
        # 5개 중 4개만 _WORKPLACE 소속
        self.assertEqual(result["total_reports"], 4)

    def test_dashboard_status_distribution(self):
        reports = self._make_reports()
        result = _wb.get_bullying_dashboard(
            reports=reports,
            workplace=_WORKPLACE,
            period_start=dt.date(2026, 1, 1),
            period_end=dt.date(2026, 12, 31),
        )
        dist = result["status_distribution"]
        self.assertEqual(dist["received"], 1)
        self.assertEqual(dist["investigating"], 1)
        self.assertEqual(dist["concluded"], 2)
        self.assertEqual(dist["closed"], 0)

    def test_dashboard_finding_distribution(self):
        reports = self._make_reports()
        result = _wb.get_bullying_dashboard(
            reports=reports,
            workplace=_WORKPLACE,
            period_start=dt.date(2026, 1, 1),
            period_end=dt.date(2026, 12, 31),
        )
        findings = result["finding_distribution"]
        self.assertEqual(findings.get("confirmed", 0), 1)
        self.assertEqual(findings.get("unconfirmed", 0), 1)

    def test_dashboard_action_type_distribution(self):
        reports = self._make_reports()
        result = _wb.get_bullying_dashboard(
            reports=reports,
            workplace=_WORKPLACE,
            period_start=dt.date(2026, 1, 1),
            period_end=dt.date(2026, 12, 31),
        )
        actions = result["action_type_distribution"]
        self.assertEqual(actions.get("warning", 0), 1)

    def test_dashboard_contains_no_pii(self):
        """대시보드 반환값에 개인 식별 정보(report_id 포함)가 없어야 함."""
        reports = self._make_reports()
        result = _wb.get_bullying_dashboard(
            reports=reports,
            workplace=_WORKPLACE,
            period_start=dt.date(2026, 1, 1),
            period_end=dt.date(2026, 12, 31),
        )
        result_str = str(result)
        # report_id는 대시보드에 없어야 함
        for r in reports[:4]:
            self.assertNotIn(r["report_id"], result_str)
        # reporter_name 등 PII 없어야 함
        self.assertNotIn("reporter_name", result_str)
        self.assertNotIn("reporter_contact", result_str)

    def test_dashboard_period_filter_excludes_out_of_range(self):
        """기간 외 신고는 집계에서 제외."""
        reports = self._make_reports()
        result = _wb.get_bullying_dashboard(
            reports=reports,
            workplace=_WORKPLACE,
            period_start=dt.date(2099, 1, 1),  # 미래 기간
            period_end=dt.date(2099, 12, 31),
        )
        self.assertEqual(result["total_reports"], 0)

    def test_dashboard_raises_if_period_end_before_start(self):
        with self.assertRaises(ValueError):
            _wb.get_bullying_dashboard(
                reports=[],
                workplace=_WORKPLACE,
                period_start=dt.date(2026, 12, 31),
                period_end=dt.date(2026, 1, 1),
            )

    def test_avg_resolution_days_is_none_for_open_reports(self):
        """결론 미도달 신고만 있으면 평균 처리 기간 None."""
        reports = [_make_report(), _to_investigating(_make_report())]
        result = _wb.get_bullying_dashboard(
            reports=reports,
            workplace=_WORKPLACE,
            period_start=dt.date(2026, 1, 1),
            period_end=dt.date(2026, 12, 31),
        )
        self.assertIsNone(result["avg_resolution_days"])


class TestFullWorkflow(unittest.TestCase):
    """엔드-투-엔드 워크플로우 통합 테스트"""

    def test_full_workflow_anonymous_report_to_dismissal(self):
        """익명 신고 → 조사관 지정 → confirmed → 해고 조치 전체 흐름."""
        # 1. 익명 신고
        report = _make_report(
            reporter_anonymous=True,
            reporter_name="김피해자",
            reporter_contact="010-0000-1111",
        )
        self.assertIsNone(report["reporter_name"])
        self.assertIsNone(report["reporter_contact"])
        self.assertEqual(report["status"], "received")

        # 2. 조사관 지정 (human_approved 필수)
        investigating = _wb.assign_investigator(
            report=report,
            investigator="외부_조사위원",
            decided_by="대표이사",
            human_approved=True,
        )
        self.assertEqual(investigating["status"], "investigating")

        # 3. 조사 결과 제출 (confirmed)
        concluded = _wb.submit_investigation_finding(
            report=investigating,
            investigator="외부_조사위원",
            finding="confirmed",
            investigation_notes="반복적 폭언 및 모욕 행위 확인. 목격자 진술 일치.",
            recommended_actions=["isolation", "reprimand"],
            decided_by="외부_조사위원",
            human_approved=True,
        )
        self.assertEqual(concluded["status"], "concluded")
        self.assertEqual(concluded["finding"], "confirmed")

        # 4. 피해자 보호 조치 — 분리
        protected = _wb.apply_protective_action(
            report=concluded,
            action_type="isolation",
            target_employee="이가해자",
            action_description="즉시 피해자와 물리적 분리",
            decided_by="HR_관리자",
            human_approved=True,
        )
        self.assertEqual(len(protected["protective_actions"]), 1)

        # 5. 가해자 징계 — 해고 (confirmed이므로 가능)
        final = _wb.apply_protective_action(
            report=protected,
            action_type="dismissal",
            target_employee="이가해자",
            action_description="반복적 직장 내 괴롭힘 — 징계해고 (근기법 76조의3 2항)",
            decided_by="대표이사",
            human_approved=True,
        )
        self.assertEqual(len(final["protective_actions"]), 2)
        self.assertEqual(final["protective_actions"][1]["action_type"], "dismissal")

        # 감사 로그: create + assign + finding + action×2 = 5개
        self.assertEqual(len(final["audit_log"]), 5)

    def test_full_workflow_named_report_no_action(self):
        """실명 신고 → 조사 → not_workplace_bullying → no_action 흐름."""
        report = _make_report(reporter_anonymous=False, reporter_name="박신고자")
        self.assertEqual(report["reporter_name"], "박신고자")

        investigating = _to_investigating(report)
        concluded = _wb.submit_investigation_finding(
            report=investigating,
            investigator="HR_담당자",
            finding="not_workplace_bullying",
            investigation_notes="업무상 정당한 지시로 판단됨 (근기법 76조의2)",
            recommended_actions=["no_action"],
            decided_by="HR_관리자",
            human_approved=True,
        )
        self.assertEqual(concluded["finding"], "not_workplace_bullying")

        # no_action 조치 적용
        final = _wb.apply_protective_action(
            report=concluded,
            action_type="no_action",
            target_employee="피신고인",
            action_description="조사 결과 조치 없음",
            decided_by="HR_관리자",
            human_approved=True,
        )
        self.assertEqual(final["protective_actions"][0]["action_type"], "no_action")


if __name__ == "__main__":
    unittest.main(verbosity=2)
