"""산재 발생 신고 workflow 테스트.

프레임워크 독립 — frappe 없이 pytest로 직접 실행 가능.
대상 모듈: hrms/regional/south_korea/industrial_accident.py

실행:
    pytest hrms/tests/test_korea_industrial_accident.py -v

주의: hrms/__init__.py 가 import frappe를 수행하므로 패키지를 통한 일반적 import는
Frappe 런타임 없이 불가능합니다. importlib를 사용해 hrms 패키지 __init__ 를 우회하고
industrial_accident.py 모듈을 직접 로드합니다.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import sys
import types
from pathlib import Path

import pytest

# ── frappe stub — import 순환 방지 ──────────────────────────────────────────
# hrms.regional.south_korea.industrial_accident 는 frappe 미사용 (framework-free).
# 그러나 Python이 패키지를 해석할 때 hrms/__init__.py → import frappe 를 실행하므로
# 더미 frappe 모듈을 sys.modules에 먼저 등록해 충돌을 방지합니다.
if "frappe" not in sys.modules:
    _frappe_stub = types.ModuleType("frappe")
    sys.modules["frappe"] = _frappe_stub

# hrms 패키지를 빈 네임스페이스로 등록 (실제 __init__ 실행 방지)
_ROOT = Path(__file__).resolve().parent.parent.parent
if "hrms" not in sys.modules:
    _hrms_stub = types.ModuleType("hrms")
    _hrms_stub.__path__ = [str(_ROOT / "hrms")]
    _hrms_stub.__package__ = "hrms"
    sys.modules["hrms"] = _hrms_stub

# 중간 패키지도 등록
for _pkg in ("hrms.regional", "hrms.regional.south_korea"):
    if _pkg not in sys.modules:
        _parts = _pkg.split(".")
        _mod = types.ModuleType(_pkg)
        _mod.__path__ = [str(_ROOT.joinpath(*_parts))]
        _mod.__package__ = _pkg
        sys.modules[_pkg] = _mod

# industrial_accident.py 직접 로드
_MODULE_PATH = _ROOT / "hrms" / "regional" / "south_korea" / "industrial_accident.py"
_spec = importlib.util.spec_from_file_location(
    "hrms.regional.south_korea.industrial_accident",
    _MODULE_PATH,
)
_ia_module = importlib.util.module_from_spec(_spec)
sys.modules["hrms.regional.south_korea.industrial_accident"] = _ia_module
_spec.loader.exec_module(_ia_module)

CONTRACT_TYPE = _ia_module.CONTRACT_TYPE
FORM_TYPE_ACCIDENT = _ia_module.FORM_TYPE_ACCIDENT
FORM_TYPE_CRITICAL = _ia_module.FORM_TYPE_CRITICAL
create_accident_report = _ia_module.create_accident_report
generate_accident_report_pdf_payload = _ia_module.generate_accident_report_pdf_payload
list_pending_reports = _ia_module.list_pending_reports
submit_to_workers_compensation_corp = _ia_module.submit_to_workers_compensation_corp

# ── 공통 픽스처 ────────────────────────────────────────────────────────────────

_BASE_DATETIME = dt.datetime(2026, 3, 15, 9, 30, 0)
_BASE_WORKPLACE = "테스트 사업장"


def _make_report(**overrides):
    """기본 산재 보고서 생성 헬퍼."""
    defaults = dict(
        employee="홍길동",
        incident_datetime=_BASE_DATETIME,
        incident_location="3층 작업실",
        incident_description="고소 작업 중 발판이 미끄러져 추락",
        injury_type="추락",
        affected_body_part="허리/척추",
        expected_treatment_days=7,
        witnesses=["이영희", "김철수"],
        initial_treatment="응급실 내원 후 X선 촬영",
        workplace=_BASE_WORKPLACE,
        human_approved=False,
    )
    defaults.update(overrides)
    return create_accident_report(**defaults)


# ── 1. 분류 로직 테스트 ────────────────────────────────────────────────────────

class TestClassification:
    """산재 보고 자동 분류 로직."""

    def test_4_days_or_more_requires_report(self):
        """요양 4일 이상 → 신고 필수 (산재발생신고서)."""
        for days in [4, 5, 14, 30, 90]:
            report = _make_report(expected_treatment_days=days, injury_type="낙상")
            assert report["applies_report_obligation"] is True, f"days={days} must require report"
            assert report["report_type"] == "serious"
            assert report["report_form_type"] == FORM_TYPE_ACCIDENT

    def test_less_than_4_days_no_report_obligation(self):
        """요양 3일 미만 → 신고 불필요 (자체 처리)."""
        for days in [0, 1, 2, 3]:
            report = _make_report(expected_treatment_days=days, injury_type="자상")
            assert report["applies_report_obligation"] is False, f"days={days} must NOT require report"
            assert report["report_type"] == "minor"
            assert report["report_form_type"] is None
            assert report["report_deadline"] is None

    def test_exactly_3_days_no_obligation(self):
        """정확히 3일 → 신고 불필요 (경계 케이스)."""
        report = _make_report(expected_treatment_days=3, injury_type="타박상")
        assert report["applies_report_obligation"] is False
        assert report["report_type"] == "minor"

    def test_exactly_4_days_requires_report(self):
        """정확히 4일 → 신고 필수 (경계 케이스)."""
        report = _make_report(expected_treatment_days=4, injury_type="골절")
        assert report["applies_report_obligation"] is True
        assert report["report_type"] == "serious"

    def test_fatal_injury_requires_immediate_report(self):
        """사망 → 즉시 신고 (중대재해보고서), 기대일수 무관."""
        report = _make_report(
            expected_treatment_days=0,
            injury_type="사망",
        )
        assert report["applies_report_obligation"] is True
        assert report["report_type"] == "fatal"
        assert report["report_form_type"] == FORM_TYPE_CRITICAL

    def test_fatal_overrides_treatment_days(self):
        """사망 시 요양일수 < 4일이라도 즉시 신고."""
        report = _make_report(expected_treatment_days=1, injury_type="사망")
        assert report["report_type"] == "fatal"
        assert report["applies_report_obligation"] is True

    def test_fatal_deadline_is_incident_date(self):
        """사망 사고의 신고 기한은 발생일 당일."""
        report = _make_report(injury_type="사망")
        assert report["report_deadline"] == _BASE_DATETIME.date().isoformat()

    def test_serious_deadline_is_one_month_later(self):
        """4일 이상 요양 → 신고 기한은 발생일로부터 1개월 후."""
        incident = dt.datetime(2026, 3, 15, 10, 0)
        report = create_accident_report(
            employee="박영희",
            incident_datetime=incident,
            incident_location="창고",
            incident_description="물건 낙하",
            injury_type="타박상",
            affected_body_part="어깨",
            expected_treatment_days=7,
            witnesses=None,
            initial_treatment="냉찜질",
            workplace="테스트",
        )
        assert report["report_deadline"] == "2026-04-15"

    def test_serious_deadline_month_end_boundary(self):
        """1월 31일 → 마감일은 2월 28일 (월말 경계)."""
        incident = dt.datetime(2026, 1, 31, 8, 0)
        report = create_accident_report(
            employee="최강자",
            incident_datetime=incident,
            incident_location="공장",
            incident_description="기계 끼임",
            injury_type="절단",
            affected_body_part="손가락",
            expected_treatment_days=10,
            witnesses=None,
            initial_treatment="응급 처치",
            workplace="공장A",
        )
        assert report["report_deadline"] == "2026-02-28"


# ── 2. 계약 타입 및 구조 테스트 ───────────────────────────────────────────────

class TestReportStructure:
    """보고서 반환 구조 검증."""

    def test_contract_type_is_correct(self):
        """contract_type 값 검증."""
        report = _make_report()
        assert report["contract_type"] == CONTRACT_TYPE

    def test_report_payload_contains_required_fields(self):
        """report_payload에 필수 필드 모두 포함."""
        report = _make_report()
        payload = report["report_payload"]
        required = {
            "employee", "incident_datetime", "incident_location",
            "incident_description", "injury_type", "affected_body_part",
            "expected_treatment_days", "witnesses", "initial_treatment",
            "workplace",
        }
        for field in required:
            assert field in payload, f"report_payload에 '{field}' 없음"

    def test_human_approved_echoed(self):
        """human_approved 값이 반환에 반영됨."""
        report_false = _make_report(human_approved=False)
        report_true = _make_report(human_approved=True)
        assert report_false["human_approved"] is False
        assert report_true["human_approved"] is True

    def test_witnesses_none_becomes_empty_list(self):
        """witnesses=None → payload에서 빈 리스트로."""
        report = _make_report(witnesses=None)
        assert report["report_payload"]["witnesses"] == []

    def test_witnesses_preserved(self):
        """목격자 리스트 그대로 보존."""
        witnesses = ["이영희", "김철수"]
        report = _make_report(witnesses=witnesses)
        assert report["report_payload"]["witnesses"] == witnesses


# ── 3. PDF payload 테스트 ─────────────────────────────────────────────────────

class TestPdfPayload:
    """generate_accident_report_pdf_payload() 검증."""

    def test_pdf_payload_has_all_required_fields(self):
        """PDF payload 필드 완전성."""
        report = _make_report()
        pdf = generate_accident_report_pdf_payload(report)

        assert pdf["pdf_template"] == "korea_industrial_accident_report"
        assert "fields" in pdf
        fields = pdf["fields"]

        required_keys = {
            "사업장명", "사업장소재지", "사업자등록번호",
            "재해자성명", "재해발생일시", "재해발생장소",
            "재해발생경위", "상해종류", "상해부위",
            "요양예상일수", "목격자", "초기치료내용",
            "보고서유형", "신고의무여부", "신고기한",
        }
        for key in required_keys:
            assert key in fields, f"PDF fields에 '{key}' 없음"

    def test_pdf_payload_values_match_input(self):
        """PDF payload 값이 입력과 일치 (round-trip)."""
        report = _make_report(
            employee="홍길동",
            injury_type="낙상",
            affected_body_part="발목",
            expected_treatment_days=7,
            witnesses=["이영희"],
        )
        pdf = generate_accident_report_pdf_payload(report)
        fields = pdf["fields"]

        assert fields["재해자성명"] == "홍길동"
        assert fields["상해종류"] == "낙상"
        assert fields["상해부위"] == "발목"
        assert fields["요양예상일수"] == "7"
        assert fields["목격자"] == "이영희"

    def test_pdf_payload_no_witnesses(self):
        """목격자 없을 때 '없음' 표시."""
        report = _make_report(witnesses=[])
        pdf = generate_accident_report_pdf_payload(report)
        assert pdf["fields"]["목격자"] == "없음"

    def test_pdf_payload_fatal_form_type(self):
        """사망 사고 → 중대재해보고서 PDF."""
        report = _make_report(injury_type="사망")
        pdf = generate_accident_report_pdf_payload(report)
        assert pdf["form_type"] == FORM_TYPE_CRITICAL
        assert pdf["fields"]["보고서유형"] == FORM_TYPE_CRITICAL

    def test_pdf_payload_serious_obligation_is_yes(self):
        """신고 의무 있는 경우 → '예'."""
        report = _make_report(expected_treatment_days=7)
        pdf = generate_accident_report_pdf_payload(report)
        assert pdf["fields"]["신고의무여부"] == "예"

    def test_pdf_payload_minor_obligation_is_no(self):
        """신고 의무 없는 경우 → '아니오'."""
        report = _make_report(expected_treatment_days=2)
        pdf = generate_accident_report_pdf_payload(report)
        assert pdf["fields"]["신고의무여부"] == "아니오"
        assert pdf["fields"]["신고기한"] == "해당없음"

    def test_pdf_payload_invalid_contract_type_raises(self):
        """잘못된 contract_type → ValueError."""
        with pytest.raises(ValueError, match="contract_type"):
            generate_accident_report_pdf_payload({"contract_type": "wrong_v99"})

    def test_pdf_payload_requires_dict(self):
        """report가 dict가 아닌 경우 → ValueError."""
        with pytest.raises(ValueError):
            generate_accident_report_pdf_payload("not_a_dict")


# ── 4. 제출 게이트 테스트 ────────────────────────────────────────────────────

class TestSubmit:
    """submit_to_workers_compensation_corp() 게이트 검증."""

    def test_submit_refuses_without_human_approved(self):
        """human_approved=False → PermissionError."""
        report = _make_report(expected_treatment_days=7)
        with pytest.raises(PermissionError, match="human_approved"):
            submit_to_workers_compensation_corp(
                report=report,
                human_approved=False,
                dry_run=True,
            )

    def test_submit_dry_run_with_approval(self):
        """human_approved=True + dry_run=True → 'dry_run' 상태 반환."""
        report = _make_report(expected_treatment_days=7, human_approved=True)
        result = submit_to_workers_compensation_corp(
            report=report,
            human_approved=True,
            dry_run=True,
        )
        assert result["status"] == "dry_run"
        assert result["payload_sent"] is not None

    def test_submit_refused_if_no_obligation(self):
        """신고 의무 없음 → 'refused' 상태 반환."""
        report = _make_report(expected_treatment_days=2, human_approved=True)
        result = submit_to_workers_compensation_corp(
            report=report,
            human_approved=True,
            dry_run=True,
        )
        assert result["status"] == "refused"
        assert "신고 의무 없음" in result["reason"]

    def test_submit_real_raises_not_implemented(self):
        """dry_run=False → NotImplementedError (v1 미구현)."""
        report = _make_report(expected_treatment_days=7, human_approved=True)
        with pytest.raises(NotImplementedError):
            submit_to_workers_compensation_corp(
                report=report,
                human_approved=True,
                dry_run=False,
            )

    def test_submit_invalid_contract_type_raises(self):
        """잘못된 contract_type → ValueError."""
        with pytest.raises(ValueError, match="contract_type"):
            submit_to_workers_compensation_corp(
                report={"contract_type": "bad_v99"},
                human_approved=True,
                dry_run=True,
            )


# ── 5. 입력 검증 테스트 ──────────────────────────────────────────────────────

class TestInputValidation:
    """create_accident_report() 입력 검증."""

    def test_empty_employee_raises(self):
        with pytest.raises(ValueError, match="employee"):
            _make_report(employee="")

    def test_negative_treatment_days_raises(self):
        with pytest.raises(ValueError, match="expected_treatment_days"):
            _make_report(expected_treatment_days=-1)

    def test_non_datetime_raises(self):
        with pytest.raises((ValueError, TypeError)):
            _make_report(incident_datetime="2026-03-15")  # str는 불가

    def test_zero_treatment_days_is_valid(self):
        """0일 → minor, 정상 동작."""
        report = _make_report(expected_treatment_days=0)
        assert report["report_type"] == "minor"
        assert report["applies_report_obligation"] is False


# ── 6. list_pending_reports 테스트 ───────────────────────────────────────────

class TestListPendingReports:
    """list_pending_reports() 필터링 및 정렬 검증."""

    def _make_serious_report(self, incident_date: dt.date, workplace: str = _BASE_WORKPLACE):
        """신고 필수 보고서 생성 헬퍼."""
        return _make_report(
            incident_datetime=dt.datetime.combine(incident_date, dt.time(9, 0)),
            workplace=workplace,
            expected_treatment_days=7,
        )

    def test_filters_by_workplace(self):
        """사업장 필터 동작."""
        r1 = self._make_serious_report(dt.date(2026, 3, 1), workplace="A사업장")
        r2 = self._make_serious_report(dt.date(2026, 3, 10), workplace="B사업장")

        result = list_pending_reports(
            workplace="A사업장",
            as_of_date=dt.date(2026, 3, 15),
            reports=[r1, r2],
        )
        assert len(result) == 1
        assert result[0]["report_payload"]["workplace"] == "A사업장"

    def test_excludes_minor_reports(self):
        """신고 의무 없는 경미 사고는 목록에서 제외."""
        minor = _make_report(expected_treatment_days=2)
        serious = _make_report(expected_treatment_days=7)

        result = list_pending_reports(
            workplace=_BASE_WORKPLACE,
            as_of_date=dt.date(2026, 3, 15),
            reports=[minor, serious],
        )
        assert all(r["applies_report_obligation"] for r in result)
        assert len(result) == 1

    def test_days_until_deadline_calculated(self):
        """days_until_deadline 올바르게 계산."""
        incident = dt.date(2026, 3, 1)
        report = self._make_serious_report(incident)
        # deadline = 2026-04-01
        as_of = dt.date(2026, 3, 25)

        result = list_pending_reports(
            workplace=_BASE_WORKPLACE,
            as_of_date=as_of,
            reports=[report],
        )
        assert len(result) == 1
        assert result[0]["days_until_deadline"] == (dt.date(2026, 4, 1) - as_of).days

    def test_overdue_flag(self):
        """마감일 지난 경우 overdue=True."""
        report = self._make_serious_report(dt.date(2026, 1, 1))
        # deadline = 2026-02-01, as_of = 2026-03-01 (마감 후)

        result = list_pending_reports(
            workplace=_BASE_WORKPLACE,
            as_of_date=dt.date(2026, 3, 1),
            reports=[report],
        )
        assert len(result) == 1
        assert result[0]["overdue"] is True

    def test_sorted_by_deadline(self):
        """마감일 임박순 정렬."""
        r_later = self._make_serious_report(dt.date(2026, 3, 10))   # deadline ~2026-04-10
        r_earlier = self._make_serious_report(dt.date(2026, 2, 20)) # deadline ~2026-03-20

        result = list_pending_reports(
            workplace=_BASE_WORKPLACE,
            as_of_date=dt.date(2026, 3, 1),
            reports=[r_later, r_earlier],
        )
        # 빠른 마감일이 먼저
        assert result[0]["report_deadline"] < result[1]["report_deadline"]

    def test_empty_reports_returns_empty(self):
        """빈 보고서 목록 → 빈 결과."""
        result = list_pending_reports(
            workplace=_BASE_WORKPLACE,
            as_of_date=dt.date(2026, 3, 15),
            reports=[],
        )
        assert result == []


# ── 7. 통합 시나리오 ─────────────────────────────────────────────────────────

class TestIntegrationScenarios:
    """실제 운영 시나리오 통합 테스트."""

    def test_full_serious_accident_workflow(self):
        """4일 이상 요양 사고 전체 흐름: 생성 → PDF → 제출(dry_run)."""
        # 1. 보고서 생성
        report = create_accident_report(
            employee="이철민",
            incident_datetime=dt.datetime(2026, 5, 10, 14, 30),
            incident_location="2층 생산라인",
            incident_description="프레스 기계 조작 중 손가락 끼임",
            injury_type="절단",
            affected_body_part="오른손 검지",
            expected_treatment_days=21,
            witnesses=["박대리"],
            initial_treatment="응급실 이송 및 접합 수술",
            workplace="위너스 공장",
        )

        assert report["report_type"] == "serious"
        assert report["applies_report_obligation"] is True
        assert report["report_form_type"] == FORM_TYPE_ACCIDENT
        assert report["report_deadline"] == "2026-06-10"

        # 2. PDF payload 생성
        pdf = generate_accident_report_pdf_payload(report)
        assert pdf["fields"]["재해자성명"] == "이철민"
        assert pdf["fields"]["신고의무여부"] == "예"

        # 3. 승인 없이 제출 시도 → 거부
        with pytest.raises(PermissionError):
            submit_to_workers_compensation_corp(
                report=report, human_approved=False, dry_run=True
            )

        # 4. 승인 후 dry_run 제출
        result = submit_to_workers_compensation_corp(
            report=report, human_approved=True, dry_run=True
        )
        assert result["status"] == "dry_run"
        assert result["payload_sent"]["fields"]["재해자성명"] == "이철민"

    def test_full_fatal_accident_workflow(self):
        """사망 사고 전체 흐름: 즉시 신고, 중대재해보고서."""
        incident = dt.datetime(2026, 4, 20, 7, 0)
        report = create_accident_report(
            employee="김건설",
            incident_datetime=incident,
            incident_location="지하 1층 굴착 현장",
            incident_description="굴착 중 지반 붕괴로 작업자 매몰",
            injury_type="사망",
            affected_body_part="전신",
            expected_treatment_days=0,
            witnesses=None,
            initial_treatment="현장 응급 처치 후 병원 이송",
            workplace="건설현장B",
        )

        assert report["report_type"] == "fatal"
        assert report["report_form_type"] == FORM_TYPE_CRITICAL
        assert report["report_deadline"] == "2026-04-20"

        pdf = generate_accident_report_pdf_payload(report)
        assert pdf["form_type"] == FORM_TYPE_CRITICAL
        assert pdf["fields"]["보고서유형"] == FORM_TYPE_CRITICAL
        assert pdf["fields"]["신고기한"] == "2026-04-20"

    def test_full_minor_accident_workflow(self):
        """경미 사고(3일 미만): 신고 불필요, 제출 거부."""
        report = create_accident_report(
            employee="정민수",
            incident_datetime=dt.datetime(2026, 5, 1, 11, 0),
            incident_location="주방",
            incident_description="칼 사용 중 손 베임",
            injury_type="자상",
            affected_body_part="왼손 엄지",
            expected_treatment_days=2,
            witnesses=[],
            initial_treatment="지혈 및 응급 처치",
            workplace="레스토랑C",
        )

        assert report["report_type"] == "minor"
        assert report["applies_report_obligation"] is False
        assert report["report_deadline"] is None

        result = submit_to_workers_compensation_corp(
            report=report, human_approved=True, dry_run=True
        )
        assert result["status"] == "refused"
