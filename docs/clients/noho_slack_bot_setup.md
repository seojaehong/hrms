# NOHO 슬랙 봇 셋업 가이드
> 채널: `#hrms-beta-noho` (thenoho workspace)
> 구현 옵션: n8n webhook (권장) 또는 자체 봇

---

## 개요

HRMS에서 발생하는 이벤트(휴가 승인, 급여 마감, 근태 이상)를 슬랙 채널로 자동 알림.
카카오 알림톡과 병행 또는 대체 용도로 활용 가능.

---

## 옵션 A — n8n Webhook (권장)

### 전제 조건
- n8n 인스턴스 가동 중 (서버2 또는 n8n Cloud)
- thenoho 슬랙 워크스페이스 관리자 권한

### 1단계: 슬랙 앱 생성

1. https://api.slack.com/apps 접속 → **Create New App** → **From scratch**
2. App Name: `HRMS Bot`  |  Workspace: `thenoho`
3. **OAuth & Permissions** > Bot Token Scopes 추가:
   - `chat:write`
   - `chat:write.public`
   - `channels:read`
4. **Install to Workspace** → Bot Token (`xoxb-...`) 복사

### 2단계: n8n 워크플로우 구성

```
[Webhook Trigger]
  ↓ POST /webhook/hrms-noho
[Switch Node]  — event_type 분기
  ├─ leave_approved    → [Slack: #hrms-beta-noho] 메시지 발송
  ├─ leave_rejected    → [Slack: #hrms-beta-noho] 메시지 발송
  ├─ payroll_closing   → [Slack: #hrms-beta-noho] 메시지 발송
  └─ compliance_alert  → [Slack: #hrms-beta-noho] @channel 멘션
```

**n8n Slack Node 설정**:
- Credential: Slack OAuth2 (Bot Token)
- Channel: `#hrms-beta-noho`
- Text: 이벤트별 메시지 템플릿 (아래 참조)

### 3단계: HRMS Webhook 설정

```bash
bench --site noho.hrms.safeclaw.kr set-config \
  SLACK_WEBHOOK_URL "https://n8n.your-server.com/webhook/hrms-noho"
```

또는 Frappe Desk에서:
```
설정 > 시스템 설정 > 한국 HRMS 알림 > 슬랙 Webhook URL 입력
```

### 메시지 템플릿 예시

```
[휴가 승인] {employee_name}님의 {leave_type} 신청이 승인되었습니다.
기간: {from_date} ~ {to_date} ({days}일)
승인자: {approver}

[급여 마감] {period} 급여 마감이 완료되었습니다.
대상: {count}명 | 총액: {total}원
담당: @재홍 검수 완료

[컴플라이언스] :warning: {alert_title}
조치 기한: {due_date}
```

---

## 옵션 B — 자체 Python 봇 (심화)

> n8n이 없거나 세밀한 제어가 필요할 때 사용.

### 구조

```
hrms/regional/south_korea/
  slack_notifier.py        ← 기존 kakao_notification.py 패턴 동일
  slack_templates.json     ← 채널별 메시지 템플릿
```

### 구현 스케치

```python
# slack_notifier.py
import frappe
import requests

def send_slack_message(channel: str, text: str, blocks: list = None):
    webhook_url = frappe.conf.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        frappe.logger().warning("SLACK_WEBHOOK_URL not configured")
        return

    payload = {"text": text, "channel": channel}
    if blocks:
        payload["blocks"] = blocks

    resp = requests.post(webhook_url, json=payload, timeout=10)
    resp.raise_for_status()

def notify_leave_approved(doc, method=None):
    send_slack_message(
        channel="#hrms-beta-noho",
        text=f"[휴가 승인] {doc.employee_name}님의 {doc.leave_type} 승인 완료 "
             f"({doc.from_date} ~ {doc.to_date})"
    )
```

### 훅 등록

```python
# hooks.py에 추가
doc_events = {
    "Leave Application": {
        "on_submit": "hrms.regional.south_korea.slack_notifier.notify_leave_approved",
    }
}
```

---

## 옵션 비교

| 항목 | n8n (A) | 자체 봇 (B) |
|------|---------|------------|
| 구현 난이도 | 낮음 (UI 설정) | 중간 (Python 코딩) |
| 유지보수 | n8n 워크플로우 수정 | 코드 수정 후 배포 |
| 유연성 | 중간 | 높음 |
| 외부 의존성 | n8n 인스턴스 | 없음 |
| 권장 시점 | 베타 즉시 적용 | 정식 전환 후 |

---

## 셋업 체크리스트

- [ ] **재홍님**: thenoho 슬랙 워크스페이스 관리자 권한 확인
- [ ] **재홍님**: 슬랙 `#hrms-beta-noho` 채널 생성 + 관련자 초대
- [ ] 슬랙 앱 생성 + Bot Token 발급
- [ ] 옵션 A: n8n 워크플로우 구성 + Webhook URL 등록
- [ ] 옵션 B: `slack_notifier.py` 구현 + hooks.py 등록 + site restart
- [ ] 테스트: 휴가 신청 1건 제출 → 슬랙 채널 메시지 수신 확인
- [ ] 테스트: 급여 마감 → 슬랙 알림 수신 확인

---

## 주의 사항

- 슬랙 Bot Token(`xoxb-...`)은 HRMS site config 또는 환경변수로 관리 (코드에 하드코딩 금지)
- 민감 정보(급여 금액)는 슬랙 채널 대신 카카오 알림톡 개인 발송 권장
- 슬랙 채널 메시지는 내부 운영용, 직원 개별 알림은 카카오 알림톡 사용
