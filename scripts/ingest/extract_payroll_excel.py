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

import importlib.util
import json
import pathlib
import sys

# 파싱·무결성 로직은 hrms 패키지 코어로 승격됨 — 이 스크립트는 thin wrapper.
_CORE_PATH = (
    pathlib.Path(__file__).resolve().parents[2]
    / "hrms" / "regional" / "south_korea" / "payroll_excel.py"
)
_spec = importlib.util.spec_from_file_location("_korea_payroll_excel_core", _CORE_PATH)
_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core)

PROFILES = _core.PROFILES


def extract(path: str, period: str, sheet_type: str = "monthly", sheet: str | None = None) -> dict:
    if sheet_type not in PROFILES:
        raise SystemExit(f"알 수 없는 --sheet-type: {sheet_type} (가능: {', '.join(PROFILES)})")
    try:
        return _core.extract_payroll(path, period, sheet_type, sheet)
    except ValueError as error:
        raise SystemExit(str(error)) from error


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
