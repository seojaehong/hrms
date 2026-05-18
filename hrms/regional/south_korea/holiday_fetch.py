"""한국 공휴일 자동 페치 + 대체공휴일 계산.

공공데이터포털 특일정보 API에서 fetch한다. API 키 없거나 fetch 실패 시
hardcoded 2025-2027 데이터로 fallback한다.

API: https://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService/getRestDeInfo
- 파라미터: solYear, solMonth, ServiceKey
- 응답: XML (items/item: dateName, locdate, isHoliday)
- API 키 환경변수: DATA_GO_KR_SERVICE_KEY (없으면 hardcoded fallback)
"""

from __future__ import annotations

import os
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

_API_BASE = (
    "https://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService/getRestDeInfo"
)

# ---------------------------------------------------------------------------
# Hardcoded holiday data — 2025 / 2026 / 2027
#
# 형식: (YYYY-MM-DD, 공휴일명)
# 대체공휴일 여부는 is_substitute()로 판별.
#
# 출처 및 검증:
#   2025 — 행정안전부 공식 달력 확인 완료
#   2026 — 양력 고정일 + 음력 환산 (설날 2026-02-17, 부처님오신날 2026-05-24,
#           추석 2026-09-25). 대통령선거 미포함 (일정 미확정).
#          선거일: 제9회 전국동시지방선거 2026-06-03 (수) 포함.
#   2027 — 양력 고정일 + 음력 환산 (설날 2027-02-06, 부처님오신날 2027-05-13,
#           추석 2027-09-15). API 키 있으면 API 우선 사용 권장.
# ---------------------------------------------------------------------------
HARDCODED_HOLIDAYS: dict[int, list[tuple[str, str]]] = {
    2025: [
        ("2025-01-01", "신정"),
        ("2025-01-28", "설날연휴"),
        ("2025-01-29", "설날"),
        ("2025-01-30", "설날연휴"),
        ("2025-03-01", "삼일절"),
        ("2025-03-03", "대체공휴일(삼일절)"),  # 삼일절 토요일 -> 일요일 -> 월요일
        ("2025-05-05", "어린이날"),
        ("2025-05-05", "부처님오신날"),  # 어린이날과 동일
        ("2025-05-06", "대체공휴일(어린이날/부처님오신날)"),  # 겹침 -> 다음 날
        ("2025-06-06", "현충일"),
        ("2025-08-15", "광복절"),
        ("2025-10-03", "개천절"),
        ("2025-10-05", "추석연휴"),
        ("2025-10-06", "추석"),
        ("2025-10-07", "추석연휴"),
        ("2025-10-08", "대체공휴일(추석)"),  # 추석연휴 일요일 -> 수요일
        ("2025-10-09", "한글날"),
        ("2025-12-25", "기독탄신일"),
    ],
    2026: [
        ("2026-01-01", "신정"),
        ("2026-02-16", "설날연휴"),
        ("2026-02-17", "설날"),
        ("2026-02-18", "설날연휴"),
        ("2026-03-01", "삼일절"),
        ("2026-03-02", "대체공휴일(삼일절)"),  # 삼일절 일요일 -> 월요일
        ("2026-05-05", "어린이날"),
        ("2026-05-24", "부처님오신날"),
        ("2026-05-25", "대체공휴일(부처님오신날)"),  # 부처님오신날 일요일 -> 월요일
        ("2026-06-03", "선거일"),  # 제9회 전국동시지방선거
        ("2026-06-06", "현충일"),
        ("2026-08-15", "광복절"),
        ("2026-08-17", "대체공휴일(광복절)"),  # 광복절 토요일 -> 월요일
        ("2026-09-24", "추석연휴"),
        ("2026-09-25", "추석"),
        ("2026-09-26", "추석연휴"),
        ("2026-09-28", "대체공휴일(추석연휴)"),  # 추석연휴 토요일 -> 월요일
        ("2026-10-03", "개천절"),
        ("2026-10-05", "대체공휴일(개천절)"),  # 개천절 토요일 -> 월요일
        ("2026-10-09", "한글날"),
        ("2026-12-25", "기독탄신일"),
    ],
    2027: [
        ("2027-01-01", "신정"),
        ("2027-02-05", "설날연휴"),
        ("2027-02-06", "설날"),
        ("2027-02-07", "설날연휴"),
        ("2027-02-08", "대체공휴일(설날)"),  # 설날연휴 일요일 -> 월요일
        ("2027-03-01", "삼일절"),
        ("2027-05-05", "어린이날"),
        ("2027-05-13", "부처님오신날"),
        ("2027-06-06", "현충일"),
        ("2027-06-07", "대체공휴일(현충일)"),  # 현충일 일요일 -> 월요일
        ("2027-08-15", "광복절"),
        ("2027-08-16", "대체공휴일(광복절)"),  # 광복절 일요일 -> 월요일
        ("2027-09-14", "추석연휴"),
        ("2027-09-15", "추석"),
        ("2027-09-16", "추석연휴"),
        ("2027-10-03", "개천절"),
        ("2027-10-04", "대체공휴일(개천절)"),  # 개천절 일요일 -> 월요일
        ("2027-10-09", "한글날"),
        ("2027-10-11", "대체공휴일(한글날)"),  # 한글날 토요일 -> 월요일
        ("2027-12-25", "기독탄신일"),
    ],
}

