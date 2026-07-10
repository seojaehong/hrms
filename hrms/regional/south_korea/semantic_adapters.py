# -*- coding: utf-8 -*-
"""v2 시맨틱 검색 어댑터 — 임베딩 API·Supabase RPC HTTP 글루. framework-free.

semantic_retrieval.build_retrieval에 주입할 embedder/rpc_caller의 실제 구현.
HTTP 호출(http_post)은 주입 가능 → 단위테스트는 네트워크 없이 계약만 검증.

⚠️ 모델 정합성: 코퍼스는 pkb=Gemini 768d, 그 외=OpenAI 1536d로 임베딩됨.
질문 임베딩 모델이 코퍼스와 다르면 유사도가 무의미해진다. 모델 ID는 환경변수로
주입하되 기본값은 표준(text-embedding-004 / text-embedding-3-small)을 쓰고,
스모크(smoke_v2_semantic.py)로 top 결과가 온토픽인지 실증 확인한다.
"""
from __future__ import annotations

from typing import Any, Callable

_GEMINI_DIM = 768
_OPENAI_DIM = 1536


def _default_http_post(url, headers=None, json=None):  # pragma: no cover - 실네트워크
    import requests  # 지연 import(테스트는 http_post 주입)

    resp = requests.post(url, headers=headers or {}, json=json or {}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def make_embedder(
    *,
    gemini_key: str,
    openai_key: str,
    http_post: Callable[..., Any] | None = None,
    gemini_model: str = "text-embedding-004",
    openai_model: str = "text-embedding-3-small",
) -> Callable[[str, str], list[float]]:
    """(model, text) → 임베딩 벡터. model 'gemini-768' | 'openai-1536'.

    코퍼스와 동일 차원(768/1536)을 검증한다(불일치 시 ValueError = 모델 오설정 조기 발견).
    """
    post = http_post or _default_http_post

    def embed(model: str, text: str) -> list[float]:
        if model == "gemini-768":
            if not gemini_key:
                raise ValueError("GEMINI_API_KEY 미설정 — pkb(768d) 임베딩 불가")
            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{gemini_model}:embedContent?key={gemini_key}"
            )
            body = {"model": f"models/{gemini_model}", "content": {"parts": [{"text": text}]}}
            data = post(url, headers={"Content-Type": "application/json"}, json=body)
            vec = ((data or {}).get("embedding") or {}).get("values") or []
            _check_dim(vec, _GEMINI_DIM, model)
            return vec
        if model == "openai-1536":
            if not openai_key:
                raise ValueError("OPENAI_API_KEY 미설정 — 행정해석/판례/FAQ(1536d) 임베딩 불가")
            url = "https://api.openai.com/v1/embeddings"
            headers = {"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"}
            body = {"model": openai_model, "input": text}
            data = post(url, headers=headers, json=body)
            arr = (data or {}).get("data") or []
            vec = arr[0].get("embedding") if arr else []
            _check_dim(vec, _OPENAI_DIM, model)
            return vec
        raise ValueError(f"알 수 없는 임베딩 모델: {model}")

    return embed


def _check_dim(vec: list, expected: int, model: str) -> None:
    if not isinstance(vec, list) or len(vec) != expected:
        raise ValueError(
            f"{model} 임베딩 차원 불일치: {len(vec) if isinstance(vec, list) else 'N/A'} "
            f"(기대 {expected}) — 임베딩 모델이 코퍼스와 다를 수 있음"
        )


def make_rpc_caller(
    *,
    base_url: str,
    api_key: str,
    http_post: Callable[..., Any] | None = None,
) -> Callable[[str, dict], list[dict]]:
    """(rpc, params) → rows. Supabase PostgREST `/rest/v1/rpc/{fn}` POST."""
    if not base_url or not api_key:
        raise ValueError("Supabase base_url/api_key 미설정 — RPC 호출 불가")
    post = http_post or _default_http_post
    root = base_url.rstrip("/")

    def call(rpc: str, params: dict) -> list[dict]:
        url = f"{root}/rest/v1/rpc/{rpc}"
        headers = {
            "apikey": api_key,
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        data = post(url, headers=headers, json=params)
        return data if isinstance(data, list) else []

    return call
