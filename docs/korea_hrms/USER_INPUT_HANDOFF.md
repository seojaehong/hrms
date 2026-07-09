# 사용자 투입 필요 항목 — 마스터 핸드오프 (2026-07-09)

이 문서는 **Claude가 코드로 끝낼 수 없는, 사람만 할 수 있는 외부 작업**만 모은 단일 체크리스트다.
각 항목: **무엇 / 어디서 / 어떻게 / 적용값(어디에 넣나)**. 값이 준비되면 대부분 `scripts/launch_day_apply.sh` 한 줄로 반영된다(값 없으면 자동 SKIP → 부분 적용 가능).

> 적용 실행 위치: `ssh claudebot-2` → `cd /home/ubuntu/workspaces/seojaehong-hrms-100h && git pull` → 아래 원커맨드.
> 키를 Claude 세션에 주면 대신 실행 가능(단, 시크릿 취급 주의 — public repo 커밋 금지).

---

## 🔴 TIER 1 — 지금 노호 개통 (각 독립, 1번만 해도 접속 열림)

### 1. Cloudflare DNS — ⏱️2분, **이것만 하면 접속 개통**
- **어디서**: Cloudflare 대시보드 → `safeclaw.kr` → DNS → Records
- **어떻게**: 기존 `*.hrms` CNAME **Edit** → Name을 `*` 로 수정 → Save
  - Target `a04b8f7a-8b04-49f7-8c73-3fc1c07519fb.cfargotunnel.com` (Proxied 유지)
- **결과**: 1~2분 뒤 `https://noho.safeclaw.kr` + `https://ai.safeclaw.kr` 개통
- **Claude 불가 이유**: Cloudflare 계정 = 본인 소유(euiri.choi 계정 아님, safeclaw는 iceamericano9). 대시보드 인증 필요

### 2. 구글 로그인 — ⏱️10분
- **어디서**: console.cloud.google.com → API 및 서비스 → 사용자 인증 정보 → OAuth 클라이언트 ID(웹)
- **승인된 리디렉션 URI**: `https://noho.safeclaw.kr/api/method/frappe.integrations.oauth2_logins.login_via_google`
- **적용값**: `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`

### 3. 카카오 로그인 — ⏱️10분
- **어디서**: developers.kakao.com → 앱 생성 → [앱 키] REST API 키 + [보안] Client Secret 발급
- **Redirect URI**: `https://noho.safeclaw.kr/api/method/hrms.regional.south_korea.social_login_api.kakao_callback`
- **⚠ 필수 설정**: [동의항목] → 카카오계정(이메일) = **필수 동의**
- **적용값**: `KAKAO_REST_API_KEY`, `KAKAO_CLIENT_SECRET`

