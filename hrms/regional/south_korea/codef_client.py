# -*- coding: utf-8 -*-
"""CODEF(코드에프) API 클라이언트 — 4대보험 조회용 (framework-free).

CODEF 공통 규격:
- 토큰: POST https://oauth.codef.io/oauth/token (client_credentials, Basic 인증)
- 데모:  https://development.codef.io + 데모 client_id/secret (심사 전, 고정 테스트데이터)
- 정식:  https://api.codef.io + 정식 키 (심사 후)
- 요청 본문의 비밀번호류 필드는 CODEF 발급 RSA 공개키로 암호화(EasyCodef 규격).
- 응답 result.code == "CF-00000" 이 성공.

설계:
- transport 주입(callable) — 실HTTP 없이 테스트 가능. 기본 transport는 requests 지연 import.
- 자격증명이 없으면 어떤 네트워크 호출도 하지 않고 CodefNotConfigured (fail-closed).
- 상품 경로는 상수로 두되 인자로 오버라이드 가능(계약 상품에 따라 경로가 다름).

참조: docs/korea_hrms/research-4insure-private-api.md §2.1, §7 Phase 1.
"""
from __future__ import annotations

import base64
import json
import time
from typing import Any, Callable

OAUTH_URL = "https://oauth.codef.io/oauth/token"
API_BASE_DEMO = "https://development.codef.io"
API_BASE_PROD = "https://api.codef.io"

# 4대사회보험 정보연계센터 — 사업장 가입자 명부 (연구보고서 §2.1; 계약 상품에 따라 조정)
PRODUCT_INSURED_ROSTER = "/v1/kr/public/pp/nps-minwon/insured-list"

SUCCESS_CODE = "CF-00000"


class CodefError(RuntimeError):
	"""CODEF 호출 실패 (전송·인증·업무 오류 공통)."""

	def __init__(self, message: str, *, code: str | None = None, raw: Any = None):
		super().__init__(message)
		self.code = code
		self.raw = raw


class CodefNotConfigured(CodefError):
	"""자격증명 미설정 — 네트워크 호출 전에 발생 (fail-closed)."""


def _default_transport(method: str, url: str, headers: dict, body: bytes, timeout: int) -> tuple[int, bytes]:
	"""기본 HTTP 전송 (requests 지연 import — framework-free 테스트에서 불필요)."""
	import requests  # noqa: PLC0415

	resp = requests.request(method, url, headers=headers, data=body, timeout=timeout)
	return resp.status_code, resp.content


class CodefClient:
	"""토큰 발급 + 상품 호출. demo=True면 데모 서버.

	Args:
		client_id / client_secret: CODEF 발급 키 (데모 키 가능).
		demo: True → development.codef.io (데모 키 전용).
		transport: (method, url, headers, body, timeout) -> (status, content). 테스트 주입용.
	"""

	def __init__(
		self,
		client_id: str | None,
		client_secret: str | None,
		*,
		demo: bool = True,
		transport: Callable[..., tuple[int, bytes]] | None = None,
		timeout: int = 60,
	):
		self.client_id = (client_id or "").strip()
		self.client_secret = (client_secret or "").strip()
		self.base = API_BASE_DEMO if demo else API_BASE_PROD
		self.demo = demo
		self._transport = transport or _default_transport
		self._timeout = timeout
		self._token: str | None = None
		self._token_expiry: float = 0.0

	# -- 자격증명 ------------------------------------------------------------
	def is_configured(self) -> bool:
		return bool(self.client_id and self.client_secret)

	def _require_configured(self) -> None:
		if not self.is_configured():
			raise CodefNotConfigured(
				"CODEF 자격증명이 없습니다 — site_config(codef_client_id/codef_client_secret) "
				"또는 환경변수(CODEF_CLIENT_ID/CODEF_CLIENT_SECRET)를 설정하세요."
			)

	# -- 토큰 ---------------------------------------------------------------
	def get_token(self, force: bool = False) -> str:
		self._require_configured()
		if self._token and not force and time.monotonic() < self._token_expiry:
			return self._token
		basic = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
		status, content = self._transport(
			"POST",
			OAUTH_URL,
			{
				"Authorization": f"Basic {basic}",
				"Content-Type": "application/x-www-form-urlencoded",
			},
			b"grant_type=client_credentials&scope=read",
			self._timeout,
		)
		if status != 200:
			raise CodefError(f"CODEF 토큰 발급 실패 (HTTP {status})", raw=content[:500])
		data = json.loads(content)
		token = data.get("access_token")
		if not token:
			raise CodefError("CODEF 토큰 응답에 access_token 없음", raw=data)
		self._token = token
		# 만료 여유 60초
		self._token_expiry = time.monotonic() + max(60, int(data.get("expires_in", 3600)) - 60)
		return token

	# -- 상품 호출 -----------------------------------------------------------
	def request_product(self, product_path: str, payload: dict[str, Any]) -> dict[str, Any]:
		"""상품 API 호출. CODEF 응답은 URL-인코딩된 JSON — 디코딩 후 result.code 검사."""
		token = self.get_token()
		status, content = self._transport(
			"POST",
			self.base + product_path,
			{
				"Authorization": f"Bearer {token}",
				"Content-Type": "application/json",
			},
			json.dumps(payload, ensure_ascii=False).encode(),
			self._timeout,
		)
		if status == 401:
			# 토큰 만료 — 1회 재발급 후 재시도
			token = self.get_token(force=True)
			status, content = self._transport(
				"POST",
				self.base + product_path,
				{"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
				json.dumps(payload, ensure_ascii=False).encode(),
				self._timeout,
			)
		if status != 200:
			raise CodefError(f"CODEF 상품 호출 실패 (HTTP {status})", raw=content[:500])
		data = _decode_codef_body(content)
		result = data.get("result") or {}
		code = result.get("code")
		if code != SUCCESS_CODE:
			raise CodefError(
				f"CODEF 업무 오류: {code} {result.get('message', '')}".strip(),
				code=code,
				raw=data,
			)
		return data.get("data") or {}


def _decode_codef_body(content: bytes) -> dict[str, Any]:
	"""CODEF 응답 본문 디코딩 — URL 인코딩된 JSON(정식 규격) 또는 평문 JSON(스텁) 모두 수용."""
	text = content.decode("utf-8", errors="replace").strip()
	if text.startswith("{"):
		return json.loads(text)
	from urllib.parse import unquote_plus  # noqa: PLC0415

	return json.loads(unquote_plus(text))
