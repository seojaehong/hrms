"""근로기준법 56조 가산수당 계산기 테스트.

테스트 범위:
    - 일 8h 정시 (regular=8, overtime=0, night=0)
    - 일 10h 연장 (regular=8, overtime=2)
    - 일 12h 연장+야간 (regular=8, overtime=4, night 일부)
    - 야간전담 22:00~06:00 (regular=8, night=8)
    - 휴일 8h 이내 (holiday=8, holiday_overtime=0)
    - 휴일 12h (holiday=8, holiday_overtime=4)
    - 휴일 야간 12h (holiday + night + holiday_overtime 중첩)
    - 주 단위 §53 한도 검증 (정확히 12h / 초과)
    - 금액 추정 (통상시급 10000원 기준)

버킷 규칙:
    - 휴일: overtime 버킷 0, holiday + holiday_overtime 사용
    - 비휴일: regular + overtime 버킷 사용
    - 야간(night): 독립 오버레이, 22:00~익일06:00 교차

주 단위 연장 케이스 설계:
    "주 60h" = 월~금 각 12h (9:00~22:00, 점심60분 = 실12h)
        → 일 regular=8, overtime=4 → 주 overtime=20h (한도 12h 초과)
        ※ 명세의 "weekly_overtime=12" 설명은 불정확. §53 기준 정확히 계산.

    "주 정확히 12h 연장" = 월~금 각 10.4h (9:00~20:24, 점심60분 = 실 9.4h)
        → 일 overtime=1.4h × 5 = 7h (한도 미만)
        → 또는 월~수 각 12h = overtime=4×3=12h 정확히 한도 도달

    "주 17h 연장" = 월~금 각 13h (9:00~23:00, 점심60분 = 실 13h)
        → 일 overtime=5h × 5 = 25h? → 실무상 주 상한 달성 후 분류 필요.
        ※ §53은 회사의 준수 의무이고 계산기는 결과를 알려주는 것이므로
           실제 발생한 시간 그대로 집계 후 한도 초과 경고를 반환.
        ※ 명세의 "weekly_overtime=17"은 아래 케이스로 구현:
           월~목 각 12h (overtime=4×4=16h), 금 9h (overtime=1h) → 총 17h
"""

import datetime as dt
import importlib.util
import pathlib
import sys
import types
import unittest

# framework-free: overtime_premium.py는 frappe import 없음.
# hrms/__init__.py가 frappe를 import하므로 spec_from_file_location으로 직접 로드.
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "hrms" / "regional" / "south_korea" / "overtime_premium.py"

