"""통합 검색 — framework-free core + Frappe adapter 인터페이스.

외부 LLM API 없음. 순수 문자열 매칭 + 권한 필터.

진입점:
    global_search(query, user_role, ..., data_loader) -> dict
    search_within_doctype(doctype, query, ..., data_loader) -> list[dict]
    build_search_snippet(doc, query) -> str
    apply_search_permissions(results, user_role, user_employee) -> list[dict]
"""

from __future__ import annotations

import time
from typing import Any, Callable

# ---------------------------------------------------------------------------
# 검색 가능한 Doctype 메타 정보
# ---------------------------------------------------------------------------

SEARCHABLE_DOCTYPES: dict[str, dict[str, Any]] = {
    "Employee": {
        "label": "직원",
        "search_fields": ["employee_name", "email", "designation", "department"],
        "result_template": "{employee_name} ({email}) — {department}",
        "url_template": "/app/employee/{name}",
        "pwa_url_template": "/hrms/employee/{name}",
        # 권한: 직원은 자신의 name 으로만 조회 가능
        "owner_field": "name",
    },
    "Attendance": {
        "label": "출근기록",
        "search_fields": ["employee", "attendance_date", "status"],
        "result_template": "{employee} — {attendance_date} ({status})",
        "url_template": "/app/attendance/{name}",
        "pwa_url_template": "/hrms/attendance/{name}",
        "owner_field": "employee",
    },
    "Salary Slip": {
        "label": "급여명세서",
        "search_fields": ["employee", "employee_name", "start_date", "end_date"],
        "result_template": "{employee_name} — {start_date} ~ {end_date}",
        "url_template": "/app/salary-slip/{name}",
        "pwa_url_template": "/hrms/salary-slips/{name}",
        "owner_field": "employee",
    },
    "Leave Application": {
        "label": "휴가신청",
        "search_fields": ["employee", "employee_name", "leave_type", "from_date", "to_date"],
        "result_template": "{employee_name} — {leave_type} ({from_date} ~ {to_date})",
        "url_template": "/app/leave-application/{name}",
        "pwa_url_template": "/hrms/leaves/{name}",
        "owner_field": "employee",
    },
    "Employment Contract": {
        "label": "고용계약서",
        "search_fields": ["employee", "employee_name", "contract_type"],
        "result_template": "{employee_name} — {contract_type}",
        "url_template": "/app/employment-contract/{name}",
        "pwa_url_template": "/hrms/contract/{name}",
        "owner_field": "employee",
    },
    "Korea Payroll Closing Draft": {
        "label": "한국 페이롤 마감",
        "search_fields": ["company", "pay_year_month", "status"],
        "result_template": "{company} — {pay_year_month} ({status})",
        "url_template": "/app/korea-payroll-closing-draft/{name}",
        "pwa_url_template": "/hrms/korea-payroll-closing-draft/{name}",
        # 마감 문서는 HR/관리자만 — 직원은 접근 불가
        "owner_field": None,
        "hr_only": True,
    },
    "Korea Workplace Profile": {
        "label": "한국 사업장",
        "search_fields": ["company", "business_registration_number", "worksite_name"],
        "result_template": "{worksite_name} ({business_registration_number})",
        "url_template": "/app/korea-workplace-profile/{name}",
        "pwa_url_template": "/hrms/korea-workplace-profile/{name}",
        "owner_field": None,
        "hr_only": True,
    },
    "Korea Employment Profile": {
        "label": "한국 고용 프로필",
        "search_fields": ["employee", "employee_name", "employment_type"],
        "result_template": "{employee_name} — {employment_type}",
        "url_template": "/app/korea-employment-profile/{name}",
        "pwa_url_template": "/hrms/korea-employment-profile/{name}",
        "owner_field": "employee",
    },
}

# ---------------------------------------------------------------------------
# 역할 상수
# ---------------------------------------------------------------------------

