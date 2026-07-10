# -*- coding: utf-8 -*-
"""에이전트 자동 프로비저닝 — 순수 코어.

가입 시 에이전트 개통(서비스유저·계산전용토큰·site_config·채널바인딩)을
'실행할 스텝을 데이터로 표현'하는 순수 함수 모음. frappe 를 import 하지 않고
부수효과가 없으므로 spec_from_file_location 으로 직접 로드해 테스트한다.

site_config 키는 hrms/regional/south_korea/agent_harness_api.py 와 일치:
  korea_agent_harness_provider / hermes_gateway_url.
"""

from __future__ import annotations

import copy

# agent_harness_api.PROVIDER_CONFIG_KEY / HERMES_GATEWAY_URL_KEY 와 동일 값.
# (해당 모듈은 frappe 연쇄 import 라 여기서 import 하지 않고 상수만 복제.)
PROVIDER_CONFIG_KEY = "korea_agent_harness_provider"
HERMES_GATEWAY_URL_KEY = "hermes_gateway_url"


def build_agent_provisioning_plan(
	site,
	*,
	telegram_chat_id=None,
	provider="hermes",
	gateway_url=None,
):
	"""프로비저닝 실행 스텝을 dict 리스트로 반환하는 순수 함수(부수효과 0).

	스텝 순서: ensure_service_user → issue_mcp_token → set_site_config
	(+ telegram_chat_id 있으면 bind_channel).
	잘못된 인자(빈 site / gateway_url 누락)는 ValueError.
	"""
	site = (site or "").strip()
	if not site:
		raise ValueError("site 는 비어 있을 수 없습니다.")
	gateway_url = (gateway_url or "").strip()
	if not gateway_url:
		raise ValueError("gateway_url 은 필수입니다.")

	plan = [
		{
			"action": "ensure_service_user",
			"email": f"agent-bot@{site}",
			"roles": ["System Manager"],
		},
		{
			"action": "issue_mcp_token",
			"site": site,
			"scope": "calc_only",
			"label": f"agent-bot@{site}",
		},
		{
			"action": "set_site_config",
			"keys": {
				PROVIDER_CONFIG_KEY: provider,
				HERMES_GATEWAY_URL_KEY: gateway_url,
			},
		},
	]
	if telegram_chat_id is not None:
		plan.append(
			{
				"action": "bind_channel",
				"channel": "telegram",
				"chat_id": telegram_chat_id,
			}
		)
	return plan


def merge_channel_binding(bindings, chat_id, site, credentials):
	"""채널 바인딩 dict 에 항목을 추가/갱신한 새 dict 를 반환(순수·멱등).

	깊은 복사로 원본 bindings 는 불변. 이미 있으면 site·자격만 갱신하므로
	같은 인자로 두 번 호출해도 결과가 동일(멱등). 시크릿 값은 그대로 저장하고,
	로깅용 마스킹은 mask_binding 로 분리한다.
	"""
	result = copy.deepcopy(bindings or {})
	key = str(chat_id)
	entry = dict(result.get(key) or {})
	entry["site"] = site
	entry.update(credentials or {})
	result[key] = entry
	return result


def mask_binding(b):
	"""바인딩 dict 의 시크릿을 마스킹한 새 dict 반환(원본 불변).

	api_secret 이 있으면 '***' 로 치환한다. api_key 등 비밀 아닌 값은 유지.
	"""
	masked = copy.deepcopy(b or {})
	if "api_secret" in masked:
		masked["api_secret"] = "***"
	return masked


def check_agent_provisioning(binding, site_config):
	"""바인딩·site_config 만으로 개통 완비 여부를 판정(순수·주입식, 라이브 조회 없음).

	반환 {'ready': bool, 'missing': [...]}. 부족한 것을 missing 에 나열한다:
	binding 의 api_key/api_secret/frappe_url, site_config 의 provider/gateway_url.
	"""
	binding = binding or {}
	site_config = site_config or {}
	missing = []
	for field in ("api_key", "api_secret", "frappe_url"):
		if not binding.get(field):
			missing.append(field)
	if not site_config.get(PROVIDER_CONFIG_KEY):
		missing.append("provider")
	if not site_config.get(HERMES_GATEWAY_URL_KEY):
		missing.append("gateway_url")
	return {"ready": not missing, "missing": missing}
