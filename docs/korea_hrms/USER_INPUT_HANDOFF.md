# 사용자 투입 필요 항목 — 마스터 핸드오프 (2026-07-09)

이 문서는 **Claude가 코드로 끝낼 수 없는, 사람만 할 수 있는 외부 작업**만 모은 단일 체크리스트다.
각 항목: **무엇 / 어디서 / 어떻게 / 적용값(어디에 넣나)**. 값이 준비되면 대부분 `scripts/launch_day_apply.sh` 한 줄로 반영된다(값 없으면 자동 SKIP → 부분 적용 가능).

> 적용 실행 위치: `ssh claudebot-2` → `cd /home/ubuntu/workspaces/seojaehong-hrms-100h && git pull` → 아래 원커맨드.
> 키를 Claude 세션에 주면 대신 실행 가능(단, 시크릿 취급 주의 — public repo 커밋 금지).

---

## 🔴 TIER 1 — 지금 노호 개통 (각 독립, 1번만 해도 접속 열림)

### 1. Cloudflare DNS — ✅ **이미 완료 (2026-07-09 검증)**
- **현재 상태**: `*.safeclaw.kr` (Tunnel → winhr-intake, Proxied) 와일드카드 레코드가 **이미 존재**.
  `noho.safeclaw.kr` **HTTP 200 라이브**, `noho.safeclaw.kr/app` 200, `ai.safeclaw.kr` 401(인증게이트 정상).
  노호 사장님(류두선) 실 로그인·가동 확인됨.
- ⚠️ **런북의 "`*.hrms`를 `*`로 수정" 지시는 낡음** — `*` 레코드가 이미 있으므로 **편집하지 말 것**(중복/충돌·라이브 서비스 손상 위험).
- DNS 레코드 4개: `safeclaw.kr`(A 216.150.1.1) · `*.hrms.safeclaw.kr`(Tunnel) · `*.safeclaw.kr`(Tunnel winhr-intake) · `www.safeclaw.kr`(CNAME vercel).

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

### 10-1. CODEF 데모 키 — 4대보험 조회 연동 (⏱️15분, 결정됨 2026-07-10)
- **어디서**: https://codef.io → 회원가입 → 대시보드 → **데모 신청**(무료, 심사 없음) → 데모 client_id/client_secret 발급
- **적용값**: 서버 site_config 또는 env — `codef_client_id`, `codef_client_secret` (데모는 `codef_demo` 생략, 정식 전환 시 `codef_demo=false`)
  ```bash
  # 서버에서: docker exec -w /home/frappe/frappe-bench docker-frappe-1 \
  #   bench --site noho.safeclaw.kr set-config codef_client_id "..." 
  #   bench --site noho.safeclaw.kr set-config codef_client_secret "..."
  ```
- **연동 코드 준비 완료**: `insurance_inquiry_api.py`(조회 전용·fail-closed) + `codef_client.py` — 키만 넣으면 `fetch_insured_roster(관리번호)` 작동
- **확정된 실무 구조** (대행기관 실경험, 2026-07-10): 대행기관 일괄조회는 **고용·산재(토탈서비스)만 가능** — 크롬 확장으로 이미 자동화 자산 보유. **건보·연금은 사업장별 인증 위임 불가피** → CODEF의 실가치 = 건보/연금 사업장별 인증 마찰의 API 대체.
- **★ 정식 계약 전 영업문의로 반드시 확인할 것**:
  1. **건보/연금 사업장별 위임 인증 방식** — 인증서를 CODEF에 보관하는가? 간편인증(카카오 등) 1회성인가? 갱신 주기·만료 시 재인증 UX는? (온보딩 마찰의 크기가 여기서 결정)
  2. 4대보험 상품별 건당 단가·월 최소약정
  3. 상품 경로/파라미터 스펙 (현재 코드의 PRODUCT_INSURED_ROSTER는 확정 전 가정값)
  4. (부차) 고용산재는 대행기관 일괄 경로가 이미 있으므로 CODEF 상품이 그보다 나은 게 있는지
- **Claude 불가 이유**: 회원가입=계정 생성(보안 규칙상 사용자 직접). 가입 후 키만 주시면 연동·검증은 자동

## 🟢 TIER 3 — S2 확장·셀프서브 (Phase 3, 9~10월)

### 11. 중앙 인증 브로커 `auth.safeclaw.kr`
- 구글 리디렉션 URI 1개화(테넌트 무한확장). 구글 OAuth 콘솔에 통합 리디렉션 등록 필요

### 12. PG(결제) 연동 — 유료 실결제
- **어디서**: 토스페이먼츠/포트원(아임포트) 등 가맹 계약 + 심사
- **적용값**: PG 상점 키 → 미터링→요금제 실결제 연결

### 13. HR 전용 VM (선택)
- Oracle Cloud에서 4~8 vCPU VM 추가(모니터링·격리). 인프라 결제·프로비저닝은 본인 콘솔

---

## 📌 요약 (2026-07-09 실검증 반영)
- **DNS·접속 = 이미 완료** (noho.safeclaw.kr 라이브, 류두선 가동 중). §1은 손대지 말 것.
- 남은 사용자 투입 = **소셜로그인 키(구글/카카오)·SMTP·주민번호 CSV** 중 아직 미적용분. 단, 노호가 이미 로그인·운영 중이므로 **일부는 이미 적용됐을 수 있음** → 실제 미적용분만 확인 후 `launch_day_apply.sh`.
- **⚠️ 낡은 런북 주의**: `LAUNCH_DAY_RUNBOOK.md`는 출시 전 작성본 — DNS 등 일부 항목이 이미 처리됨. 이 문서(실검증)를 우선.

## 참고 문서
- 출시 런북(원문): `docs/korea_hrms/LAUNCH_DAY_RUNBOOK.md`
- 채널 연결: `docs/korea_hrms/ai-hr-channels.md`
- 장기 로드맵: `docs/korea_hrms/long-term-roadmap.md`
- 적용 스크립트: `scripts/launch_day_apply.sh`
