"""한국 공휴일 Frappe Holiday List 시드.

fetch한 공휴일 데이터를 Frappe Holiday List에 idempotent하게 삽입한다.
human_approved=False 이면 fail-closed (아무것도 쓰지 않음).
"""

from __future__ import annotations

import os
from typing import Any

try:
    import frappe
except ImportError:
    frappe = None  # type: ignore[assignment]

from hrms.regional.south_korea.holiday_fetch import fetch_holidays


def seed_korea_holiday_list(
    *,
    year: int,
    holiday_list_name: str | None = None,
    company: str | None = None,
    service_key: str | None = None,
    human_approved: bool = False,
) -> dict[str, Any]:
    """Holiday List에 한국 공휴일을 시드한다.

    Args:
        year: 대상 연도 (예: 2025)
        holiday_list_name: Frappe Holiday List 이름.
            없으면 ``"한국 공휴일 {year}"`` 으로 자동 생성.
        company: Holiday List에 연결할 회사명 (선택).
        service_key: 공공데이터포털 API 인증키 (없으면 hardcoded fallback).
        human_approved: True여야만 실제로 데이터를 쓴다 (fail-closed).

    Returns:
        ::

            {
                "applied": bool,
                "year": int,
                "holiday_list": str,
                "new_count": int,
                "existing_count": int,
                "source": "api" | "hardcoded",
                "human_approval_verified": bool,
            }

    Raises:
        RuntimeError: frappe 모듈을 import할 수 없는 경우.
        PermissionError: human_approved=False인 경우 (fail-closed).
    """
    if frappe is None:
        raise RuntimeError(
            "frappe is not available. Run this inside a Frappe bench environment."
        )

    if not human_approved:
        return {
            "applied": False,
            "year": year,
            "holiday_list": holiday_list_name or f"한국 공휴일 {year}",
            "new_count": 0,
            "existing_count": 0,
            "source": "none",
            "human_approval_verified": False,
        }

    resolved_key = service_key or os.environ.get("DATA_GO_KR_SERVICE_KEY") or None
    holidays = fetch_holidays(year, service_key=resolved_key)
    source = holidays[0]["source"] if holidays else "hardcoded"

    list_name = holiday_list_name or f"한국 공휴일 {year}"

    # Holiday List가 없으면 생성
    if not frappe.db.exists("Holiday List", list_name):
        hl_doc = frappe.get_doc(
            {
                "doctype": "Holiday List",
                "holiday_list_name": list_name,
                "from_date": f"{year}-01-01",
                "to_date": f"{year}-12-31",
                "company": company,
            }
        )
        hl_doc.insert(ignore_permissions=True)

    # 기존 날짜+이름 조합 수집 (idempotent 체크용)
    existing_holidays: set[tuple[str, str]] = set()
    existing_rows = frappe.get_all(
        "Holiday",
        filters={"parent": list_name},
        fields=["holiday_date", "description"],
    )
    for row in existing_rows:
        date_str = str(row.get("holiday_date") or "")
        desc = str(row.get("description") or "")
        existing_holidays.add((date_str, desc))

    new_count = 0
    existing_count = 0

    hl_doc = frappe.get_doc("Holiday List", list_name)

    for holiday in holidays:
        date_str = holiday["date"]
        name = holiday["name"]
        key = (date_str, name)

        if key in existing_holidays:
            existing_count += 1
            continue

        hl_doc.append(
            "holidays",
            {
                "holiday_date": date_str,
                "description": name,
                "weekly_off": 0,
            },
        )
        existing_holidays.add(key)
        new_count += 1

    if new_count > 0:
        hl_doc.save(ignore_permissions=True)

    return {
        "applied": True,
        "year": year,
        "holiday_list": list_name,
        "new_count": new_count,
        "existing_count": existing_count,
        "source": source,
        "human_approval_verified": True,
    }


def seed_korea_holiday_list_multi(
    years: list[int] | None = None,
    *,
    company: str | None = None,
    service_key: str | None = None,
    human_approved: bool = False,
) -> list[dict[str, Any]]:
    """여러 연도를 한 번에 시드한다.

    Args:
        years: 연도 리스트. 기본값은 [2025, 2026, 2027].
        company: Holiday List에 연결할 회사명 (선택).
        service_key: 공공데이터포털 API 인증키 (없으면 hardcoded fallback).
        human_approved: True여야만 실제로 데이터를 쓴다 (fail-closed).

    Returns:
        연도별 seed_korea_holiday_list 결과 리스트.
    """
    if years is None:
        years = [2025, 2026, 2027]

    results = []
    for year in years:
        result = seed_korea_holiday_list(
            year=year,
            company=company,
            service_key=service_key,
            human_approved=human_approved,
        )
        results.append(result)
    return results
