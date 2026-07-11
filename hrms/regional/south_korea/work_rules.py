"""Framework-free South Korea 취업규칙(work rules) judgment helpers.

개인 스킬 취업규칙검토·취업규칙개정·취업규칙의견서(HWP 중심 로컬 워크플로우)의
판단 규칙을 에이전트가 쓸 수 있는 framework-free 함수로 이식한 모듈이다.
생성·HWP 렌더링은 여전히 개인 스킬이 담당하고(docs/korea_hrms/payroll-skills-bridge.md
참조), 이 모듈은 필수기재 점검·신고의무·절차 판정·불이익변경 candidate 판정만 맡는다.

근거 법령 (mcp__korean-law__get_law_text, mst=265959 근로기준법, 확인일 2026-07-11,
공포 2024-10-22 / 시행 2025-10-23 현행본 — 조문이 위 API로 실확인됨, "원문 검수 필요"
표기 불필요):

- 근로기준법 제93조(취업규칙의 작성ㆍ신고) — 상시 10명 이상 근로자 사용 사업장은
  각 호 사항에 관한 취업규칙을 작성해 고용노동부장관에게 신고해야 한다.
- 근로기준법 제94조(규칙의 작성, 변경 절차) — 과반수 노동조합(없으면 근로자 과반수)의
  의견을 들어야 하고, 불리하게 변경하는 경우에는 동의를 받아야 한다. 신고 시 의견을
  적은 서면을 첨부해야 한다.
- 근로기준법 제95조(제재 규정의 제한) — 감급 제재 한도(1회 평균임금 1일분의 2분의 1,
  총액 1임금지급기 임금 총액의 10분의 1). 본 모듈에서는 참고 상수로만 노출한다.
- 근로기준법 제14조(법령 주요 내용 등의 게시) — 취업규칙을 근로자가 자유롭게 열람할
  수 있는 장소에 항상 게시하거나 갖추어 두어야 한다.

이 모듈은 불이익변경 해당 여부·필수기재 있음/불충분/누락의 최종 판단을 내리지
않는다(설계서 §8, 개인 스킬 diff-engine-규칙.md §5와 동일 원칙). 키워드 매칭에
의한 candidate 판정만 반환하고, 항상 사람(노무사) 확인 플래그를 동봉한다.
"""

from __future__ import annotations

from typing import Any

# 근로기준법 제93조 각 호 — 9의2를 포함해 14개 항목.
# keywords: check_required_items의 커버리지 판정에 쓰는 키워드 후보(OR 매칭).
# 개인 스킬 references/근기법-93조-체크리스트.md의 "점검 포인트" 열과 대조해 확정.
WORK_RULES_REQUIRED_ITEMS: tuple[dict[str, Any], ...] = (
	{
		"ho": "1",
		"label": "업무 시작·종료 시각, 휴게시간, 휴일, 휴가, 교대근로",
		"keywords": ("시작", "종료", "휴게", "휴일", "휴가", "교대"),
	},
	{
		"ho": "2",
		"label": "임금의 결정·계산·지급 방법, 산정기간, 지급시기, 승급",
		"keywords": ("임금", "지급", "산정기간", "승급"),
	},
	{
		"ho": "3",
		"label": "가족수당의 계산·지급 방법",
		"keywords": ("가족수당",),
	},
	{
		"ho": "4",
		"label": "퇴직에 관한 사항",
		"keywords": ("퇴직",),
	},
	{
		"ho": "5",
		"label": "퇴직급여(근퇴법 §4)·상여·최저임금",
		"keywords": ("퇴직급여", "퇴직금", "상여", "최저임금"),
	},
	{
		"ho": "6",
		"label": "근로자의 식비·작업용품 등 부담",
		"keywords": ("식비", "작업용품", "작업 용품"),
	},
	{
		"ho": "7",
		"label": "근로자를 위한 교육시설",
		"keywords": ("교육시설",),
	},
	{
		"ho": "8",
		"label": "출산전후휴가·육아휴직 등 모성보호·일가정 양립",
		"keywords": ("출산전후휴가", "육아휴직", "모성보호", "일가정"),
	},
	{
		"ho": "9",
		"label": "안전과 보건",
		"keywords": ("안전", "보건"),
	},
	{
		"ho": "9의2",
		"label": "성별·연령·신체조건 등 특성에 따른 사업장 환경 개선",
		"keywords": ("성별", "신체적 조건", "특성에 따른", "사업장 환경"),
	},
	{
		"ho": "10",
		"label": "업무상·업무 외 재해부조",
		"keywords": ("재해부조", "재해보상"),
	},
	{
		"ho": "11",
		"label": "직장 내 괴롭힘의 예방 및 발생 시 조치",
		"keywords": ("괴롭힘",),
	},
	{
		"ho": "12",
		"label": "표창과 제재",
		"keywords": ("표창", "제재", "징계"),
	},
	{
		"ho": "13",
		"label": "그 밖에 근로자 전체에 적용될 사항",
		"keywords": ("전체에 적용", "그 밖에"),
	},
)