### 4. 오프사이트 백업 스토리지 — ⏱️10분
- **어디서**: Oracle Cloud 콘솔 → Object Storage 버킷 생성 → User Settings → Customer Secret Keys 발급
- **S3 호환 endpoint 형식**: `https://<namespace>.compat.objectstorage.<region>.oraclecloud.com`
- **적용값**: `BACKUP_S3_BUCKET`(s3://…), `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_ENDPOINT_URL`
- (미투입 시 로컬 백업 크론은 계속 가동 — 개통 필수 아님)

### 5. 노호 직원 명부 CSV + 주민번호 — 고객 협업
- **템플릿**: `docs/clients/noho_employee_import_template.csv`
- **절차(SOP)**: `docs/clients/noho_beta_onboarding.md` §3
- **주민번호**: 암호화 커스텀 필드에 입력 → 4대보험 신고서 3종 완전체(현재 필드/암호화는 코드측 준비 필요 = P1 개발항목, 별도)
- **Claude 불가 이유**: 실제 개인정보(주민번호) = 고객이 직접 제공, public repo·세션 로그 금지

### TIER 1 원커맨드 (2~4 일괄 적용)
```bash
ssh claudebot-2
cd /home/ubuntu/workspaces/seojaehong-hrms-100h && git pull
GOOGLE_OAUTH_CLIENT_ID=... GOOGLE_OAUTH_CLIENT_SECRET=... \
KAKAO_REST_API_KEY=... KAKAO_CLIENT_SECRET=... \
BACKUP_S3_BUCKET=s3://hrms-backup AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_ENDPOINT_URL=... \
./scripts/launch_day_apply.sh noho.safeclaw.kr
```

---

## 🟡 TIER 2 — 제품 완성·2호 고객 (Phase 2, 7월 하반~8월)

### 6. SMTP 이메일 계정 — 명세서 자동발송 + 메일 AI 채널
- **어디서**: 발송용 메일 계정(예: Google Workspace, 네이버웍스 abc@winhr.co.kr, 또는 전용 SMTP)
- **필요값**: SMTP host/port, 계정, 앱 비밀번호(2FA 계정은 앱 비번 발급)
- **적용**: 개통 후 노호 사이트 → Email Account(Frappe) 연결 → 내부 주소로 발송 리허설 후 활성화
- **Claude 불가 이유**: 메일 계정 소유·앱 비번 발급은 본인 인증 필요

### 7. 카카오 알림톡 — ⚠️심사 7~14일, **즉시 신청 권장**
- **어디서**: 카카오 비즈니스 채널 개설 → Solapi(또는 대행사) 발신프로필 등록 → 템플릿 심사
- **왜 지금**: 심사가 오래 걸려 리드타임이 병목. 채널만 먼저 열어두기
- **적용값**: Solapi API 키 + 승인된 템플릿 코드(추후 env)

### 8. LLM API 키 — AI v2 자연대화 승격
- **어디서**: Anthropic Console(권장, claude-*) 또는 Gemini
- **적용값**: `ANTHROPIC_API_KEY`(또는 `GEMINI_API_KEY`) → `~/.korea-hrms-mcp/` env
- (현재 AI는 조회·계산·조문인용까지 LLM 없이 작동. 키는 자연대화 `call_llm_with_context` 활성화용)

### 9. 메신저 앱 등록 (슬랙·디스코드·구글챗) — 5채널 전면 가동
- **슬랙**: api.slack.com/apps → 앱 생성 → Signing Secret + Bot Token, 슬래시커맨드/이벤트 URL = `https://ai.safeclaw.kr/slack/...`
- **디스코드**: discord.com/developers → 앱/봇 → Bot Token + Public Key, Interactions URL = `https://ai.safeclaw.kr/discord/...`
- **구글챗**: 이미 winnersbot 실가동(OIDC 이중모드) — 노호 스페이스에 봇 추가만 남음(`project_korea_hrms_noho_launch`)
- **정리 문서**: `docs/korea_hrms/ai-hr-channels.md`

### 10. 브랜드 확정 — 디자인 D4 게이트 + Linear 랜딩 확정
- **결정 필요**: SafeClaw 병용 vs NODE 차용 vs 신규. 로고, 국문 서체(Pretendard variable 검토)
- **영향**: Linear 다크 랜딩/가입 페이지의 워드마크·팔레트 최종 확정, 취소 불가 커밋 전 필요

---

## 🟢 TIER 3 — S2 확장·셀프서브 (Phase 3, 9~10월)

### 11. 중앙 인증 브로커 `auth.safeclaw.kr`
- 구글 리디렉션 URI 1개화(테넌트 무한확장). 구글 OAuth 콘솔에 통합 리디렉션 등록 필요

### 12. PG(결제) 연동 — 유료 실결제
- **어디서**: 토스페이먼츠/포트원(아임포트) 등 가맹 계약 + 심사
- **적용값**: PG 상점 키 → 미터링→요금제 실결제 연결

### 13. HR 전용 VM (선택)
- Oracle Cloud에서 4~8 vCPU VM 추가(모니터링·격리). 인프라 결제·프로비저닝은 본인 콘솔

---

## 📌 요약 — 지금 당장 할 것 딱 하나
**TIER 1 §1 (Cloudflare DNS `*`)** = 2분, 그거 하나로 노호 접속이 열린다. 나머지는 병렬로.

## 참고 문서
- 출시 런북(원문): `docs/korea_hrms/LAUNCH_DAY_RUNBOOK.md`
- 채널 연결: `docs/korea_hrms/ai-hr-channels.md`
- 장기 로드맵: `docs/korea_hrms/long-term-roadmap.md`
- 적용 스크립트: `scripts/launch_day_apply.sh`
