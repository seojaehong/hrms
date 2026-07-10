# -*- coding: utf-8 -*-
"""v2 시맨틱 RAG 실증 스모크 — 실키로 임베딩 모델 정합 + 검색 품질 확인.

시크릿은 env에서만 읽는다(출력 금지). 실행:
  YELLOW_ENVELOPE_SUPABASE_URL=... YELLOW_ENVELOPE_SUPABASE_KEY=... \
  OPENAI_API_KEY=... GEMINI_API_KEY=... \
  python scripts/smoke_v2_semantic.py "주휴수당 발생 요건"

판정 기준(모델 정합):
- top 유사도가 0.5+ 이고 결과가 온토픽 → 임베딩 모델이 코퍼스와 일치(정상)
- 유사도가 전부 0.1 근처/뒤죽박죽 → 질문 임베딩 모델이 코퍼스와 다름(모델 오설정)
"""
import importlib.util
import os
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_KO = _ROOT / "hrms" / "regional" / "south_korea"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    query = sys.argv[1] if len(sys.argv) > 1 else "주휴수당 발생 요건"

    missing = [k for k in ("YELLOW_ENVELOPE_SUPABASE_URL", "YELLOW_ENVELOPE_SUPABASE_KEY")
               if not os.environ.get(k)]
    if missing:
        print(f"[중단] Supabase 접속 env 미설정: {', '.join(missing)}")
        print("       (임베딩: OPENAI_API_KEY / GEMINI_API_KEY 도 필요)")
        return 2

    cfg = _load("semantic_config", _KO / "semantic_config.py")
    retrieval = _load("semantic_retrieval", _KO / "semantic_retrieval.py")
    adapters = _load("semantic_adapters", _KO / "semantic_adapters.py")

    embedder = adapters.make_embedder(
        gemini_key=os.environ.get("GEMINI_API_KEY", ""),
        openai_key=os.environ.get("OPENAI_API_KEY", ""),
    )
    rpc = adapters.make_rpc_caller(
        base_url=os.environ["YELLOW_ENVELOPE_SUPABASE_URL"],
        api_key=os.environ["YELLOW_ENVELOPE_SUPABASE_KEY"],
    )

    print(f"질문: {query}\n" + "=" * 60)
    for src in cfg.DEFAULT_SOURCES:
        try:
            docs = retrieval.build_retrieval(query, [src], embedder=embedder,
                                             rpc_caller=rpc, top_k=3, per_source_cap=3)
        except Exception as e:  # noqa: BLE001
            print(f"[{src}] 오류: {type(e).__name__}: {e}")
            continue
        if not docs:
            print(f"[{src}] 결과 없음")
            continue
        top = docs[0]
        print(f"[{top['source']}] top score={top['score']:.3f}")
        for d in docs:
            print(f"    {d['score']:.3f} | {(d['title'] or d['ref'])[:50]}")

    # 전체 소스 합쳐 chat_query 팩트체크 판정까지
    ai_chat = _load("ai_chat", _KO / "ai_chat.py")
    retriever = cfg.build_semantic_retriever_from_env()
    r = ai_chat.chat_query(user_question=query, user_role="hr_manager",
                           session_id="smoke", retriever=retriever)
    print("=" * 60)
    print(f"신뢰도(retrieval_confidence): {r['retrieval_confidence']}")
    print(f"사람연결(requires_human_consult): {r['requires_human_consult']}")
    print("답변:\n" + r["answer"][:600])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
