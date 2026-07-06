# 출시일 아침 런북 — 10분 체크리스트 (2026-07-06)

시스템은 준비 완료 상태다 (`launch-master-plan.md` §6-7 최종 판정). 아래 5개만 하면 노호에 링크를 보낼 수 있다.
각 항목은 독립적이다 — 1번만 해도 접속은 열린다.

## 1. DNS (2분) — 이것만 하면 접속 개통
Cloudflare 대시보드 → safeclaw.kr → DNS → Records → 기존 `*.hrms` CNAME **Edit** → Name을 `*` 로 수정 → Save.
(Target `a04b8f7a-8b04-49f7-8c73-3fc1c07519fb.cfargotunnel.com` · Proxied 그대로)
→ 1~2분 뒤 `https://noho.safeclaw.kr` 개통 (AI 게이트웨이 `https://ai.safeclaw.kr` 도 함께).

## 2. 구글 로그인 키 (10분)
console.cloud.google.com → API 및 서비스 → 사용자 인증 정보 → OAuth 클라이언트 ID(웹).
승인된 리디렉션 URI: `https://noho.safeclaw.kr/api/method/frappe.integrations.oauth2_logins.login_via_google`

## 3. 카카오 로그인 키 (10분)
developers.kakao.com → 앱 생성 → [앱 키] REST API 키 + [보안] Client Secret 발급.
Redirect URI: `https://noho.safeclaw.kr/api/method/hrms.regional.south_korea.social_login_api.kakao_callback`
⚠ [동의항목] 카카오계정(이메일) = **필수 동의** 설정.

## 4. 백업 오프사이트 키 (10분)
Oracle Cloud 콘솔 → Object Storage 버킷 생성 → User Settings → Customer Secret Keys 발급.
(S3 호환 endpoint: `https://<namespace>.compat.objectstorage.<region>.oraclecloud.com`)

## 2~4 적용 (서버에서 한 줄)
```bash
ssh claudebot-2
cd /home/ubuntu/workspaces/seojaehong-hrms-100h && git pull
GOOGLE_OAUTH_CLIENT_ID=... GOOGLE_OAUTH_CLIENT_SECRET=... \
KAKAO_REST_API_KEY=... KAKAO_CLIENT_SECRET=... \
BACKUP_S3_BUCKET=s3://hrms-backup AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_ENDPOINT_URL=... \
./scripts/launch_day_apply.sh noho.safeclaw.kr
```
값이 없는 항목은 자동 SKIP — 부분 적용 가능. (또는 키를 Claude 세션에 주면 대신 실행)

## 5. 노호 직원 CSV (고객 협업)
템플릿: `docs/clients/noho_employee_import_template.csv` → 온보딩 SOP `docs/clients/noho_beta_onboarding.md` §3.

## 접속 정보 (노호 전달용)
- 주소: `https://noho.safeclaw.kr` (모바일 PWA: `/hrms`)
- 관리자: `admin@noho.kr` / 임시 비번은 별도 전달분 — **최초 로그인 즉시 변경**
- AI HR 담당자: 텔레그램 (현재 사장님 채팅 바인딩, 노호 담당자 추가는 `~/.korea-hrms-mcp/tg-bindings.json`). 5채널(텔레그램·메일·슬랙·디스코드·구글챗) 연결·바인딩 정리는 `docs/korea_hrms/ai-hr-channels.md`

## 지금 이미 돌아가는 것 (아무 것도 안 해도)
크론 5종(일일 전사이트 백업·5분 스모크→텔레그램 경보·5분 가입 워커·월간 복구 드릴·월간 사용량/SLA 리포트) + systemd 2종(AI 게이트웨이·텔레그램 커넥터).
