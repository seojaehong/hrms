# Korea Launch Gap Audit

기준 시점: 2026-04-24
레포: `/home/ubuntu/workspaces/frappe-hrms`

## 사실
- `sudo docker compose ps` 기준 `frappe`, `mariadb`, `redis` 컨테이너 모두 Up 상태.
- `frappe` 로그 기준 ERPNext/HRMS 설치가 완료되었고 web/socketio/schedule/worker 프로세스가 기동됨.
- `hrms/locale` 아래 `ko.po`를 신규 추가했다.
- `hrms/regional` 아래 한국 패키지로 `south_korea`와 실제 Country slug 대응용 `korea_republic_of`를 추가했다.
- 개발 사이트(`hrms.localhost`)에 한국 커스텀 필드와 한국 급여 컴포넌트 1차를 실제 반영했다.
- Frappe Country 마스터에서 한국 국명은 `Korea, Republic of`로 조회된다.

## 해석
- 한국화는 더 이상 "계획만 있는 상태"가 아니라, 개발 사이트에 1차 스캐폴드가 적용된 상태다.
- Country 기반 자동 regional setup은 `korea_republic_of` slug를 우선 기준으로 맞추는 것이 안전하다.
- 다음 단계는 법/4대보험 기준값과 휴일/휴가/교대 운영 템플릿을 실제 DocType 데이터로 주입하는 것이다.

## 리스크
1. `ko.po`는 핵심 동선 위주의 초안이므로 전체 UI 한국어화는 아직 미완성.
2. 급여 컴포넌트는 이름/분류 스캐폴드이며, 법정 계산식은 아직 연결 전.
3. 법/보험 기준값은 `.hermes/KOREA_LEGAL_RULES_INPUT.yaml`에 빈 값이 남아 있어 사용자 입력이 필요.
4. 브라우저 E2E는 엔드포인트 응답은 확인했지만 시각 흐름 검증은 추가 정리 필요.

## 권고
- 내일은 실제 로그인 후 Company/Employee/Salary Component 화면에서 필드 노출을 먼저 확인.
- 사용자 기준표를 받는 즉시 `.hermes/KOREA_LEGAL_RULES_INPUT.yaml`과 regional data를 2차 업데이트.
- 그 다음 Holiday List / Leave Policy / Shift Type 샘플 레코드를 실제 사이트에 생성.
