# AI HR 담당자 — 채널 연결 정리 (SSOT)

> 이 프로그램은 **특정 사업장 전용이 아니다.** 봇/엔드포인트 **1벌**이 멀티테넌트를
> 서빙하는 범용 연결·라우팅 레이어이며, **노호는 tenant #1(첫 사업장)** 일 뿐이다.
> 코드는 테넌트를 모른다 — "누가 어느 테넌트인지"는 전부 아래 **바인딩 파일(데이터)** 로만 정해진다.
> (로직상 `noho`가 등장하는 유일한 곳은 예약 서브도메인 차단 목록 한 줄뿐이다.)

## 불변식

1. **봇/엔드포인트 1벌 = N테넌트.** 채널 커넥터는 `사용자ID → 테넌트 바인딩`과 텍스트 in/out만
   담당하고, 명령·계산·Q&A는 전부 `channel_core`가 처리한다. **채널이 늘어도 코어는 불변.**
2. **fail-closed.** 바인딩 없는 사용자/대화는 무응답(또는 "연결 안 됨" 안내). 미설정 채널은 503.
3. 테넌트 1개 = Frappe 사이트 1개. (site-per-tenant. 만개 확장의 실제 병목은 이 데이터 층이며
   샤딩은 로드맵 Phase 4. 연결 층은 지금 구조로 만개 확장 가능.)

## 5채널 한눈에

| 채널 | 실행 | 코드 | 바인딩 키 | 바인딩 파일(env) | 인증 |
|------|------|------|-----------|------------------|------|
| 텔레그램 | 독립 systemd 프로세스 | `telegram_connector.py` | `chat_id` | `KCHRMS_TG_BINDINGS` | 봇 토큰(`TELEGRAM_BOT_TOKEN`) |
| 메일 | 독립 systemd 프로세스 | `mail_connector.py` | 발신자 이메일 | `KCHRMS_MAIL_BINDINGS` | IMAP/SMTP 계정 |
| 슬랙 | `http_server` `/slack/events` | `handle_slack` | 채널 ID | `KCHRMS_SLACK_BINDINGS` | v0 서명(`SLACK_SIGNING_SECRET`) |
| 디스코드 | `http_server` `/discord/interactions` | `handle_discord` | 채널 ID | `KCHRMS_DISCORD_BINDINGS` | ed25519(`DISCORD_PUBLIC_KEY`) |
| **구글챗** | `http_server` `/googlechat/events` | `handle_googlechat` | `space.name` (예: `spaces/AAAA`) | `KCHRMS_GOOGLECHAT_BINDINGS` | JWT 이중모드(`GOOGLECHAT_PROJECT_NUMBER` + `GOOGLECHAT_AUDIENCE`) |

미설정 채널은 키가 없으면 503(휴면)이라 **고객이 실제 쓰는 채널만 켜면 된다.**

## 바인딩 파일 포맷 (공통)

키(채널별 식별자) → `{"site": "<Frappe 사이트>", "label": "<표시명>"}`.
파일 기본 위치: `~/.korea-hrms-mcp/`.

```jsonc
// tg-bindings.json (텔레그램)
{ "123456789": { "site": "noho.safeclaw.kr", "label": "노호 사장님" } }

// mail-bindings.json (메일)
{ "boss@noho.kr": { "site": "noho.safeclaw.kr", "label": "노호 사장님" } }

// slack-bindings.json (슬랙)     ← 키 = 슬랙 채널 ID
{ "C0ABC123": { "site": "noho.safeclaw.kr", "label": "노호 HR방" } }

// discord-bindings.json (디스코드) ← 키 = 디스코드 채널 ID
{ "998877665544": { "site": "noho.safeclaw.kr", "label": "노호 HR방" } }

// googlechat-bindings.json (구글챗) ← 키 = space.name
{ "spaces/AAAAxxxx": { "site": "noho.safeclaw.kr", "label": "노호 HR방" } }
```

> 실제 바인딩 파일은 **서버(claudebot-2)** 의 `~/.korea-hrms-mcp/` 에만 두고 git에 커밋하지 않는다.
> (본 문서의 값은 포맷 예시.)

## 새 테넌트(2호~) 붙이는 법

프로그램 배포·재시작 없이 **바인딩 한 줄 추가**로 끝난다:

1. 해당 고객의 Frappe 사이트 프로비저닝 (`config/multi_site.json` tenants[]).
2. 고객이 쓰는 채널의 바인딩 파일에 `식별자 → {site, label}` 추가.
3. (파일은 요청마다 로드되므로) 저장 즉시 반영. 봇 재시작 불필요.

## 구글챗 등록 절차 (5번째 채널 — 2026-07-06 실가동 검증 완료)

현재 가동: **winnersbot** (Workspace=노무법인위너스, GCP 프로젝트 번호 962433020697,
앱 URL `https://ai.safeclaw.kr/googlechat/events`).

1. **Workspace 계정**으로 Google Cloud Console → Chat API 활성 프로젝트에서 앱 구성.
   (개인 gmail 계정으로는 Chat 앱 구성 불가 — 실측 확인)
2. Connection settings = **HTTP endpoint URL** → `https://ai.safeclaw.kr/googlechat/events`.
3. **공개 상태**: "특정 사용자 및 그룹" 체크 + 사용자 등록 — 안 하면 채팅에서 앱 검색 자체가 안 됨.
4. 서버 env (systemd drop-in `korea-hrms-mcp.service.d/googlechat.conf`):
   - `GOOGLECHAT_PROJECT_NUMBER=<프로젝트 번호>` — 독립앱 JWT aud + 부가기능 서비스계정 검증
   - `GOOGLECHAT_AUDIENCE=https://ai.safeclaw.kr/googlechat/events` — **부가기능형 필수** (OIDC aud=앱 URL)
   - `KCHRMS_GOOGLECHAT_BINDINGS=~/.korea-hrms-mcp/googlechat-bindings.json`
5. `pip install pyjwt cryptography` — JWT 서명 검증.
6. 봇을 스페이스에 초대 → 미바인딩이면 "연결되지 않았습니다" 응답 + 서버 로그에
   `googlechat unbound space: spaces/XXXX` 기록 → 그 값을 바인딩 파일에 등록 (재시작 불필요).

### ⚠️ 부가기능형(Workspace add-on) 챗 앱 주의 (실측으로 확정)
"이 채팅 앱을 Workspace 부가기능으로 빌드"가 켜진 앱은 **표준 Chat 앱과 프로토콜이 다르다**:
- 인증: `chat@system` 서명이 아니라 **accounts.google.com OIDC ID 토큰**
  (aud=앱 URL, email=`service-{프로젝트번호}@gcp-sa-gsuiteaddons.iam.gserviceaccount.com`)
- 페이로드: `{"chat": {"messagePayload": {...}}}` (표준 `{"type":"MESSAGE",...}` 아님)
- 응답: `{"hostAppDataAction":{"chatDataAction":{"createMessageAction":{"message":{"text":...}}}}}` 래핑 필수
`http_server.py`의 `verify_googlechat_jwt`/`handle_googlechat`이 **이중 모드**로 둘 다 처리한다.

검증: 서명 실패/라이브러리 부재/aud·iss 불일치는 전부 401 또는 fail-closed 안내.
env 미설정이면 `/googlechat/events`는 503.
