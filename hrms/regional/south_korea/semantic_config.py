# -*- coding: utf-8 -*-
"""v2 시맨틱 retriever 환경 팩토리 — env에서 키/접속을 읽어 조립. framework-free.

Supabase(yellow-envelope-law) 접속이 설정돼 있으면 embedder·rpc_caller·retriever를
조립해 반환. 미설정이면 None → chat_query는 v1(char-bigram 로컬 카탈로그)로 폴백.
즉 키가 있는 프로덕션에서만 더러운 로컬 카탈로그가 v2 임베딩 코퍼스로 은퇴한다.

시크릿은 절대 코드/repo에 두지 않는다 — 전부 env:
- YELLOW_ENVELOPE_SUPABASE_URL, YELLOW_ENVELOPE_SUPABASE_KEY
- OPENAI_API_KEY(1536: 행정해석/판례/FAQ), GEMINI_API_KEY(768: 최영우 pkb)

실행: python3 hrms/tests/test_korea_semantic_config.py
"""
from __future__ import annotations

import importlib.util as _ilu
import os
import pathlib as _pl
from typing import Any, Callable

_DIR = _pl.Path(__file__).resolve().parent

DEFAULT_SOURCES = ["pkb", "interpretation", "cases", "faq", "nlrc"]


def _load(name: str):
    spec = _ilu.spec_from_file_location(name, _DIR / f"{name}.py")
    m = _ilu.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


_adapters = _load("semantic_adapters")
_retrieval = _load("semantic_retrieval")
_ai_chat_sem = _load("ai_chat_semantic")


def build_semantic_retriever_from_env(
    env: dict | None = None,
    *,
    http_post: Callable[..., Any] | None = None,
    sources: list[str] | None = None,
    redactor: Callable[[str], str] | None = None,
) -> Callable[..., list[dict]] | None:
    """env가 Supabase 접속을 갖추면 v2 retriever, 아니면 None(→ v1 폴백).

    임베딩 키가 일부만 있어도 build_retrieval이 소스 단위 fail-soft하므로 조립은 진행
    (해당 소스만 조용히 비게 됨). Supabase 접속(url+key)은 필수.
    """
    env = env if env is not None else os.environ
    base_url = env.get("YELLOW_ENVELOPE_SUPABASE_URL") or ""
    sb_key = env.get("YELLOW_ENVELOPE_SUPABASE_KEY") or ""
    if not base_url or not sb_key:
        return None

    embedder = _adapters.make_embedder(
        gemini_key=env.get("GEMINI_API_KEY") or "",
        openai_key=env.get("OPENAI_API_KEY") or "",
        http_post=http_post,
    )
    rpc_caller = _adapters.make_rpc_caller(
        base_url=base_url, api_key=sb_key, http_post=http_post,
    )

    def retrieve_fn(query: str, srcs: list[str], top_k: int) -> list[dict]:
        return _retrieval.build_retrieval(
            query, srcs, embedder=embedder, rpc_caller=rpc_caller,
            top_k=top_k, redactor=redactor,
        )

    return _ai_chat_sem.make_semantic_retriever(
        retrieve_fn=retrieve_fn, sources=sources or DEFAULT_SOURCES,
    )