_REQUIRED_HO_SET = {item["ho"] for item in WORK_RULES_REQUIRED_ITEMS}
assert len(_REQUIRED_HO_SET) == len(WORK_RULES_REQUIRED_ITEMS)  # ho 중복 없음


def check_required_items(rules_outline: dict[str, str] | list[str]) -> dict[str, Any]:
	"""근기법 §93 14개 호가 취업규칙 개요에 커버되는지 키워드로 candidate 판정한다.

	rules_outline:
	  - dict: {"1": "조문 텍스트...", "9의2": "..."} 처럼 호 번호를 키로 준 형태.
	    키는 판정에 쓰지 않고(참고용) 값 텍스트만 전 항목 대조에 사용한다.
	  - list: 조문 텍스트 문자열의 리스트. 순서 무관, 전부 이어붙여 대조한다.

	반환값은 있음/불충분의 세밀한 구분(개인 스킬 Step 3의 사람 판단 영역) 없이
	"키워드가 발견되었는가"만의 candidate 결과다. 최종 확정은 사람이 한다.
	"""

	if isinstance(rules_outline, dict):
		haystack = "\n".join(str(v) for v in rules_outline.values())
	elif isinstance(rules_outline, list):
		haystack = "\n".join(str(v) for v in rules_outline)
	else:
		raise TypeError("rules_outline must be a dict or a list of strings")

	covered: list[dict[str, Any]] = []
	missing: list[dict[str, Any]] = []
	for item in WORK_RULES_REQUIRED_ITEMS:
		matched = [kw for kw in item["keywords"] if kw in haystack]
		if matched:
			covered.append({"ho": item["ho"], "label": item["label"], "matched_keywords": matched})
		else:
			missing.append({"ho": item["ho"], "label": item["label"]})

	total = len(WORK_RULES_REQUIRED_ITEMS)
	coverage_ratio = len(covered) / total if total else 0.0
	return {
		"covered": covered,
		"missing": missing,
		"coverage_ratio": coverage_ratio,
		"note": "키워드 candidate 판정 — 있음/불충분 확정은 사람이 원문을 검수할 것",
	}


def filing_obligation(headcount: int) -> dict[str, Any]:
	"""상시 근로자 수 기준 취업규칙 작성·신고 의무 여부 (근로기준법 제93조)."""

	if not isinstance(headcount, int) or isinstance(headcount, bool):
		raise TypeError("headcount must be an int")
	if headcount < 0:
		raise ValueError("headcount cannot be negative")

	required = headcount >= 10
	return {
		"headcount": headcount,
		"required": required,
		"legal_basis": "근로기준법 제93조",
		"note": (
			"상시 10명 이상 근로자 사용 사업장은 취업규칙을 작성해 고용노동부장관에게 신고해야 한다."
			if required
			else "상시 10명 미만은 신고 의무는 없으나, 작성 시 §93 14호 기준으로 점검 권장."
		),
	}


