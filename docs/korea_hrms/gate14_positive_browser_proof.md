# Gate 14 Positive Authenticated Browser Proof Evidence

작성일: 2026-05-17 KST
검증자: human-approved run via control-plane agent (Claude, this server)
결과: **GATE 14 PASSED** ✅ — 첫 positive authenticated browser runtime proof 달성

---

## 1. 배경

Gate 14는 "Human-approved demo credential apply and authenticated browser runtime proof"가 목표 — `FRAPPE_BROWSER_PASSWORD`가 존재하고 `--human-approved` 플래그가 명시되어야 credential apply + browser verification이 실행된다.

지난 ~10일간 자율 cron이 Gate 14 영역 내의 fail-closed/scope/report-file/blank-input 검증을 정교화했지만 (PR #189 → #224), 운영자 제공 비밀번호와 명시 승인이 없어서 positive proof는 단 한 번도 산출되지 않았다.

오늘(2026-05-17 KST 08:42) 운영자 승인하에 control-plane에서 credential apply + browser verifier를 1회 실행하여 첫 positive proof를 확보했다.

---

## 2. 실행 명령

```bash
FRAPPE_BROWSER_PASSWORD='<operator-provided, never stored in repo>' \
python3 scripts/verify_korea_demo_browser_credential_apply.py \
    --base-url http://localhost:8000 \
    --human-approved \
    --report-file /tmp/gate14-final.json \
    --browser-report-file /tmp/gate14-browser-final.json
```

- `--base-url http://localhost:8000`: 호스트의 systemd-resolved가 Oracle Cloud DNS(169.254.169.254)를 stub로 사용하면서 외부 도메인 `hrms.safeclaw.kr`에 대해 NXDOMAIN을 캐시 — node `fetch()`가 실패. Frappe `serve_default_site=true` + `default_site=hrms.localhost` 설정이 이미 되어 있으므로 호스트 loopback(`http://localhost:8000`)으로 우회 가능. 컨테이너의 Frappe site가 같은 응답을 한다.
- `--human-approved`: 명시 승인 플래그. credential apply가 비밀번호 mutation을 실행하기 위한 필수 조건.
- 비밀번호는 절대 repo/log/PR에 기록하지 않으며, 운영자 환경의 600-permission file에 저장되어 환경변수로만 주입된다.

---

## 3. 검증 결과 (top-level)

```json
{
  "runtime_verified": true,
  "fixture_fallback_required": false,
  "credential_apply": {
    "attempted": true,
    "passed": true,
    "human_approval_verified": true,
    "contract_type": "korea_demo_browser_credential_runtime_apply_v1",
    "runtime_action": "demo_credential_runtime_apply"
  },
  "browser_verification": {
    "attempted": true,
    "passed": true,
    "runtime_verified": true,
    "fixture_fallback_required": false,
    "contract_type": "korea_payroll_closing_browser_runtime_walkthrough_v1",
    "runtime_action": "browser_runtime_read_only"
  }
}
```

- `runtime_verified: true` (top-level): 첫 positive proof
- `fixture_fallback_required: false`: 정적 fallback 의존 없음 — 실제 인증 브라우저가 read-only 데이터를 응답
- `credential_apply.human_approval_verified: true`: 명시 승인 적용
- `mutation_boundary` 위반 없음

---

## 4. 인증 브라우저가 호출한 read-only API (browser verifier 관측)

```
hrms.api.get_current_employee_info
hrms.api.get_current_user_info
hrms.api.get_unread_notifications_count
hrms.api.are_push_notifications_enabled
frappe.translate.load_all_translations
notification_relay.api.get_config
hrms.regional.south_korea.admin_dashboard_runtime_api.get_korea_admin_dashboard_runtime    ← 한국 모듈
hrms.regional.south_korea.payroll_closing_worklist_runtime_api.list_korea_payroll_closing_worklist_runtime  ← 한국 모듈
frappe.auth.get_logged_user
```

- 9개 API 모두 인증 세션에서 정상 응답
- 한국 페이롤 마감 모듈 (`admin_dashboard_runtime_api`, `payroll_closing_worklist_runtime_api`)이 실제 인증 브라우저에서 read-only 데이터를 반환함 — Gate 14 핵심 contract 충족

---

## 5. Mutation 경계 준수

검증 실행은 다음 mutation 경계 안에서 종료됨:
- `mutation_boundary: credential_only_then_browser_read_only_no_payroll_submit_approve_send_provider_call`
- credential apply: `demo.hr.manager@node.pe.kr` 1명에 한정된 비밀번호 update만 수행
- browser verification: 모든 호출 read-only API (`get_*`, `load_*`, `list_*`)만 관측
- 페이롤 submit/approve/send/provider call: 없음
- AI 자동 mutation: 없음 (모든 mutation은 operator-provided secret + explicit human-approval 통과 후에만)

---

## 6. 환경 메모

| 항목 | 값 |
|------|-----|
| 서버 HEAD | `1f5e86995` (현재 develop) |
| Site | `hrms.localhost` |
| host_name | `https://hrms.safeclaw.kr` |
| Company | `노란봉투법 데모` |
| Username | `demo.hr.manager@node.pe.kr` |
| Browser | `chromium-browser` (host: `/usr/bin/chromium-browser`) |
| Docker | `docker-frappe-1`, `docker-mariadb-1`, `docker-redis-1` Up |
| Base URL (검증) | `http://localhost:8000` (loopback) |

---

## 7. 추후 자동화 권고 (cron이 같은 결과 산출하려면)

1. **DNS resolution fallback**: `verify_korea_payroll_closing_browser_runtime.mjs`가 외부 도메인 `fetch failed` 시 자동으로 loopback `http://localhost:8000`으로 fallback 시도 추가 (optional)
2. **operator secret provisioning**: cron 런타임에 `FRAPPE_BROWSER_PASSWORD`를 안전한 secret manager로 주입 (예: file-based with 600 perm, env var injection at cron exec time)
3. **base-url override**: cron 환경변수 `FRAPPE_BROWSER_BASE_URL`를 통해 cron 자체적으로 loopback 선호 가능

위 권고는 mutation boundary를 확대하지 않음 — credential apply는 여전히 `--human-approved` 명시 필요.

---

## 8. 다음 단계

- Gate 14 closeout — 본 evidence 머지 후 HERMES_WORKSPACE.md "Latest authenticated-browser status" 섹션이 positive proof로 갱신될 수 있음
- Gate 15 candidate (cron이 다음 게이트로 진행 가능):
  - 페이롤 계산 정밀도 (statutory_payroll, payroll_salary_slip_adapter end-to-end)
  - 컴플라이언스 진단 (compliance_diagnosis_api 실제 결과 산출)
  - 카카오 알림 (kakao_notification 실제 발송 path)
  - 연차 마감 (annual_leave + attendance_summary closing)
  - 인증된 브라우저 검증을 다른 화면 (Salary Slip / Leave / Approval Inbox)으로 확장

## 부록 A. Full run report (redacted)

전체 redacted JSON 보고서:
- `/tmp/gate14-final-redacted.json` (74 lines, 호스트)
- `/tmp/gate14-browser-final.json` (45 lines, 호스트)

이 evidence 파일은 비밀번호 노출 위험으로 repo에 직접 포함하지 않으며, 운영자가 필요 시 동일 명령으로 재현 가능.
