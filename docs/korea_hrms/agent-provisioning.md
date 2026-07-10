# 에이전트 자동 프로비저닝 (코드 파트)

가입 시 AI HR 담당자 에이전트를 **자동 개통**한다. 1호(노호)는 서비스유저·토큰·
바인딩을 손으로 만들었지만, 2호부터는 이 파이프라인으로 무인 개통한다.
10만 사업장 상용을 향한 셀프서브/크론 자동화의 코드 토대다.

이 문서가 다루는 것은 **프로비저닝을 실행할 순수·검증가능한 코드**다. 실제 유저
생성·토큰 발급·config 기록·바인딩 같은 라이브 부수효과는 `--apply` + frappe 런타임
에서만 일어나며, 실행 자체는 사람/크론의 몫이다.

## 구성

| 파일 | 역할 |
|---|---|
| `mcp_server/agent_provisioning.py` | 순수 코어 — 플랜 빌더·바인딩 병합·상태 점검(frappe 미import, 부수효과 0) |
| `mcp_server/provision_agent.py` | CLI — 플랜을 실제 부수효과로 옮김(조건부 frappe, 기본 dry-run) |

## 흐름: 가입 → 플랜 → apply

1. **가입 이벤트**(셀프서브 폼 제출 또는 운영자 등록)로 사이트·(선택)텔레그램 chat_id 확보.
2. **플랜 생성** — `build_agent_provisioning_plan(site, *, telegram_chat_id=None,
   provider="hermes", gateway_url=...)` 가 실행할 스텝을 **데이터(dict 리스트)**로 반환:
   - `ensure_service_user` — `agent-bot@{site}` 서비스 유저(System Manager)
   - `issue_mcp_token` — **계산전용(`calc_only`)** 토큰 발급 지시
   - `set_site_config` — `korea_agent_harness_provider` / `hermes_gateway_url`
   - `bind_channel` — chat_id 가 있을 때만 텔레그램 바인딩
   순수 함수라 부수효과가 없고(같은 입력 → 같은 플랜), 빈 site·gateway_url 누락은 `ValueError`.
3. **점검(선택)** — `check_agent_provisioning(binding, site_config)` 가 주입된 값만으로
   `{ready, missing}` 를 돌려준다(라이브 조회 없음). `ready` 가 아니면 무엇이 빠졌는지 알 수 있다.
4. **apply** — CLI 로 실행:

```bash
# 기본은 dry-run — 계획만 출력하고 아무것도 바꾸지 않는다(fail-safe).
python3 mcp_server/provision_agent.py noho.safeclaw.kr \
    --gateway-url https://hermes.example.com --telegram-chat-id 12345

# 실제 개통은 --apply 를 명시했을 때만(그리고 frappe 런타임 안에서).
python3 mcp_server/provision_agent.py noho.safeclaw.kr \
    --gateway-url https://hermes.example.com --telegram-chat-id 12345 --apply
```

`--apply` 가 없으면 항상 dry-run 이고, `--apply` 라도 frappe 가 없으면 안전하게
dry-run 으로 강등한다(실수로 라이브를 건드리지 않는다).

## 멱등성

`merge_channel_binding(bindings, chat_id, site, credentials)` 는 기존 바인딩 dict 에
항목을 추가/갱신한 **새 dict** 를 반환한다(깊은 복사 — 원본 불변). 같은 사이트가
이미 있으면 자격만 갱신하므로, **같은 입력으로 두 번 호출해도 결과가 같다(멱등)**.
가입 이벤트가 재시도되거나 크론이 중복 실행돼도 상태가 어긋나지 않는다.

## 보안

- **계산전용 토큰 스코프**: 자동 발급 토큰은 `calc_only` 스코프다. 테넌트 데이터에
  접근하지 못하고 계산·조회 도구만 쓸 수 있어, 개통 자동화가 최소 권한을 유지한다.
  (브리지 도구용 자격은 별도 `issue_token.py` + BYOK 경로로만 부여.)
- **시크릿 마스킹**: 로깅·dry-run 출력은 `mask_binding(b)` 로 `api_secret` 을 `***` 로
  가린다. 평문 시크릿은 발급 시 1회만 노출되고 저장물에는 sha256/마스킹 값만 남는다.
- **fail-safe 기본값**: dry-run 이 기본이라, 잘못된 인자나 frappe 부재 시 부수효과가 0 이다.

## 10만 사업장 확장 연결점

- **셀프서브**: 가입 폼 제출 → `build_agent_provisioning_plan` → 결재/자동 승인 후 `--apply`.
  플랜이 데이터(dict)라 승인 큐에 그대로 실어 사람이 검토하거나 정책으로 자동 통과시킬 수 있다.
- **크론**: 미개통(`check_agent_provisioning.ready == False`) 테넌트를 주기적으로 스캔해
  배치 apply. 멱등성 덕분에 재실행이 안전하다.
- **샤딩**: `issue_token.py --frappe-url` 로 테넌트가 다른 bench 호스트에 있어도
  토큰 바인딩에 호스트를 실어 라우팅한다(데이터 위치만 바뀜).

## 테스트

- `python3 hrms/tests/test_korea_agent_provisioning.py` — 코어(플랜·병합·마스킹·점검).
- `python3 hrms/tests/test_korea_provision_agent_cli.py` — CLI(dry-run 부수효과 0·apply·마스킹).
- `python3 hrms/tests/test_korea_agent_provisioning_docs.py` — 이 문서 정합성.

모두 framework-free(frappe 미의존, fake/주입식)이며 라이브 인프라를 건드리지 않는다.
