# 기존 급여대장 엑셀 → 시스템 임포트용 JSON 추출 (기존 데이터 임베딩 1/2).
#
# 노무법인 표준 급여대장 포맷(노호 5월분으로 실검증)을 파싱한다.
# 시트 종류(--sheet-type)별로 컬럼 매핑 프로파일을 골라 파싱한다.
#   - monthly  : 월급제 '급여(직원)' 시트 (기본, 32/32 1원 일치)
#   - parttime : 시급제 '파트타임' 시트
# 사용:
#   python3 scripts/ingest/extract_payroll_excel.py "<급여대장.xlsx>" 2026-05 > payroll.json
#   python3 scripts/ingest/extract_payroll_excel.py "<급여대장.xlsx>" 2026-05 --sheet-type parttime
#   python3 scripts/ingest/extract_payroll_excel.py "<급여대장.xlsx>" 2026-05 --sheet "다른시트명"
# 출력 JSON: {period, count, employees: [{name, dept, join, email, earnings{}, deductions{},
#            expected_gross, expected_ded, expected_net}]}
# 추출 후 반드시 내부 무결성(earnings 합=세전, 세전-공제=실지급)을 검사하고 불일치면 실패한다.
#
# 주민번호는 추출하지 않는다 (신고서 생성 단계에서만 별도 취급).

from __future__ import annotations

import json
import sys

import openpyxl

# 시트 종류별 컬럼 매핑 프로파일 (1-base 인덱스). 다른 포맷은 프로파일만 추가.
PROFILES = {
    # 월급제 '급여(직원)' 시트 — 노호 5월 32명 1원 일치.
    "monthly": {
        "sheet": "급여(직원)",
        "cols": {"dept": 2, "name": 3, "join": 8, "email": 14,
                 "gross": 31, "ded_total": 38, "net": 39},
        "earnings": {
            20: "기본급", 21: "고정연장수당", 22: "고정야간수당", 23: "고정휴일수당",
            24: "고정휴일연장수당", 25: "연차선지급", 26: "식대(비과세)", 27: "보안수당",
            28: "근로자의날추가지급", 29: "초과근무수당", 30: "전월미지급",
        },
        "deductions": {32: "소득세", 33: "지방소득세", 34: "국민연금", 35: "건강보험", 36: "장기요양", 37: "고용보험"},
    },
    # 시급제 '파트타임' 시트 — U~X=지급, Y=세전합계, Z~AE=공제, AF=공제합계, AG=차인지급액.
    "parttime": {
        "sheet": "파트타임",
        "cols": {"dept": 2, "name": 3, "join": 8, "email": 14,
                 "gross": 25, "ded_total": 32, "net": 33},
        "earnings": {21: "기본급", 22: "주휴수당", 23: "근로자의날추가지급", 24: "기타수당"},
        "deductions": {26: "소득세", 27: "지방소득세", 28: "국민연금", 29: "건강보험", 30: "장기요양", 31: "고용보험"},
    },
}


def extract(path: str, period: str, sheet_type: str = "monthly", sheet: str | None = None) -> dict:
    if sheet_type not in PROFILES:
        raise SystemExit(f"알 수 없는 --sheet-type: {sheet_type} (가능: {', '.join(PROFILES)})")
    profile = PROFILES[sheet_type]
    cols = profile["cols"]
    earning_cols = profile["earnings"]
    deduction_cols = profile["deductions"]

    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb[sheet or profile["sheet"]]

    SUMMARY_NAMES = {"합계", "총계", "소계", "계"}

    def num(r: int, c: int) -> int:
        v = ws.cell(r, c).value
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            return 0
        return int(round(float(v)))

    employees = []
    for r in range(2, ws.max_row + 1):
        name = ws.cell(r, cols["name"]).value
        if not name:
            continue
        if str(name).strip() in SUMMARY_NAMES:
            continue  # 합계행은 자기일관이라 무결성 검사를 통과하므로 반드시 이름으로 스킵
        earnings = {label: num(r, c) for c, label in earning_cols.items() if num(r, c)}
        deductions = {label: num(r, c) for c, label in deduction_cols.items() if num(r, c)}
        employees.append(
            {
                "name": str(name).strip(),
                "dept": str(ws.cell(r, cols["dept"]).value or "").strip(),
                "join": str(ws.cell(r, cols["join"]).value)[:10] if ws.cell(r, cols["join"]).value else "",
                "email": str(ws.cell(r, cols["email"]).value or "").strip(),
                "earnings": earnings,
                "deductions": deductions,
                "expected_gross": num(r, cols["gross"]),
                "expected_ded": num(r, cols["ded_total"]),
                "expected_net": num(r, cols["net"]),
            }
        )

    errors = []
    for e in employees:
        if not e["earnings"] and e["expected_gross"] == 0 and e["expected_net"] == 0:
            errors.append(f"{e['name']}: 숫자 셀 없음 — 텍스트 서식 행 의심 (0원 시드 방지)")
            continue
        if sum(e["earnings"].values()) != e["expected_gross"]:
            errors.append(f"{e['name']}: earnings 합 != 세전")
        if e["expected_gross"] - sum(e["deductions"].values()) != e["expected_net"]:
            errors.append(f"{e['name']}: 세전-공제 != 실지급")
    if errors:
        raise SystemExit("무결성 실패 (엑셀이 권위 — 매핑을 점검하라):\n" + "\n".join(errors))

    return {"period": period, "count": len(employees), "employees": employees}


def _parse_args(argv: list[str]) -> dict:
    positional, sheet_type, sheet = [], "monthly", None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--sheet-type":
            i += 1
            sheet_type = argv[i]
        elif a == "--sheet":
            i += 1
            sheet = argv[i]
        else:
            positional.append(a)
        i += 1
    if len(positional) < 2:
        raise SystemExit(__doc__)
    return {"path": positional[0], "period": positional[1], "sheet_type": sheet_type, "sheet": sheet}


if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
    opts = _parse_args(sys.argv[1:])
    data = extract(opts["path"], opts["period"], opts["sheet_type"], opts["sheet"])
    print(json.dumps(data, ensure_ascii=False, indent=1))
