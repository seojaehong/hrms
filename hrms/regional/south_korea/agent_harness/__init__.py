# -*- coding: utf-8 -*-
"""Agent Harness PoC — 하네스 엔지니어링 코어 (framework-free).

스킬 정의·도구 레지스트리·프롬프트 빌더·에이전트 루프를 framework-free 모듈로
모아둔 패키지. LLM provider는 주입식(테스트=fake)이라 API 키·네트워크 불필요.
Hermes 런타임 내재화(docs/korea_hrms/hermes-ontology-north-star.md)의 전 단계 PoC.

이 패키지의 코어 모듈은 상단에서 frappe를 import하지 않는다(비협상).
사이트 노출은 얇은 hrms/regional/south_korea/agent_harness_api.py 래퍼가 담당한다.
"""
