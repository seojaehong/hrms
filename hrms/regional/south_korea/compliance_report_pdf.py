"""한국 노무 컴플라이언스 진단 PDF 리포트 생성.

run_full_compliance_diagnosis 결과 dict → HTML → PDF (frappe.utils.pdf.get_pdf).

외부 LLM API 없음. read-only. 진단 결과를 PDF로 포맷팅만 수행.

사용법::

    from hrms.regional.south_korea.compliance_diagnosis_api import run_compliance_diagnosis
    from hrms.regional.south_korea.compliance_report_pdf import generate_compliance_pdf

    diagnosis_result = run_compliance_diagnosis(
        company="위너스",
        workplace="서울지사",
        as_of_date="2026-05-17",
    )
    pdf_bytes = generate_compliance_pdf(diagnosis_result)
    # pdf_bytes를 파일로 저장하거나 HTTP 응답으로 반환
"""

from __future__ import annotations

import html
from typing import Any

import frappe

from hrms.regional.south_korea.compliance_diagnosis import DIAGNOSIS_RULES

# Status → (한국어 레이블, CSS 색상 클래스)
STATUS_DISPLAY: dict[str, tuple[str, str]] = {
    "pass": ("양호", "status-pass"),
    "warn": ("검토필요", "status-warn"),
    "fail": ("위반의심", "status-fail"),
}

OVERALL_STATUS_DISPLAY: dict[str, str] = {
    "good": "컴플라이언스 양호",
    "needs_attention": "일부 항목 검토 필요",
    "high_risk": "즉시 조치 필요",
}

SEVERITY_DISPLAY: dict[str, str] = {
    "high": "높음",
    "medium": "중간",
    "low": "낮음",
}

CSS = """
body { font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif; font-size: 10pt; color: #222; margin: 0; padding: 0; }
h1 { font-size: 16pt; color: #1a3a5c; margin-bottom: 4px; }
h2 { font-size: 12pt; color: #1a3a5c; margin-top: 20px; margin-bottom: 6px; border-bottom: 1px solid #b0c4d8; padding-bottom: 3px; }
h3 { font-size: 10pt; color: #2c5282; margin-top: 14px; margin-bottom: 4px; }
.header-block { background: #f0f5fc; border-left: 4px solid #2b6cb0; padding: 10px 14px; margin-bottom: 18px; }
.meta { font-size: 9pt; color: #555; margin: 2px 0; }
.overall-good { background: #e6f4ea; border: 1px solid #5cb85c; padding: 8px 12px; border-radius: 4px; margin-bottom: 14px; }
.overall-needs_attention { background: #fff8e1; border: 1px solid #f0ad4e; padding: 8px 12px; border-radius: 4px; margin-bottom: 14px; }
.overall-high_risk { background: #fdecea; border: 1px solid #d9534f; padding: 8px 12px; border-radius: 4px; margin-bottom: 14px; }
.status-pass { background: #5cb85c; color: #fff; padding: 2px 8px; border-radius: 3px; font-weight: bold; font-size: 8pt; }
.status-warn { background: #f0ad4e; color: #fff; padding: 2px 8px; border-radius: 3px; font-weight: bold; font-size: 8pt; }
.status-fail { background: #d9534f; color: #fff; padding: 2px 8px; border-radius: 3px; font-weight: bold; font-size: 8pt; }
.category-block { border: 1px solid #dce4ef; border-radius: 4px; padding: 10px 14px; margin-bottom: 12px; }
.category-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.finding-item { background: #fafafa; border-left: 3px solid #d9534f; padding: 5px 10px; margin: 4px 0; font-size: 9pt; }
.finding-item.warn { border-left-color: #f0ad4e; }
.finding-item.unavailable { border-left-color: #aaa; color: #888; }
.recommendation-item { background: #f0f5fc; border-left: 3px solid #2b6cb0; padding: 4px 10px; margin: 3px 0; font-size: 9pt; }
.law-ref { font-size: 8pt; color: #2c5282; margin-left: 6px; }
.severity-high { color: #c0392b; font-weight: bold; }
.severity-medium { color: #e67e22; }
.severity-low { color: #27ae60; }
.summary-box { background: #f7faff; border: 1px solid #b0c4d8; padding: 10px 14px; margin-top: 18px; border-radius: 4px; font-size: 9pt; }
.disclaimer { font-size: 8pt; color: #888; margin-top: 18px; border-top: 1px solid #ddd; padding-top: 8px; }
table { width: 100%; border-collapse: collapse; margin-top: 10px; }
th { background: #2b6cb0; color: #fff; padding: 6px 10px; text-align: left; font-size: 9pt; }
td { padding: 5px 10px; border-bottom: 1px solid #eee; font-size: 9pt; vertical-align: top; }
tr:nth-child(even) td { background: #f7faff; }
"""


