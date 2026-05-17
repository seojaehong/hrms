"""Frappe whitelist wrapper — 한국 공휴일 Holiday List 시드 API.

외부에서 Frappe REST API로 호출 가능한 whitelist 함수.
human_approved 파라미터로 fail-closed 보호.
"""

from __future__ import annotations

try:
    import frappe
except ImportError:
    frappe = None  # type: ignore[assignment]

from hrms.regional.south_korea.holiday_seed import (
    seed_korea_holiday_list,
    seed_korea_holiday_list_multi,
)


if frappe is not None:

    @frappe.whitelist()
    def seed_holidays(
        year: int,
        holiday_list_name: str | None = None,
        company: str | None = None,
        service_key: str | None = None,
        human_approved: bool = False,
    ) -> dict:
        """한국 공휴일을 Frappe Holiday List에 시드한다.

        Args:
            year: 연도 (예: 2025)
            holiday_list_name: Holiday List 이름 (없으면 자동 생성)
            company: 회사명 (선택)
            service_key: 공공데이터포털 API 인증키 (없으면 hardcoded fallback)
            human_approved: True여야만 실제로 데이터를 쓴다 (fail-closed)

        Returns:
            seed_korea_holiday_list 결과 dict
        """
        try:
            year = int(year)
        except (TypeError, ValueError):
            frappe.throw("year must be an integer")

        if isinstance(human_approved, str):
            human_approved = human_approved.strip().lower() in {"1", "true", "yes"}

        return seed_korea_holiday_list(
            year=year,
            holiday_list_name=holiday_list_name or None,
            company=company or None,
            service_key=service_key or None,
            human_approved=bool(human_approved),
        )

    @frappe.whitelist()
    def seed_holidays_multi(
        years: list | None = None,
        company: str | None = None,
        service_key: str | None = None,
        human_approved: bool = False,
    ) -> list:
        """여러 연도의 한국 공휴일을 한 번에 시드한다.

        Args:
            years: 연도 리스트 (없으면 [2025, 2026, 2027])
            company: 회사명 (선택)
            service_key: 공공데이터포털 API 인증키 (없으면 hardcoded fallback)
            human_approved: True여야만 실제로 데이터를 쓴다 (fail-closed)

        Returns:
            연도별 결과 리스트
        """
        if isinstance(human_approved, str):
            human_approved = human_approved.strip().lower() in {"1", "true", "yes"}

        parsed_years: list[int] | None = None
        if years is not None:
            try:
                parsed_years = [int(y) for y in years]
            except (TypeError, ValueError):
                frappe.throw("years must be a list of integers")

        return seed_korea_holiday_list_multi(
            years=parsed_years,
            company=company or None,
            service_key=service_key or None,
            human_approved=bool(human_approved),
        )

else:
    # Frappe 없을 때 stub — 테스트 환경용
    def seed_holidays(  # type: ignore[misc]
        year: int,
        holiday_list_name: str | None = None,
        company: str | None = None,
        service_key: str | None = None,
        human_approved: bool = False,
    ) -> dict:
        """Stub for non-Frappe environments."""
        return seed_korea_holiday_list(
            year=year,
            holiday_list_name=holiday_list_name,
            company=company,
            service_key=service_key,
            human_approved=human_approved,
        )

    def seed_holidays_multi(  # type: ignore[misc]
        years: list | None = None,
        company: str | None = None,
        service_key: str | None = None,
        human_approved: bool = False,
    ) -> list:
        """Stub for non-Frappe environments."""
        return seed_korea_holiday_list_multi(
            years=years,
            company=company,
            service_key=service_key,
            human_approved=human_approved,
        )
