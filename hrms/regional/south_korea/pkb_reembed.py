# -*- coding: utf-8 -*-
"""pkb 재임베딩 순수 코어 — 최영우 pkb를 OpenAI 1536으로 통일(Gemini 768 폐기). framework-free.

배치 분할·OpenAI 응답 파싱·쓰기 페이로드 조립만 담당(순수). 실제 OpenAI/Supabase
호출은 scripts/reembed_pkb_openai.py.

실행: python3 hrms/tests/test_korea_pkb_reembed.py
"""
from __future__ import annotations

from typing import Any


# 임베딩 입력 안전 절단 길이 — 한국어 ~2토큰/자, 3-small 한도 8192토큰.
# 8k자 청크(≈16k토큰)로 400 실사고 → 3000자(≈6-7.5k토큰)면 안전. 검색용이라 앞부분로 충분.
_EMBED_MAX_CHARS = 3000


def truncate_for_embedding(text: str) -> str:
    """임베딩 입력용 텍스트 절단. 빈/공백 문자열은 공백 1자(OpenAI가 빈 입력 거부)."""
    t = (text or "").strip()
    if not t:
        return " "
    return t[:_EMBED_MAX_CHARS]


def chunk_batches(items: list, size: int) -> list[list]:
    """items를 size 단위 배치로 분할."""
    return [items[i:i + size] for i in range(0, len(items), size)]


def parse_openai_embeddings(response: dict, expected: int | None = None) -> list[list[float]]:
    """OpenAI /v1/embeddings 응답 → index 순 임베딩 리스트. expected 주면 개수 검증."""
    data = (response or {}).get("data") or []
    ordered = [d["embedding"] for d in sorted(data, key=lambda d: d.get("index", 0))]
    if expected is not None and len(ordered) != expected:
        raise ValueError(f"임베딩 개수 불일치: {len(ordered)} (기대 {expected})")
    return ordered


def assemble_write_payload(ids: list, vectors: list[list[float]]) -> list[dict[str, Any]]:
    """(ids, vectors) → pkb_write_1536용 [{id, emb}] 페이로드. 길이 불일치 시 에러."""
    if len(ids) != len(vectors):
        raise ValueError(f"ids({len(ids)})와 vectors({len(vectors)}) 길이 불일치")
    return [{"id": i, "emb": v} for i, v in zip(ids, vectors)]
