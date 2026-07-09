# -*- coding: utf-8 -*-
"""Employee 주민번호 마스킹 자동 파생 (frappe 글루).

전체 주민번호(암호화 Password 필드 `resident_registration_number`)가 새로 입력되면
마스킹 표기 `rrn_masked`를 자동 채운다. 핵심 로직은 framework-free `resident_registration_number`
모듈에 있고, 여기서는 Employee 문서 생명주기에만 연결한다.

**안전 설계 (라이브 Employee 저장에 붙는 훅)**:
- 값이 없거나 변경되지 않았으면 즉시 반환(암호화값을 마스킹하지 않도록).
- 13자리로 파싱되지 않으면 조용히 skip(암호화 blob·부분입력 등).
- **절대 throw 하지 않는다** — 저장을 차단하지 않는다(유효성 강제는 4대보험 신고 플로우에서 별도).
- 유효한 새 전체번호일 때만 rrn_masked 세팅.
"""
import frappe

from hrms.regional.south_korea import resident_registration_number as rrn_core


def derive_rrn_masked(doc, method=None):
	full = doc.get("resident_registration_number")
	if not full:
		return
	# Password 필드: 변경 안 됐으면 DB의 암호화값이므로 건드리지 않는다.
	try:
		changed = doc.is_new() or doc.has_value_changed("resident_registration_number")
	except Exception:  # noqa: BLE001 — 생명주기 API 차이에 대비, 보수적으로 진행
		changed = True
	if not changed:
		return
	try:
		normalized = rrn_core.normalize(full)
	except (ValueError, TypeError):
		return  # 13자리 아님 → skip (throw 안 함)
	if rrn_core.is_valid_rrn(normalized):
		doc.rrn_masked = rrn_core.mask_rrn(normalized)
