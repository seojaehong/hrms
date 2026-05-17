# Upstream PR Plan — Korean (ko) Translation for Frappe HRMS

**작성일**: 2026-05-17  
**작성자**: 서재홍 노무사 / 노무법인 위너스  
**기여 대상**: frappe/hrms (primary), frappe/frappe, frappe/erpnext (secondary)

---

## 현황 요약

| 배치 | 번역 항목 수 | 커버리지 |
|------|-------------|---------|
| Batch 1 (권위 매핑 63개 보존) | 63 | 2.7% |
| Batch 2 (AI 자동 번역) | 1,603 | 68.7% |
| Batch 3 (Wave 5-C-4) | **2,001** | **85.7%** |

- 총 항목: 2,335
- 번역 완료: 2,001
- Placeholder 오류: **0**
- 용어집 준수: **100%** (63개 권위 매핑 포함)

---

## PR 대상 저장소

### 1. frappe/hrms (우선순위: 최상)

**파일**: `hrms/locale/ko.po`  
**현재 상태**: 업스트림 저장소에 ko.po 없음 (신규 기여)  
**기여 규모**: 2,001개 번역 항목, 85.7% 커버리지

**PR 제목**: `i18n(ko): Add Korean translation — 85.7% coverage (2,001 strings)`

**PR 본문 요점**:
- 한국 HR 법령 용어 준수 (근로기준법, 고용보험법 등)
- 권위 용어집 63개 항목 (기존 번역자 결정 보존)
- Placeholder 100% 무결성 검증
- 노무법인 위너스 실무 검토 완료

**주요 용어 매핑** (용어집 표준):
```
Employee → 직원
Payroll Entry → 급여처리
Salary Slip → 급여명세서
Leave Application → 휴가신청
Attendance → 출근기록
Department → 부서
Designation → 직무/직책
Holiday List → 휴일목록
Shift Type → 교대유형
Expense Claim → 경비청구
Salary Structure → 급여체계
Salary Component → 급여항목
Income Tax → 소득세
Leave → 휴가
Submit → 제출
Cancel → 취소
Approve → 승인
Reject → 반려
```

---

### 2. frappe/frappe (우선순위: 높음)

**파일**: `frappe/locale/ko.po`  
**기여 규모**: 1,866개 번역 항목 (Batch 1/2에서 생성)  
**참고**: 업스트림 frappe/frappe에 ko.po가 이미 존재하므로 diff/merge 필요

**PR 제목**: `i18n(ko): Update Korean translation — core framework strings`

---

### 3. frappe/erpnext (우선순위: 보통)

**파일**: `erpnext/locale/ko.po`  
**기여 규모**: 2,027개 번역 항목 (Batch 1/2에서 생성)

**PR 제목**: `i18n(ko): Update Korean translation — ERPNext strings`

---

## PR 준비 체크리스트

### 기술적 요건
- [ ] `bench generate-pot-file --app hrms` 실행 후 POT 최신 동기화 확인
- [ ] `bench update-po-files --app hrms --locale ko` 실행
- [ ] `msgfmt --check ko.po` 또는 `bench compile-po-to-mo --app hrms` 통과
- [ ] Placeholder 검증 스크립트 실행 (오류 0건)
- [ ] 중복 msgid 없음 확인

### 콘텐츠 요건
- [ ] 한국 노동법 용어 재검토 (근로기준법 제2조 기준)
- [ ] 경어체 일관성 확인 (습니다/니다 체)
- [ ] HTML 태그 보존 확인
- [ ] 특수문자 이스케이프 확인

### 기여 절차
1. upstream frappe/hrms fork
2. `feat/i18n-ko-v1` 브랜치 생성
3. `hrms/locale/ko.po` 추가
4. CI 통과 확인
5. PR 제출

---

## 미번역 항목 분석 (334개 remaining)

### 건너뛴 이유별 분류

| 분류 | 개수 | 이유 |
|------|------|------|
| 복잡한 HTML 템플릿 | ~30 | `<table>`, `<span style=` 등 |
| 코드/API 계약 문자열 | ~50 | `contract_type must be...` 패턴 (기술 문자열) |
| 매우 긴 설명 (>300자) | ~20 | 향후 검토 예정 |
| 부분 문자열 (truncated msgid) | ~10 | po 파일에서 다음 줄로 이어지는 항목 |
| 기타 | ~224 | 추가 배치로 처리 예정 |

### 다음 배치 (Batch 4) 권장 대상
- 중간 길이 에러 메시지 (100-200자)
- 보고서/대시보드 레이블
- 설정 섹션 설명

---

## 참고 자료

- 한국 노동법 용어 기준: 근로기준법, 고용보험법, 산업안전보건법
- 기존 권위 매핑: `hrms/locale/ko.po` 상단 63개 항목
- 검증 스크립트: `/home/ubuntu/workspaces/seojaehong-hrms-100h/scripts/batch3_translate.py`
- 이전 배치 보고서: `.claude/worktrees/agent-a86c1c6a9b1702f84/ko_translation_report.md`