ROLE_EMPLOYEE = "Employee"
ROLE_HR = "HR Manager"
ROLE_MANAGER = "HR User"
# 관리자 역할 집합 (자유 확장)
ADMIN_ROLES: frozenset[str] = frozenset(
    {ROLE_HR, ROLE_MANAGER, "System Manager", "Administrator"}
)


def _is_admin(user_role: str) -> bool:
    return user_role in ADMIN_ROLES


# ---------------------------------------------------------------------------
# 핵심 검색 함수
# ---------------------------------------------------------------------------


def global_search(
    *,
    query: str,
    user_role: str,
    user_employee: str | None = None,
    company: str | None = None,
    doctypes: list[str] | None = None,
    limit_per_doctype: int = 10,
    data_loader: Callable,
) -> dict:
    """통합 검색.

    Args:
        query: 검색어 (2자 이상 권장 — 프론트에서 강제, 백엔드는 1자도 허용)
        user_role: 현재 사용자 역할 ('Employee', 'HR Manager', ...)
        user_employee: 현재 사용자의 Employee docname (직원 자기 데이터 필터용)
        company: 필터할 회사 (None이면 전체)
        doctypes: 검색할 doctype 목록 (None이면 SEARCHABLE_DOCTYPES 전체)
        limit_per_doctype: doctype 당 최대 결과 수
        data_loader: (doctype, query, search_fields, filters, limit) -> list[dict]

    Returns:
        {
            "contract_type": "korea_global_search_result_v1",
            "query": str,
            "total_results": int,
            "results_by_doctype": { doctype: [result, ...], ... },
            "elapsed_ms": int,
        }
    """
    t0 = time.monotonic()

    query = (query or "").strip()
    if not query:
        return _empty_response(query=query, elapsed_ms=0)

    target_doctypes = doctypes if doctypes else list(SEARCHABLE_DOCTYPES.keys())
    # 존재하지 않는 doctype 요청 무시
    target_doctypes = [dt for dt in target_doctypes if dt in SEARCHABLE_DOCTYPES]

    results_by_doctype: dict[str, list[dict]] = {}
    total = 0

    for doctype in target_doctypes:
        meta = SEARCHABLE_DOCTYPES[doctype]

        # hr_only 독타입: 관리자만 접근
        if meta.get("hr_only") and not _is_admin(user_role):
            continue

        raw_results = search_within_doctype(
            doctype=doctype,
            query=query,
            search_fields=meta["search_fields"],
            company=company,
            user_role=user_role,
            user_employee=user_employee,
            owner_field=meta.get("owner_field"),
            limit=limit_per_doctype,
            data_loader=data_loader,
        )

        # 권한 필터 (소유자 기반)
        filtered = apply_search_permissions(
            results=raw_results,
            user_role=user_role,
            user_employee=user_employee,
            owner_field=meta.get("owner_field"),
        )

        # 결과 카드 포맷
        cards = [
            _format_result(doc=doc, meta=meta, query=query)
            for doc in filtered
        ]

        if cards:
            results_by_doctype[doctype] = cards
            total += len(cards)

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    return {
        "contract_type": "korea_global_search_result_v1",
        "query": query,
        "total_results": total,
        "results_by_doctype": results_by_doctype,
        "elapsed_ms": elapsed_ms,
    }


def search_within_doctype(
    *,
    doctype: str,
    query: str,
    search_fields: list[str],
    company: str | None = None,
    user_role: str,
    user_employee: str | None = None,
    owner_field: str | None = None,
    limit: int = 10,
    data_loader: Callable,
) -> list[dict]:
    """단일 doctype 검색.

    data_loader 시그니처:
        data_loader(
            doctype: str,
            query: str,
            search_fields: list[str],
            extra_filters: dict,
            limit: int,
        ) -> list[dict]

    직원 역할이면 owner_field 기반으로 pre-filter (loader에게 전달).
    """
    extra_filters: dict[str, Any] = {}

    if company:
        extra_filters["company"] = company

    # 직원 역할이면 자신의 데이터만 — loader 레벨 최적화
    if not _is_admin(user_role) and user_employee and owner_field:
        extra_filters[owner_field] = user_employee

    try:
        return data_loader(
            doctype=doctype,
            query=query,
            search_fields=search_fields,
            extra_filters=extra_filters,
            limit=limit,
        )
    except Exception:
        # doctype 미존재 or DB 오류 — 해당 doctype 스킵
        return []