def generate_compliance_pdf(
    diagnosis_result: dict[str, Any],
    *,
    print_format: str | None = None,
) -> bytes:
    """진단 결과 dict → PDF bytes.

    Args:
        diagnosis_result: run_full_compliance_diagnosis 반환값.
        print_format: 사용할 Frappe Print Format (None이면 내장 HTML 사용).

    Returns:
        PDF 파일 bytes. Frappe HTTP 응답으로 직접 전달 가능.

    주의:
        - read-only. DB 수정 없음.
        - 점수/확률/숫자 지표 출력 없음.
    """
    html_content = build_compliance_html(diagnosis_result)

    try:
        from frappe.utils.pdf import get_pdf

        return get_pdf(html_content, {"orientation": "Portrait"})
    except ImportError:
        frappe.throw("PDF 생성을 위해 frappe.utils.pdf 모듈이 필요합니다.")


@frappe.whitelist()
def download_compliance_pdf(
    company: str,
    workplace: str = "",
    as_of_date: str | None = None,
) -> None:
    """컴플라이언스 진단 PDF 다운로드 API.

    Frappe HTTP 응답으로 PDF 파일을 직접 반환합니다.

    Args:
        company: 회사명 (필수).
        workplace: 사업장명 (선택).
        as_of_date: 진단 기준일 YYYY-MM-DD (선택).
    """
    from hrms.regional.south_korea.compliance_diagnosis_api import run_compliance_diagnosis

    if not company:
        frappe.throw("company is required")

    diagnosis_result = run_compliance_diagnosis(
        company=company,
        workplace=workplace or "",
        as_of_date=as_of_date,
    )

    pdf_bytes = generate_compliance_pdf(diagnosis_result)

    safe_company = company.replace(" ", "_").replace("/", "-")
    safe_date = (as_of_date or str(frappe.utils.today())).replace("-", "")
    filename = f"compliance_report_{safe_company}_{safe_date}.pdf"

    frappe.local.response.filename = filename
    frappe.local.response.filecontent = pdf_bytes
    frappe.local.response.type = "pdf"


def build_compliance_html(diagnosis_result: dict[str, Any]) -> str:
    """진단 결과 dict → HTML 문자열.

    단독으로도 사용 가능 (테스트, 이메일 발송 등).
    """
    company = _esc(diagnosis_result.get("company", ""))
    workplace = _esc(diagnosis_result.get("workplace", "") or "전사")
    as_of_date = _esc(diagnosis_result.get("as_of_date", ""))
    overall_status = diagnosis_result.get("overall_status", "needs_attention")
    overall_label = OVERALL_STATUS_DISPLAY.get(overall_status, overall_status)
    high_severity = diagnosis_result.get("high_severity_findings", 0)
    rec_summary = _esc(diagnosis_result.get("recommendation_summary", ""))
    diagnoses = diagnosis_result.get("diagnoses", {})

    sections = []

    # 카테고리별 섹션
    for rule_key, rule_meta in DIAGNOSIS_RULES.items():
        result = diagnoses.get(rule_key, {})
        sections.append(_build_category_section(rule_key, rule_meta, result))

    sections_html = "\n".join(sections)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>한국 노무 컴플라이언스 진단 보고서</title>