_spec = importlib.util.spec_from_file_location("overtime_premium", _MODULE_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

# 편의상 네임스페이스에서 꺼내기
WEEKLY_OVERTIME_LIMIT_HOURS = _mod.WEEKLY_OVERTIME_LIMIT_HOURS
WorkSession = _mod.WorkSession
calculate_daily_premium = _mod.calculate_daily_premium
calculate_weekly_aggregate = _mod.calculate_weekly_aggregate
estimate_premium_amount = _mod.estimate_premium_amount


def _session(
    start: str,
    end: str,
    date_str: str = "2025-01-06",  # 월요일
    break_minutes: int = 60,
    is_holiday: bool = False,
    is_weekly_off: bool = False,
    employee: str = "EMP-001",
) -> WorkSession:
    """테스트용 WorkSession 헬퍼."""
    work_date = dt.date.fromisoformat(date_str)
    start_time = dt.time.fromisoformat(start)
    end_time = dt.time.fromisoformat(end)
    return WorkSession(
        employee=employee,
        work_date=work_date,
        start_time=start_time,
        end_time=end_time,
        break_minutes=break_minutes,
        is_holiday=is_holiday,
        is_weekly_off=is_weekly_off,
    )


def _daily(session: WorkSession) -> dict:
    return calculate_daily_premium(session)


class TestWorkSessionClock(unittest.TestCase):
    """WorkSession 기본 시간 계산."""

    def test_same_day_clock(self):
        s = _session("09:00", "18:00", break_minutes=60)
        # 클럭 9h, 휴게 1h → 실 8h
        self.assertEqual(s.total_clock_minutes(), 9 * 60)
        self.assertEqual(s.total_work_minutes(), 8 * 60)

    def test_midnight_crossover(self):
        # 22:00 ~ 06:00 → 익일 처리
        s = _session("22:00", "06:00", break_minutes=0)
        self.assertEqual(s.total_clock_minutes(), 8 * 60)

    def test_midnight_crossover_with_break(self):
        s = _session("22:00", "06:00", break_minutes=30)
        self.assertEqual(s.total_work_minutes(), 7 * 60 + 30)


class TestDailyPremiumRegularDay(unittest.TestCase):
    """비휴일 가산수당 분류."""

    def test_regular_8h_no_overtime_no_night(self):
        """9:00~18:00 (점심1h) = 실8h → regular=8, overtime=0, night=0."""
        s = _session("09:00", "18:00", break_minutes=60)
        d = _daily(s)
        self.assertAlmostEqual(d["regular_hours"], 8.0)
        self.assertAlmostEqual(d["overtime_hours"], 0.0)
        self.assertAlmostEqual(d["night_hours"], 0.0)
        self.assertAlmostEqual(d["holiday_hours"], 0.0)
        self.assertAlmostEqual(d["holiday_overtime_hours"], 0.0)
        self.assertAlmostEqual(d["total_work_hours"], 8.0)
        self.assertFalse(d["is_holiday"])

    def test_overtime_10h(self):
        """9:00~20:00 (점심1h) = 실10h → regular=8, overtime=2."""
        s = _session("09:00", "20:00", break_minutes=60)
        d = _daily(s)
        self.assertAlmostEqual(d["regular_hours"], 8.0)
        self.assertAlmostEqual(d["overtime_hours"], 2.0)
        self.assertAlmostEqual(d["night_hours"], 0.0)
        self.assertAlmostEqual(d["total_work_hours"], 10.0)

    def test_overtime_12h_with_partial_night(self):
        """9:00~22:00 (점심1h) = 실12h → regular=8, overtime=4, night=0.
        (22:00이 경계이므로 야간 교차 없음 — 22:00 퇴근은 야간 시작점이지만
         반개구간 [start, end)이므로 0분 교차)."""
        s = _session("09:00", "22:00", break_minutes=60)
        d = _daily(s)
        self.assertAlmostEqual(d["regular_hours"], 8.0)
        self.assertAlmostEqual(d["overtime_hours"], 4.0)
        # 22:00 정각 퇴근이면 야간 교차 0
        self.assertAlmostEqual(d["night_hours"], 0.0)
        self.assertAlmostEqual(d["total_work_hours"], 12.0)

    def test_overtime_past_midnight_has_night(self):
        """9:00~23:00 (점심1h) = 실13h → regular=8, overtime=5, night=1h."""
        s = _session("09:00", "23:00", break_minutes=60)
        d = _daily(s)
        self.assertAlmostEqual(d["regular_hours"], 8.0)
        self.assertAlmostEqual(d["overtime_hours"], 5.0)
        # 22:00~23:00 = 1h 야간
        self.assertAlmostEqual(d["night_hours"], 1.0)
        self.assertAlmostEqual(d["total_work_hours"], 13.0)

    def test_night_only_22_to_06(self):
        """22:00~06:00 (점심0h) = 실8h 전부 야간.
        비휴일이므로: regular=8, overtime=0, night=8."""
        s = _session("22:00", "06:00", break_minutes=0)
        d = _daily(s)
        self.assertAlmostEqual(d["total_work_hours"], 8.0)
        self.assertAlmostEqual(d["regular_hours"], 8.0)
        self.assertAlmostEqual(d["overtime_hours"], 0.0)
        self.assertAlmostEqual(d["night_hours"], 8.0)

    def test_night_shift_with_overtime(self):
        """20:00~06:00 (점심0h) = 실10h, 야간 22:00~06:00=8h, 연장 2h.
        regular=8, overtime=2, night=8."""
        s = _session("20:00", "06:00", break_minutes=0)
        d = _daily(s)
        self.assertAlmostEqual(d["total_work_hours"], 10.0)
        self.assertAlmostEqual(d["regular_hours"], 8.0)
        self.assertAlmostEqual(d["overtime_hours"], 2.0)
        self.assertAlmostEqual(d["night_hours"], 8.0)

    def test_partial_night_hours(self):
        """9:00~00:00 (점심1h) = 실14h → regular=8, overtime=6, night=2h (22~00)."""
        s = _session("09:00", "00:00", break_minutes=60)
        d = _daily(s)
        self.assertAlmostEqual(d["total_work_hours"], 14.0)
        self.assertAlmostEqual(d["regular_hours"], 8.0)
        self.assertAlmostEqual(d["overtime_hours"], 6.0)
        self.assertAlmostEqual(d["night_hours"], 2.0)

    def test_early_morning_night_shift(self):
        """조기 출근 야간: 02:00~10:00 (break=0) = 실8h.
        야간 구간 02:00~06:00 = 4h 교차 → night=4h.
        §56④: 22:00~06:00 내 02:00~06:00 포함.
        regular=8, overtime=0, night=4.
        """
        s = WorkSession(
            employee="EMP-001",
            work_date=dt.date(2025, 1, 6),
            start_time=dt.time(2, 0),
            end_time=dt.time(10, 0),
            break_minutes=0,
        )
        d = _daily(s)
        self.assertAlmostEqual(d["total_work_hours"], 8.0)
        self.assertAlmostEqual(d["regular_hours"], 8.0)
        self.assertAlmostEqual(d["overtime_hours"], 0.0)
        # 02:00~06:00 = 4h (야간 early-morning 세그먼트)
        self.assertAlmostEqual(d["night_hours"], 4.0)

    def test_midnight_to_dawn_all_night(self):
        """00:00~06:00 (break=0) = 실6h, 전부 야간.
        regular=6, overtime=0, night=6.
        """
        s = WorkSession(
            employee="EMP-001",
            work_date=dt.date(2025, 1, 6),
            start_time=dt.time(0, 0),
            end_time=dt.time(6, 0),
            break_minutes=0,
        )
        d = _daily(s)
        self.assertAlmostEqual(d["total_work_hours"], 6.0)
        self.assertAlmostEqual(d["regular_hours"], 6.0)
        self.assertAlmostEqual(d["night_hours"], 6.0)
        self.assertAlmostEqual(d["overtime_hours"], 0.0)


class TestDailyPremiumHoliday(unittest.TestCase):
    """휴일 가산수당 분류."""

    def test_holiday_8h_no_overtime(self):
        """휴일 9:00~18:00 (점심1h) = 실8h → holiday=8, holiday_overtime=0."""
        s = _session("09:00", "18:00", break_minutes=60, is_holiday=True)
        d = _daily(s)
        self.assertTrue(d["is_holiday"])
        self.assertAlmostEqual(d["holiday_hours"], 8.0)
        self.assertAlmostEqual(d["holiday_overtime_hours"], 0.0)
        self.assertAlmostEqual(d["overtime_hours"], 0.0)
        self.assertAlmostEqual(d["regular_hours"], 0.0)
        self.assertAlmostEqual(d["night_hours"], 0.0)

    def test_holiday_less_than_8h(self):
        """휴일 9:00~15:00 (점심1h) = 실5h → holiday=5, holiday_overtime=0."""
        s = _session("09:00", "15:00", break_minutes=60, is_holiday=True)
        d = _daily(s)
        self.assertAlmostEqual(d["holiday_hours"], 5.0)
        self.assertAlmostEqual(d["holiday_overtime_hours"], 0.0)

    def test_holiday_12h(self):
        """휴일 9:00~22:00 (점심1h) = 실12h → holiday=8, holiday_overtime=4."""
        s = _session("09:00", "22:00", break_minutes=60, is_holiday=True)
        d = _daily(s)
        self.assertAlmostEqual(d["holiday_hours"], 8.0)
        self.assertAlmostEqual(d["holiday_overtime_hours"], 4.0)
        self.assertAlmostEqual(d["overtime_hours"], 0.0)
        self.assertAlmostEqual(d["total_work_hours"], 12.0)

    def test_holiday_12h_with_night(self):
        """휴일 야간 12h: 22:00~10:00(익일), break=0 → 실12h.
        holiday=8, holiday_overtime=4, night=8 (22:00~06:00).
        """
        # 22:00~10:00(익일): 클럭 12h, break 0
        s = _session("22:00", "10:00", break_minutes=0, is_holiday=True)
        d = _daily(s)
        self.assertAlmostEqual(d["total_work_hours"], 12.0)
        self.assertAlmostEqual(d["holiday_hours"], 8.0)
        self.assertAlmostEqual(d["holiday_overtime_hours"], 4.0)
        # 야간 22:00~06:00 = 8h
        self.assertAlmostEqual(d["night_hours"], 8.0)
        self.assertAlmostEqual(d["overtime_hours"], 0.0)

    def test_weekly_off_treated_as_holiday(self):
        """주휴일(is_weekly_off=True)도 휴일과 동일 처리."""
        s = _session("09:00", "18:00", break_minutes=60, is_weekly_off=True)
        d = _daily(s)
        self.assertTrue(d["is_holiday"])
        self.assertAlmostEqual(d["holiday_hours"], 8.0)
        self.assertAlmostEqual(d["overtime_hours"], 0.0)

    def test_holiday_night_partial(self):
        """휴일 10:00~23:00 (점심1h) = 실12h → holiday=8, holiday_overtime=4, night=1h."""
        s = _session("10:00", "23:00", break_minutes=60, is_holiday=True)
        d = _daily(s)
        self.assertAlmostEqual(d["total_work_hours"], 12.0)
        self.assertAlmostEqual(d["holiday_hours"], 8.0)
        self.assertAlmostEqual(d["holiday_overtime_hours"], 4.0)
        # 22:00~23:00 = 1h
        self.assertAlmostEqual(d["night_hours"], 1.0)


class TestPremiumMultipliers(unittest.TestCase):
    """가산 승수 검증."""

    def test_multipliers_present(self):
        s = _session("09:00", "18:00", break_minutes=60)
        d = _daily(s)
        m = d["premium_multipliers"]
        self.assertAlmostEqual(m["regular"], 1.0)
        self.assertAlmostEqual(m["overtime"], 1.5)
        self.assertAlmostEqual(m["night"], 0.5)
        self.assertAlmostEqual(m["holiday"], 1.5)
        self.assertAlmostEqual(m["holiday_overtime"], 2.0)


class TestWeeklyAggregate(unittest.TestCase):
    """주 단위 §53 한도 검증."""

    def _make_week_sessions(self, daily_work_hours: float, num_days: int = 5) -> list[WorkSession]:
        """월요일부터 num_days일 동안 매일 daily_work_hours 실근로 세션 생성.
        start=09:00, 휴게 1h, end 계산.
        """
        sessions = []
        base = dt.date(2025, 1, 6)  # 월요일
        for i in range(num_days):
            work_date = base + dt.timedelta(days=i)
            # 실근로 = 클럭 - 60분
            clock_hours = daily_work_hours + 1  # break 1h 추가
            end_h = 9 + int(clock_hours)
            end_m = round((clock_hours % 1) * 60)
            end_time = dt.time(end_h % 24, end_m)
            # 24h 넘으면 익일 처리됨 — WorkSession이 자동 처리
            s = WorkSession(
                employee="EMP-001",
                work_date=work_date,
                start_time=dt.time(9, 0),
                end_time=end_time,
                break_minutes=60,
                is_holiday=False,
                is_weekly_off=False,
            )
            sessions.append(s)
        return sessions

    def test_weekly_exactly_at_limit(self):
        """주 연장 정확히 12h: 월~목 각 11h + 금 8h.
        월~목: regular=8, overtime=3 → 소계 12h.
        금: regular=8, overtime=0.
        총 overtime=12h, exceeds=False.
        """
        base = dt.date(2025, 1, 6)
        sessions = []
        for i in range(4):  # 월~목 각 11h
            sessions.append(
                WorkSession(
                    employee="EMP-001",
                    work_date=base + dt.timedelta(days=i),
                    start_time=dt.time(9, 0),
                    end_time=dt.time(19, 0),  # 클럭 10h, break 1h → 실 9h → 1h OT
                    break_minutes=60,
                )
            )
        # 월~목 각 3h OT가 아니라 1h OT → 총 4h. 12h 만들려면 각 4h OT → 실 12h → 클럭 13h
        # 재설계: 월~목 각 실12h (9:00~22:00, 점심1h) → OT=4×4=16h > 12h
        # 정확히 12h 도달: 월~수 각 실12h (OT=4×3=12h), 목~금 실8h
        sessions = []
        for i in range(3):  # 월~수 각 실12h = OT 4h
            sessions.append(
                WorkSession(
                    employee="EMP-001",
                    work_date=base + dt.timedelta(days=i),
                    start_time=dt.time(9, 0),
                    end_time=dt.time(22, 0),  # 클럭 13h, break 1h → 실 12h
                    break_minutes=60,
                )
            )
        for i in range(3, 5):  # 목~금 실8h
            sessions.append(
                WorkSession(
                    employee="EMP-001",
                    work_date=base + dt.timedelta(days=i),
                    start_time=dt.time(9, 0),
                    end_time=dt.time(18, 0),  # 실 8h
                    break_minutes=60,
                )
            )

        result = calculate_weekly_aggregate(sessions)
        self.assertAlmostEqual(result["total_overtime_hours"], 12.0)
        self.assertAlmostEqual(result["weekly_overtime_limit"], 12.0)
        self.assertFalse(result["exceeds_weekly_limit"])
        self.assertAlmostEqual(result["exceed_amount_hours"], 0.0)
        self.assertIsNone(result["compliance_warning"])

    def test_weekly_exceeds_limit(self):
        """주 연장 17h: 월~목 각 실12h(OT=4×4=16h) + 금 실9h(OT=1h) = 17h.
        exceeds=True, exceed_amount=5h.
        """
        base = dt.date(2025, 1, 6)
        sessions = []
        for i in range(4):  # 월~목 각 실12h
            sessions.append(
                WorkSession(
                    employee="EMP-001",
                    work_date=base + dt.timedelta(days=i),
                    start_time=dt.time(9, 0),
                    end_time=dt.time(22, 0),  # 클럭 13h - 1h break = 실 12h
                    break_minutes=60,
                )
            )
        # 금: 실 9h (OT=1h)
        sessions.append(
            WorkSession(
                employee="EMP-001",
                work_date=base + dt.timedelta(days=4),
                start_time=dt.time(9, 0),
                end_time=dt.time(19, 0),  # 클럭 10h - 1h break = 실 9h
                break_minutes=60,
            )
        )

        result = calculate_weekly_aggregate(sessions)
        self.assertAlmostEqual(result["total_overtime_hours"], 17.0)
        self.assertTrue(result["exceeds_weekly_limit"])
        self.assertAlmostEqual(result["exceed_amount_hours"], 5.0)
        self.assertIsNotNone(result["compliance_warning"])
        self.assertIn("§53", result["compliance_warning"])

    def test_weekly_no_overtime(self):
        """주 40h(월~금 각 8h): total_overtime=0, exceeds=False."""
        sessions = self._make_week_sessions(daily_work_hours=8.0, num_days=5)
        result = calculate_weekly_aggregate(sessions)
        self.assertAlmostEqual(result["total_overtime_hours"], 0.0)
        self.assertFalse(result["exceeds_weekly_limit"])
        self.assertIsNone(result["compliance_warning"])

    def test_weekly_holiday_overtime_excluded_from_53_limit(self):
        """휴일근로는 §53 한도 집계에서 제외됨.
        일요일 실12h (holiday) → holiday_overtime=4h, overtime=0.
        월~금 각 실8h → overtime=0.
        weekly total_overtime=0, exceeds=False.
        """
        sessions = self._make_week_sessions(daily_work_hours=8.0, num_days=5)
        # 일요일 휴일 12h 추가
        holiday_session = WorkSession(
            employee="EMP-001",
            work_date=dt.date(2025, 1, 5),  # 일요일
            start_time=dt.time(9, 0),
            end_time=dt.time(22, 0),
            break_minutes=60,
            is_holiday=True,
        )
        sessions.append(holiday_session)
        result = calculate_weekly_aggregate(sessions)
        # 비휴일 overtime=0, 휴일 holiday_overtime=4 → total_overtime=0
        self.assertAlmostEqual(result["total_overtime_hours"], 0.0)
        self.assertFalse(result["exceeds_weekly_limit"])

    def test_weekly_empty_sessions(self):
        result = calculate_weekly_aggregate([])
        self.assertAlmostEqual(result["total_overtime_hours"], 0.0)
        self.assertFalse(result["exceeds_weekly_limit"])
        self.assertIsNone(result["week_start"])

    def test_weekly_meta(self):
        base = dt.date(2025, 1, 6)
        sessions = [
            WorkSession(
                employee="EMP-001",
                work_date=base + dt.timedelta(days=i),
                start_time=dt.time(9, 0),
                end_time=dt.time(18, 0),
                break_minutes=60,
            )
            for i in range(5)
        ]
        result = calculate_weekly_aggregate(sessions)
        self.assertEqual(result["week_start"], "2025-01-06")
        self.assertEqual(result["week_end"], "2025-01-10")
        self.assertEqual(len(result["by_day"]), 5)


class TestEstimatePremiumAmount(unittest.TestCase):
    """금액 추정 검증."""

    def test_regular_only(self):
        """실8h, 시급 10000원 → regular_pay=80000, total=80000."""
        s = _session("09:00", "18:00", break_minutes=60)
        d = _daily(s)
        pay = estimate_premium_amount(d, hourly_rate=10000)
        self.assertAlmostEqual(pay["regular_pay"], 80000.0)
        self.assertAlmostEqual(pay["overtime_pay"], 0.0)
        self.assertAlmostEqual(pay["night_pay"], 0.0)
        self.assertAlmostEqual(pay["holiday_pay"], 0.0)
        self.assertAlmostEqual(pay["holiday_overtime_pay"], 0.0)
        self.assertAlmostEqual(pay["total"], 80000.0)

    def test_overtime_pay_2h(self):
        """실10h (OT=2h), 시급 10000원 → overtime_pay = 2×10000×1.5 = 30000."""
        s = _session("09:00", "20:00", break_minutes=60)
        d = _daily(s)
        pay = estimate_premium_amount(d, hourly_rate=10000)
        self.assertAlmostEqual(pay["overtime_pay"], 30000.0)  # 2h × 10000 × 1.5
        self.assertAlmostEqual(pay["regular_pay"], 80000.0)
        self.assertAlmostEqual(pay["total"], 110000.0)

    def test_night_pay_addend(self):
        """실8h 전부 야간(22:00~06:00) → night_pay = 8×10000×0.5 = 40000.
        regular_pay도 포함: total=80000+40000=120000."""
        s = _session("22:00", "06:00", break_minutes=0)
        d = _daily(s)
        pay = estimate_premium_amount(d, hourly_rate=10000)
        self.assertAlmostEqual(pay["night_pay"], 40000.0)
        self.assertAlmostEqual(pay["regular_pay"], 80000.0)
        self.assertAlmostEqual(pay["total"], 120000.0)

    def test_holiday_pay_8h(self):
        """휴일 실8h → holiday_pay = 8×10000×1.5 = 120000."""
        s = _session("09:00", "18:00", break_minutes=60, is_holiday=True)
        d = _daily(s)
        pay = estimate_premium_amount(d, hourly_rate=10000)
        self.assertAlmostEqual(pay["holiday_pay"], 120000.0)
        self.assertAlmostEqual(pay["holiday_overtime_pay"], 0.0)
        self.assertAlmostEqual(pay["regular_pay"], 0.0)
        self.assertAlmostEqual(pay["total"], 120000.0)

    def test_holiday_overtime_pay(self):
        """휴일 실12h → holiday_pay=8×1.5×10000=120000, holiday_overtime=4×2.0×10000=80000."""
        s = _session("09:00", "22:00", break_minutes=60, is_holiday=True)
        d = _daily(s)
        pay = estimate_premium_amount(d, hourly_rate=10000)
        self.assertAlmostEqual(pay["holiday_pay"], 120000.0)
        self.assertAlmostEqual(pay["holiday_overtime_pay"], 80000.0)
        self.assertAlmostEqual(pay["total"], 200000.0)

    def test_holiday_night_stacking(self):
        """휴일 야간 실12h (22:00~10:00, break=0):
        holiday=8, holiday_overtime=4, night=8(22~06).
        holiday_pay = 8×1.5×10000 = 120000
        holiday_overtime_pay = 4×2.0×10000 = 80000
        night_pay = 8×0.5×10000 = 40000 (추가분)
        total = 120000 + 80000 + 40000 = 240000.
        """
        s = _session("22:00", "10:00", break_minutes=0, is_holiday=True)
        d = _daily(s)
        pay = estimate_premium_amount(d, hourly_rate=10000)
        self.assertAlmostEqual(pay["holiday_pay"], 120000.0)
        self.assertAlmostEqual(pay["holiday_overtime_pay"], 80000.0)
        self.assertAlmostEqual(pay["night_pay"], 40000.0)
        self.assertAlmostEqual(pay["total"], 240000.0)

    def test_overtime_night_stacking(self):
        """비휴일 연장 야간 (20:00~06:00, break=0):
        실10h, regular=8, overtime=2, night=8.
        regular_pay = 8×1.0×10000 = 80000
        overtime_pay = 2×1.5×10000 = 30000
        night_pay = 8×0.5×10000 = 40000
        total = 150000.
        """
        s = _session("20:00", "06:00", break_minutes=0)
        d = _daily(s)
        pay = estimate_premium_amount(d, hourly_rate=10000)
        self.assertAlmostEqual(pay["regular_pay"], 80000.0)
        self.assertAlmostEqual(pay["overtime_pay"], 30000.0)
        self.assertAlmostEqual(pay["night_pay"], 40000.0)
        self.assertAlmostEqual(pay["total"], 150000.0)


class TestEdgeCases(unittest.TestCase):
    """경계값 및 엣지케이스."""

    def test_zero_work_hours(self):
        """실 근로 0h (클럭 = 휴게) → 모든 값 0."""
        s = _session("09:00", "10:00", break_minutes=60)
        d = _daily(s)
        self.assertAlmostEqual(d["total_work_hours"], 0.0)
        self.assertAlmostEqual(d["regular_hours"], 0.0)
        self.assertAlmostEqual(d["overtime_hours"], 0.0)

    def test_exactly_8h_boundary(self):
        """실 정확히 8h → regular=8, overtime=0."""
        s = _session("08:00", "17:00", break_minutes=60)
        d = _daily(s)
        self.assertAlmostEqual(d["regular_hours"], 8.0)
        self.assertAlmostEqual(d["overtime_hours"], 0.0)

    def test_1_minute_overtime(self):
        """실 8h 1분 → regular=8, overtime=1/60."""
        s = WorkSession(
            employee="EMP-001",
            work_date=dt.date(2025, 1, 6),
            start_time=dt.time(9, 0),
            end_time=dt.time(18, 1),  # 클럭 9h1m, break 1h → 실 8h1m
            break_minutes=60,
        )
        d = _daily(s)
        self.assertAlmostEqual(d["regular_hours"], 8.0)
        self.assertAlmostEqual(d["overtime_hours"], 1 / 60, places=4)

    def test_night_boundary_exactly_22h(self):
        """09:00~22:00 (break=1h) → 실12h, night=0 (22:00 경계 — 교차 없음)."""
        s = _session("09:00", "22:00", break_minutes=60)
        d = _daily(s)
        self.assertAlmostEqual(d["night_hours"], 0.0)

    def test_night_boundary_22h_01m(self):
        """09:00~22:01 (break=1h) → night=1/60."""
        s = WorkSession(
            employee="EMP-001",
            work_date=dt.date(2025, 1, 6),
            start_time=dt.time(9, 0),
            end_time=dt.time(22, 1),
            break_minutes=60,
        )
        d = _daily(s)
        self.assertAlmostEqual(d["night_hours"], 1 / 60, places=4)

    def test_holiday_exactly_8h_no_overtime(self):
        """휴일 정확히 8h → holiday=8, holiday_overtime=0."""
        s = _session("09:00", "18:00", break_minutes=60, is_holiday=True)
        d = _daily(s)
        self.assertAlmostEqual(d["holiday_hours"], 8.0)
        self.assertAlmostEqual(d["holiday_overtime_hours"], 0.0)

    def test_holiday_8h_01m_overtime_starts(self):
        """휴일 8h 1분 → holiday=8, holiday_overtime=1/60."""
        s = WorkSession(
            employee="EMP-001",
            work_date=dt.date(2025, 1, 6),
            start_time=dt.time(9, 0),
            end_time=dt.time(18, 1),
            break_minutes=60,
            is_holiday=True,
        )
        d = _daily(s)
        self.assertAlmostEqual(d["holiday_hours"], 8.0)
        self.assertAlmostEqual(d["holiday_overtime_hours"], 1 / 60, places=4)


class TestWeeklyLimitValues(unittest.TestCase):
    """주 연장 상수 및 법적 기준값."""

    def test_weekly_limit_constant(self):
        self.assertEqual(WEEKLY_OVERTIME_LIMIT_HOURS, 12.0)

    def test_weekly_aggregate_limit_field(self):
        result = calculate_weekly_aggregate([])
        self.assertEqual(result["weekly_overtime_limit"], 12.0)


if __name__ == "__main__":
    unittest.main()