def build_search_snippet(*, doc: dict, query: str, max_length: int = 100) -> str:
    """검색 결과 snippet 생성 (query 위치 강조용 마커 포함).

    반환 형식: "...앞텍스트 **매치** 뒤텍스트..."
    프론트엔드에서 **...** 를 <mark> 로 치환해 렌더링할 것.
    """
    if not query:
        return ""

    query_lower = query.lower()
    # 모든 문자열 값을 합쳐서 매치 탐색
    combined = " ".join(str(v) for v in doc.values() if v and isinstance(v, str))

    idx = combined.lower().find(query_lower)
    if idx == -1:
        snippet = combined[:max_length]
        return snippet + ("..." if len(combined) > max_length else "")

    # 매치 전후 컨텍스트
    half = max_length // 2
    start = max(0, idx - half)
    end = min(len(combined), idx + len(query) + half)
    chunk = combined[start:end]

    # 매치 마커 삽입
    rel_idx = idx - start
    before = chunk[:rel_idx]
    match = chunk[rel_idx : rel_idx + len(query)]
    after = chunk[rel_idx + len(query) :]

    snippet = f"{'...' if start > 0 else ''}{before}**{match}**{after}{'...' if end < len(combined) else ''}"
    return snippet


def apply_search_permissions(
    *,
    results: list[dict],
    user_role: str,
    user_employee: str | None = None,
    owner_field: str | None = None,
) -> list[dict]:
    """권한 필터 — PII 보호.

    - 관리자(HR Manager, HR User, System Manager, Administrator): 전체 반환
    - 직원(Employee): owner_field 값이 자신의 employee name 인 문서만 반환.
      owner_field 가 None 이면 (예: hr_only doctype) 빈 리스트 반환 (
      hr_only 체크는 global_search 에서 doctype 단위로 이미 처리하지만
      방어적으로 여기서도 차단).
    """
    if _is_admin(user_role):
        return results

    # 일반 직원
    if not owner_field:
        # 소유자 필드가 없는 hr_only 문서 — 접근 금지
        return []

    if not user_employee:
        # 직원 identity 를 알 수 없으면 접근 거부
        return []

    return [r for r in results if r.get(owner_field) == user_employee]


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------


def _format_result(*, doc: dict, meta: dict, query: str) -> dict:
    """문서 dict 를 검색 결과 카드 형식으로 변환."""
    name = doc.get("name", "")
    label = _render_template(meta["result_template"], doc)
    snippet = build_search_snippet(doc=doc, query=query)

    return {
        "name": name,
        "label": label,
        "url": meta["url_template"].format(name=name),
        "pwa_url": meta["pwa_url_template"].format(name=name),
        "snippet": snippet,
        "doctype": meta["label"],
    }


def _render_template(template: str, doc: dict) -> str:
    """'{field}' 형식 템플릿을 doc 값으로 치환. 누락 필드는 빈 문자열."""
    try:
        return template.format_map(_DefaultDict(doc))
    except Exception:
        return template


class _DefaultDict(dict):
    """누락 키를 '' 로 반환하는 dict (format_map 용)."""

    def __missing__(self, key: str) -> str:
        return ""


def _empty_response(*, query: str, elapsed_ms: int) -> dict:
    return {
        "contract_type": "korea_global_search_result_v1",
        "query": query,
        "total_results": 0,
        "results_by_doctype": {},
        "elapsed_ms": elapsed_ms,
    }