_SUPPORTED_YEARS = frozenset(HARDCODED_HOLIDAYS.keys())
_MIN_YEAR = 2000
_MAX_YEAR = 2100


def fetch_holidays(
    year: int,
    *,
    service_key: str | None = None,
    timeout: float = 5.0,
) -> list[dict]:
    """공공데이터포털에서 공휴일 fetch. API 키 없거나 실패 시 hardcoded fallback.

    API 키는 파라미터 또는 환경변수 DATA_GO_KR_SERVICE_KEY에서 읽는다.

    Args:
        year: 연도 (예: 2025)
        service_key: 공공데이터포털 API 인증키 (없으면 환경변수 참조)
        timeout: 월별 API 요청 타임아웃 (초). 기본 5초.

    Returns:
        공휴일 dict 리스트::

            [
                {
                    "date": "2026-01-01",
                    "name": "신정",
                    "is_substitute": False,
                    "source": "api",   # or "hardcoded"
                },
                ...
            ]

    Raises:
        ValueError: year가 유효 범위(_MIN_YEAR~_MAX_YEAR)를 벗어난 경우.
    """
    if not (_MIN_YEAR <= year <= _MAX_YEAR):
        raise ValueError(
            f"year must be between {_MIN_YEAR} and {_MAX_YEAR}, got {year}"
        )

    resolved_key = service_key or os.environ.get("DATA_GO_KR_SERVICE_KEY") or ""

    if resolved_key:
        try:
            return fetch_with_api(year, resolved_key, timeout)
        except Exception:
            pass  # graceful fallback to hardcoded

    return get_hardcoded(year)


def fetch_with_api(year: int, service_key: str, timeout: float) -> list[dict]:
    """API 호출 (12개월 모두). XML 파싱 후 dict 리스트 반환.

    Args:
        year: 연도 (예: 2025)
        service_key: 공공데이터포털 API 인증키
        timeout: 요청당 타임아웃 (초)

    Returns:
        공휴일 dict 리스트 (source="api")

    Raises:
        RuntimeError: API 결과가 비어 있거나 파싱 실패 시
    """
    results: list[dict] = []
    for month in range(1, 13):
        month_str = f"{month:02d}"
        params = urllib.parse.urlencode(
            {
                "ServiceKey": service_key,
                "solYear": year,
                "solMonth": month_str,
                "numOfRows": 50,
                "_type": "xml",
            }
        )
        url = f"{_API_BASE}?{params}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()

        month_items = _parse_api_xml(raw)
        results.extend(month_items)

    return results


def _parse_api_xml(raw: bytes) -> list[dict]:
    """API XML 응답 파싱.

    Expected schema::

        <response>
          <header><resultCode>00</resultCode></header>
          <body>
            <items>
              <item>
                <dateName>신정</dateName>
                <isHoliday>Y</isHoliday>
                <locdate>20260101</locdate>
              </item>
            </items>
          </body>
        </response>

    Args:
        raw: API 응답 바이트

    Returns:
        공휴일 dict 리스트

    Raises:
        ValueError: resultCode가 00이 아닌 경우
    """
    root = ET.fromstring(raw)
    result_code = root.findtext("header/resultCode") or ""
    if result_code != "00":
        raise ValueError(f"API returned non-OK resultCode: {result_code!r}")

    items = []
    for item in root.findall(".//item"):
        locdate = item.findtext("locdate") or ""
        date_name = item.findtext("dateName") or ""
        is_holiday_flag = item.findtext("isHoliday") or "N"

        if len(locdate) != 8 or not locdate.isdigit():
            continue
        if is_holiday_flag != "Y":
            continue

        date_str = f"{locdate[:4]}-{locdate[4:6]}-{locdate[6:]}"
        items.append(
            {
                "date": date_str,
                "name": date_name,
                "is_substitute": is_substitute(date_name),
                "source": "api",
            }
        )
    return items


def get_hardcoded(year: int) -> list[dict]:
    """HARDCODED_HOLIDAYS에서 해당 연도 데이터를 dict 리스트로 반환.

    지원 연도(2025~2027) 외에는 빈 리스트 반환.

    Args:
        year: 연도

    Returns:
        공휴일 dict 리스트 (source="hardcoded")
    """
    raw_pairs = HARDCODED_HOLIDAYS.get(year, [])
    return [
        {
            "date": date_str,
            "name": name,
            "is_substitute": is_substitute(name),
            "source": "hardcoded",
        }
        for date_str, name in raw_pairs
    ]


def is_substitute(name: str) -> bool:
    """공휴일 이름에 '대체공휴일' 포함 여부.

    Args:
        name: 공휴일명

    Returns:
        True if 대체공휴일
    """
    return "대체공휴일" in (name or "")