<style>{CSS}</style>
</head>
<body>
<div class="header-block">
    <h1>한국 노무 컴플라이언스 진단 보고서</h1>
    <p class="meta">회사: <strong>{company}</strong> &nbsp;|&nbsp; 사업장: <strong>{workplace}</strong></p>
    <p class="meta">진단 기준일: <strong>{as_of_date}</strong></p>
    <p class="meta" style="font-size:8pt;color:#999;">이 보고서는 자가 진단 참고용입니다. 최종 법적 판단은 담당자 또는 전문가가 확인하세요.</p>
</div>

<div class="overall-{overall_status}">
    <strong>종합 진단: {_esc(overall_label)}</strong>
    &nbsp;|&nbsp;
    즉시 조치 필요 항목 (high severity): <strong>{high_severity}건</strong>
</div>

<h2>카테고리별 진단 결과</h2>
{sections_html}

<div class="summary-box">
    <strong>종합 권고 요약</strong><br>
    {rec_summary}
</div>

<div class="disclaimer">
    ※ 이 보고서는 Frappe HRMS 시스템에 등록된 데이터를 기반으로 자동 생성된 자가 진단 결과입니다.<br>
    ※ AI 점수/확률 미사용. 발견된 모든 항목은 human-review 대상이며 법적 효력이 없습니다.<br>
    ※ 생성일시: {_esc(str(frappe.utils.now_datetime() if hasattr(frappe, 'utils') else as_of_date))}
</div>
</body>
</html>"""


def _build_category_section(
    rule_key: str,
    rule_meta: dict[str, Any],
    result: dict[str, Any],
) -> str:
    """카테고리 하나의 HTML 섹션 생성."""
    status = result.get("status", "warn")
    status_label, status_class = STATUS_DISPLAY.get(status, (status, "status-warn"))
    severity = rule_meta.get("severity", "medium")
    severity_label = SEVERITY_DISPLAY.get(severity, severity)
    severity_class = f"severity-{severity}"
    name = _esc(rule_meta.get("name", rule_key))
    law = _esc(rule_meta.get("law", ""))

    findings = result.get("findings", [])
    recommendations = result.get("recommendations", [])

    findings_html = _build_findings_html(findings)
    recommendations_html = _build_recommendations_html(recommendations)

    return f"""<div class="category-block">
    <div class="category-header">
        <div>
            <strong>{name}</strong>
            <span class="law-ref">{law}</span>
        </div>
        <div>
            <span class="status-{status}">{status_label}</span>
            &nbsp;
            <span class="{severity_class}" style="font-size:8pt;">위험도: {severity_label}</span>
        </div>
    </div>
    {findings_html}
    {recommendations_html}
</div>"""


def _build_findings_html(findings: list[dict[str, Any]]) -> str:
    if not findings:
        return '<p style="font-size:9pt;color:#5cb85c;">발견된 문제 없음.</p>'

    items = []
    for f in findings:
        issue = _esc(f.get("issue", ""))
        employee_name = _esc(f.get("employee_name", ""))
        data_unavailable = f.get("data_unavailable", False)

        css_class = "finding-item unavailable" if data_unavailable else "finding-item"
        prefix = f"[{employee_name}] " if employee_name else ""
        items.append(f'<div class="{css_class}">{prefix}{issue}</div>')

    return "\n".join(items)


def _build_recommendations_html(recommendations: list[str]) -> str:
    if not recommendations:
        return ""

    items = [
        f'<div class="recommendation-item">{_esc(r)}</div>'
        for r in recommendations
    ]
    return (
        '<div style="margin-top:8px;"><strong style="font-size:9pt;">권고사항</strong><br>'
        + "\n".join(items)
        + "</div>"
    )


def _esc(value: Any) -> str:
    """HTML 이스케이프."""
    return html.escape(str(value or ""))