def amendment_procedure(
	is_disadvantageous: bool,
	*,
	has_majority_union: bool | None = None,
) -> dict[str, Any]:
	"""취업규칙 작성·변경 절차 (근로기준법 제94조).

	불이익변경이면 동의, 아니면 의견청취만 필요하다. 대상은 근로자 과반수로 조직된
	노동조합이 있으면 그 노동조합, 없으면 근로자 과반수다. `has_majority_union`이
	None이면(미확인) 대상을 조건부 문구로 표시한다.
	"""

	if has_majority_union is True:
		subject = "과반수 노동조합(근로자의 과반수로 조직된 노동조합)"
	elif has_majority_union is False:
		subject = "근로자 과반수"
	else:
		subject = "과반수 노동조합(있는 경우) 또는 근로자 과반수(없는 경우)"

	if is_disadvantageous:
		requirement = "consent"
		action_verb = "동의를 받아야 한다"
	else:
		requirement = "opinion_hearing"
		action_verb = "의견을 들어야 한다"

	steps = [
		f"{subject}의 {action_verb} (근로기준법 제94조제1항)",
		"의견 또는 동의 내용을 적은 서면을 작성한다",
		"취업규칙 신고 시 위 서면을 첨부한다 (근로기준법 제94조제2항)",
		"신고 후 근로자가 자유롭게 열람할 수 있는 장소에 게시한다 (근로기준법 제14조제1항)",
	]

	return {
		"is_disadvantageous": is_disadvantageous,
		"requirement": requirement,
		"subject": subject,
		"legal_basis": "근로기준법 제94조제1항",
		"steps": steps,
		"note": "불이익변경 해당 여부 자체는 이 함수의 입력값으로 전제할 뿐, 판정하지 않는다.",
	}


_CLASSIFY_KINDS = {"higher_is_favorable", "lower_is_favorable"}


def classify_amendment(*, old_item: Any, new_item: Any, kind: str) -> dict[str, Any]:
	"""취업규칙 개정 전/후 항목의 불이익변경 candidate 판정 (단정 아님).

	kind:
	  - "higher_is_favorable": 값이 클수록 근로자에게 유리(예: 임금·수당·휴가일수)
	  - "lower_is_favorable": 값이 작을수록 근로자에게 유리(예: 소정근로시간·징계 하한)

	old_item/new_item이 숫자가 아니면(문구 변경 등) 방향 비교가 불가능하므로
	candidate="indeterminate"로 반환한다. 어떤 경우든 `requires_labor_attorney_review`는
	항상 True다 — 이 함수는 불이익변경 해당 여부를 단정하지 않는다(개인 스킬
	diff-engine-규칙.md §5의 보수적 원칙과 동일).
	"""

	if kind not in _CLASSIFY_KINDS:
		raise ValueError(f"kind must be one of {sorted(_CLASSIFY_KINDS)}")

	old_is_numeric = isinstance(old_item, (int, float)) and not isinstance(old_item, bool)
	new_is_numeric = isinstance(new_item, (int, float)) and not isinstance(new_item, bool)

	if not (old_is_numeric and new_is_numeric):
		return {
			"candidate": "indeterminate",
			"requires_labor_attorney_review": True,
			"kind": kind,
			"note": "old_item/new_item이 숫자가 아니어서 방향 비교 불가 — 원문 검수 필요",
		}

	delta = float(new_item) - float(old_item)
	if delta == 0:
		candidate = "neutral"
	elif kind == "higher_is_favorable":
		candidate = "favorable" if delta > 0 else "unfavorable"
	else:  # lower_is_favorable
		candidate = "favorable" if delta < 0 else "unfavorable"

	return {
		"candidate": candidate,
		"requires_labor_attorney_review": True,
		"kind": kind,
		"delta": delta,
		"note": "candidate 판정일 뿐 불이익변경 해당 여부의 확정이 아니다 — 노무사 확인 필요",
	}


__all__ = [
	"WORK_RULES_REQUIRED_ITEMS",
	"amendment_procedure",
	"check_required_items",
	"classify_amendment",
	"filing_obligation",
]
