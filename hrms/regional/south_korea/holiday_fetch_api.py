"""Frappe whitelist wrapper — 한국 공휴일 fetch API.

외부에서 Frappe REST API로 호출 가능한 whitelist 함수.
"""

from __future__ import annotations

try:
    import frappe
except ImportError:
    frappe = None  # type: ignore[assignment]

from hrms.regional.south_korea.holiday_fetch import fetch_holidays


if frappe is not None:

    @frappe.whitelist()
    def get_korea_holidays(year: int, service_key: str | None = None) -> dict:
        """한국 공휴일 목록을 반환한다.

        Args:
            year: 연도 (예: 2025)
            service_key: 공공데이터포털 API 인증키 (없으면 hardcoded fallback)

        Returns:
            ::

                {
                    "year": int,
                    "holidays": [
                        {"date": "YYYY-MM-DD", "name": str, "is_substitute": bool, "source": str},
                        ...
                    ],
                    "count": int,
                    "source": "api" | "hardcoded",
                }
        """
        try:
            year = int(year)
        except (TypeError, ValueError):
            frappe.throw("year must be an integer")

        holidays = fetch_holidays(year, service_key=service_key or None)
        source = holidays[0]["source"] if holidays else "hardcoded"

        return {
            "year": year,
            "holidays": holidays,
            "count": len(holidays),
            "source": source,
        }

else:
    # Frappe 없을 때 stub — 테스트 환경용
    def get_korea_holidays(year: int, service_key: str | None = None) -> dict:  # type: ignore[misc]
        """Stub for non-Frappe environments."""
        holidays = fetch_holidays(year, service_key=service_key or None)
        source = holidays[0]["source"] if holidays else "hardcoded"
        return {
            "year": year,
            "holidays": holidays,
            "count": len(holidays),
            "source": source,
        }
