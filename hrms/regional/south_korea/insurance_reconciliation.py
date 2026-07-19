# -*- coding: utf-8 -*-
"""4대보험 고지내역 대사(Reconciliation) — framework-free 코어.

우리 급여엔진이 계산한 직원별 보험료와 공단 고지내역을 1원 단위로 대조해
차이를 명단으로 드러낸다. 실사고 근거: 쿠우쿠우 동탄점 국민연금 4.75% 역산
과다공제(+21,230원)가 사람 눈으로만 발견됐다 — 이 대사가 시스템으로 잡는다.

데이터 소스 불문: 고지내역은 CODEF 조회(insurance_inquiry_api)든 공단 xlsx 수동
업로드든, 아래 표준 행 형태로 정규화해 주입한다.

표준 행: {"employee": str(또는 rrn/사번 등 일치 키), "national_pension": 원,
          "health_insurance": 원, "long_term_care_insurance": 원, "employment_insurance": 원}
— 금액 키는 일부만 있어도 된다(있는 키만 대조).

원칙:
- 기본 허용오차 1원 (원단위절사 노이즈 흡수). |delta|<=tolerance 는 within_tolerance=True 로
  남되 불일치로 세지 않는다. tolerance=0 을 명시하면 1원 단위 엄격 검증(옛 동작).
- 차이·누락을 절대 숨기지 않는다: diffs / missing_in_notified / missing_in_computed 전부 반환.
- 계산 전용 — 조회·저장 없음.

실행 검증: python3 hrms/tests/test_korea_insurance_reconciliation.py
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

# 대조 대상 금액 필드 (직원 부담분 기준)
CONTRIBUTION_FIELDS = (
	"national_pension",
	"health_insurance",
	"long_term_care_insurance",
	"employment_insurance",
)

FIELD_LABELS_KO = {
	"national_pension": "국민연금",
	"health_insurance": "건강보험",
	"long_term_care_insurance": "장기요양보험",
	"employment_insurance": "고용보험",
}


def _to_won(value: Any, name: str) -> int:
	if value is None or value == "":
		raise ValueError(f"{name} is empty")
	try:
		dec = Decimal(str(value))
	except Exception as exc:  # noqa: BLE001
		raise ValueError(f"{name} must be numeric: {value!r}") from exc
	if dec != dec.to_integral_value():
		raise ValueError(f"{name} must be an integer KRW amount: {value!r}")
	return int(dec)


def _key_of(row: dict[str, Any]) -> str:
	key = str(row.get("employee") or "").strip()
	if not key:
		raise ValueError(f"row missing employee key: {row!r}")
	return key


def reconcile_contributions(
	computed: list[dict[str, Any]],
	notified: list[dict[str, Any]],
	*,
	tolerance: int = 1,
	fields: tuple[str, ...] = CONTRIBUTION_FIELDS,
) -> dict[str, Any]:
	"""직원별 보험료 대사.

	Args:
		computed: 우리 엔진 계산분 (표준 행 리스트).
		notified: 공단 고지분 (표준 행 리스트).
		tolerance: 허용 오차(원). 기본 1 — 원단위절사(원단위 절사) 노이즈를 흡수한다.
			차이가 있어도 |delta| <= tolerance 면 diff 행은 남되 within_tolerance=True 로
			표시(불일치 아님). tolerance=0 을 명시하면 옛 엄격 동작(1원도 불일치).
		fields: 대조할 금액 필드(기본 4대 전체). 양쪽 모두 값이 있는 필드만 대조.

	Returns:
		{
			"ok": bool,                      # 허용오차 초과 diff 0건 & 누락 0건
			"match_count": int,              # 필드 단위 일치 수(허용오차 내 포함)
			"diffs": [ {employee, field, label, computed, notified, delta, within_tolerance} ... ],
			"missing_in_notified": [employee...],  # 우리에겐 있는데 고지에 없음
			"missing_in_computed": [employee...],  # 고지에 있는데 우리 계산에 없음
			"totals": {field: {"computed": 합, "notified": 합, "delta": 차}},
			"tolerance": int,
		}

	delta = computed - notified (양수 = 우리가 더 걷음 = 과다공제 의심).
	"""
	if tolerance < 0:
		raise ValueError("tolerance must be >= 0")

	computed_by = {}
	for row in computed:
		key = _key_of(row)
		if key in computed_by:
			raise ValueError(f"computed에 중복 직원 키: {key}")
		computed_by[key] = row
	notified_by = {}
	for row in notified:
		key = _key_of(row)
		if key in notified_by:
			raise ValueError(f"notified에 중복 직원 키: {key}")
		notified_by[key] = row

	diffs: list[dict[str, Any]] = []
	match_count = 0
	totals: dict[str, dict[str, int]] = {f: {"computed": 0, "notified": 0, "delta": 0} for f in fields}

	shared = [k for k in computed_by if k in notified_by]
	for key in shared:
		c_row, n_row = computed_by[key], notified_by[key]
		for field in fields:
			c_val, n_val = c_row.get(field), n_row.get(field)
			if c_val in (None, "") or n_val in (None, ""):
				continue  # 한쪽에 없는 필드는 대조 대상 아님
			c_won = _to_won(c_val, f"computed.{key}.{field}")
			n_won = _to_won(n_val, f"notified.{key}.{field}")
			delta = c_won - n_won
			totals[field]["computed"] += c_won
			totals[field]["notified"] += n_won
			totals[field]["delta"] += delta
			if abs(delta) <= tolerance:
				match_count += 1
			if delta != 0:
				diffs.append({
					"employee": key,
					"field": field,
					"label": FIELD_LABELS_KO.get(field, field),
					"computed": c_won,
					"notified": n_won,
					"delta": delta,
					"within_tolerance": abs(delta) <= tolerance,
				})

	missing_in_notified = sorted(k for k in computed_by if k not in notified_by)
	missing_in_computed = sorted(k for k in notified_by if k not in computed_by)

	# 과다공제 의심(delta>0)이 먼저 보이도록 |delta| 내림차순 정렬
	diffs.sort(key=lambda d: (-abs(d["delta"]), d["employee"], d["field"]))

	real_mismatch = any(not d["within_tolerance"] for d in diffs)
	return {
		"ok": not real_mismatch and not missing_in_notified and not missing_in_computed,
		"match_count": match_count,
		"diffs": diffs,
		"missing_in_notified": missing_in_notified,
		"missing_in_computed": missing_in_computed,
		"totals": totals,
		"tolerance": tolerance,
	}


# 공제 컴포넌트명 → 표준행 키 (포함 매칭, 순서 중요: "장기요양"이 "건강보험"보다 먼저 —
# wage_statement._DEDUCTION_KEY_RULES와 동일 원칙, 4대보험 부분만)
_COMPONENT_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
	("national_pension", ("국민연금",)),
	("long_term_care_insurance", ("장기요양",)),
	("health_insurance", ("건강보험",)),
	("employment_insurance", ("고용보험",)),
)


def contribution_rows_from_slips(slips: list[dict[str, Any]]) -> dict[str, Any]:
	"""급여 슬립(공제 목록 포함) → 대사 표준행.

	Args:
		slips: [{"employee": str, "deductions": [{"salary_component"|"label": str, "amount": 원}...]}]
			동일 직원의 같은 보험 컴포넌트가 여러 줄이면 합산.

	Returns:
		{"rows": [표준행...], "unmapped": [{"employee", "component", "amount"}...]}
		unmapped = 4대보험으로 분류되지 않은 공제(소득세 등은 정상적으로 여기 옴 — 정보용).
	"""
	rows: list[dict[str, Any]] = []
	unmapped: list[dict[str, Any]] = []
	for slip in slips:
		key = _key_of(slip)
		row: dict[str, Any] = {"employee": key}
		for ded in slip.get("deductions") or []:
			name = ""
			for k in ("salary_component", "label", "component"):
				v = ded.get(k)
				if isinstance(v, str) and v.strip():
					name = v.strip()
					break
			amount = ded.get("amount")
			if amount in (None, ""):
				continue
			won = int(round(float(amount)))
			matched = None
			for field, patterns in _COMPONENT_RULES:
				if any(p in name for p in patterns):
					matched = field
					break
			if matched:
				row[matched] = row.get(matched, 0) + won
			else:
				unmapped.append({"employee": key, "component": name, "amount": won})
		rows.append(row)
	return {"rows": rows, "unmapped": unmapped}


def summarize_reconciliation_ko(result: dict[str, Any]) -> str:
	"""사람용 1줄 요약 (텔레그램/보고서용)."""
	if result["ok"]:
		return f"고지 대사 일치 — {result['match_count']}건 전부 1원 단위 일치"
	parts = []
	# 원단위절사 노이즈(within_tolerance)는 불일치로 세지 않는다 — 진짜 차이만 요약.
	mismatches = [d for d in result["diffs"] if not d.get("within_tolerance")]
	if mismatches:
		over = sum(1 for d in mismatches if d["delta"] > 0)
		under = len(mismatches) - over
		total_delta = sum(d["delta"] for d in mismatches)
		parts.append(f"차이 {len(mismatches)}건(과다 {over}·과소 {under}, 합계 {total_delta:+,}원)")
	if result["missing_in_notified"]:
		parts.append(f"고지 누락 {len(result['missing_in_notified'])}명")
	if result["missing_in_computed"]:
		parts.append(f"계산 누락 {len(result['missing_in_computed'])}명")
	return "고지 대사 불일치 — " + " · ".join(parts)
