# HRMS Korea Demo Launch Info

## Public demo link
- URL: https://patrick-alice-program-cpu.trycloudflare.com
- App path: https://patrick-alice-program-cpu.trycloudflare.com/app
- Note: Cloudflare quick tunnel (temporary). Keep process `proc_56fea374faad` alive.

## Demo login
- Username: demo.hr.manager@node.pe.kr
- Password: DemoHRMS!2026

## Seeded records
- Company: 노란봉투법 데모
- Holiday List: KR Public Holidays 2026 Demo (19 holidays)
- Shift Type: KR Standard Day Shift 09-18
- Leave Types: Annual Leave / Sick Leave / Family Event Leave
- Employees: HR-EMP-00001 김민지, HR-EMP-00002 박현우
- Salary Structure: KR Demo Salary Structure

## Policy baseline
- File: /home/ubuntu/workspaces/frappe-hrms/.hermes/KOREA_LEGAL_RULES_INPUT.yaml
- Includes demo defaults for 40h week, overtime/night/holiday premiums, 4대보험 baseline, withholding tax notes.

## Runtime
- Frappe local URL: http://10.0.0.58:8000
- Docker compose dir: /home/ubuntu/workspaces/frappe-hrms/docker
- Public tunnel log: /tmp/hrms-cloudflared.log
