#!/usr/bin/env python3
"""
HRMS ko.po Batch 3 Translation Script
Wave 5-C-4: 1,603 → 1,900+ (80%+ coverage)
No external LLM API - translations inline
"""

import re
import sys
import shutil
from datetime import datetime

KO_PO_PATH = "/home/ubuntu/workspaces/seojaehong-hrms-100h/hrms/locale/ko.po"
CONTAINER_PO_PATH = "/home/frappe/frappe-bench/apps/hrms/hrms/locale/ko.po"

# ============================================================
# Batch 3 Translations (Claude Sonnet 4.6, no external API)
# Glossary compliance:
#   Employee → 직원
#   Salary Slip → 급여명세서
#   Leave → 휴가
#   Leave Application → 휴가신청
#   Payroll → 급여처리
#   Department → 부서
#   Designation → 직무/직책
#   Attendance → 출근기록
#   Submit → 제출
#   Cancel → 취소
#   Approve → 승인
#   Reject → 반려
#   Company → 회사
#   Holiday → 휴일
#   Shift → 교대
#   Expense Claim → 경비청구
#   Salary Structure → 급여체계
#   Salary Component → 급여항목
#   Income Tax → 소득세
#   Provident Fund → 퇴직연금
#   Appraisal → 평가
#   Job Applicant → 입사지원자
#   Staffing Plan → 인력계획
# ============================================================

BATCH3_TRANSLATIONS = {
    # ---- Short UI Labels ----
    "Filled": "채워짐",
    "Timing": "시간대",
    "Showing": "표시 중",
    "Manually": "수동으로",
    "Withheld": "보류됨",
    "Non Diary": "비일지",
    "Every Week": "매주",
    "Is Expired": "만료됨",
    "Offer Term": "제안 조건",
    "Expected By": "기대 기한",
    "Explanation": "설명",
    "My Requests": "내 요청",
    "Offer Terms": "제안 조건 목록",
    "Revised CTC": "조정된 CTC",
    "No {0} added": "{0} 없음",
    "Payload JSON": "페이로드 JSON",
    "Requested By": "요청자",
    "Team Updates": "팀 업데이트",
    "Yes, Proceed": "예, 진행",
    "Every 2 Weeks": "격주",
    "Every 3 Weeks": "3주마다",
    "Every 4 Weeks": "4주마다",
    "Team Requests": "팀 요청",
    "Type of Proof": "증빙 유형",
    "Repeat On Days": "반복 요일",
    "Send Emails At": "이메일 발송 시간",
    "Total in words": "합계 (문자)",
    "Creating {0}...": "{0} 생성 중...",
    "Existing Record": "기존 레코드",
    "No {0} Selected": "{0} 선택 안 됨",
    "Over Allocation": "초과 배정",
    "Select Property": "속성 선택",
    "Taxes & Charges": "세금 및 공제",
    "Default Base Pay": "기본급 기본값",
    "For Designation ": "직무 대상 ",
    "Purpose & Amount": "목적 및 금액",
    "Responsibilities": "담당 업무",
    "Settings Missing": "설정 누락",
    "johndoe@mail.com": "gildong@mail.com",
    "Name of Organizer": "주최자 이름",
    "View Salary Slips": "급여명세서 보기",
    "Worked On Holiday": "휴일 근무",
    "Total Leaves ({0})": "총 휴가일수 ({0})",
    "Weekend Multiplier": "주말 배율",
    "Requested By (Name)": "요청자 (이름)",
    "Value / Description": "값 / 설명",
    "You have no requests": "요청이 없습니다",
    "Project Profitability": "프로젝트 수익성",
    "Reason for Adjustment": "조정 사유",
    "Reason for Requesting": "요청 사유",
    "Status for Other Half": "나머지 반일 상태",
    "Payment and Accounting": "지급 및 회계",
    "Other Taxes and Charges": "기타 세금 및 공제",
    "Requires Human Approval": "사람 승인 필요",
    "Total Receivable Amount": "총 수령 금액",
    "Encashment Limit Applied": "현금화 한도 적용됨",
    "Future dates not allowed": "미래 날짜 불가",
    "Source Runtime Apply JSON": "소스 런타임 적용 JSON",
    "Sum of all previous slabs": "이전 구간 합계",
    "You have no notifications": "알림이 없습니다",
    "Take Exact Completed Years": "완료 연수 정확히 적용",
    "<h5>Unmarked Employees</h5>": "<h5>미처리 직원</h5>",
    "Partly Claimed and Returned": "일부 청구 후 반납",
    "Select Terms and Conditions": "약관 선택",
    "Total working Days Per Year": "연간 총 근무일수",
    "You have no upcoming shifts": "예정된 교대가 없습니다",
    "No changes found in timings.": "시간대 변경 사항 없음.",
    "Payment Account is mandatory": "지급 계정은 필수입니다",
    "Round to the Nearest Integer": "정수로 반올림",
    "Max Amount Eligible For Claim": "청구 가능 최대 금액",
    "Net Pay cannot be less than 0": "실수령액은 0 미만이 될 수 없습니다",
    "Select Month for LWP Reversal": "무급결근 환원 월 선택",
    "<h5>Employees on Half Day</h5>": "<h5>반일 근무 직원</h5>",
    "Payment of {0} from {1} to {2}": "{1}부터 {2}까지 {0} 지급",
    "Please set {0} and {1} in {2}.": "{2}에서 {0}과 {1}을 설정하세요.",
    "Copy of Invitation/Announcement": "초대/공지 사본",
    "Default Payroll Payable Account": "기본 급여미지급 계정",
    "Employee {0} is on Leave on {1}": "직원 {0}은(는) {1}에 휴가 중입니다",
    "Employee {0} on Half day on {1}": "직원 {0}은(는) {1}에 반일 근무입니다",
    "Taxes and Charges on Income Tax": "소득세 관련 세금 및 공제",
    "apply_plan.docstatus must be 0.": "apply_plan.docstatus는 0이어야 합니다.",
    "audit_log must be a JSON object.": "audit_log는 JSON 객체여야 합니다.",
    "Half Day Date cannot be a holiday": "반일 날짜는 휴일이 될 수 없습니다",
    "No valid shift found for log time": "로그 시간에 유효한 교대가 없습니다",
    "Total in words (Company Currency)": "합계 (문자, 회사 통화)",
    "apply_plan must be a JSON object.": "apply_plan은 JSON 객체여야 합니다.",
    "source_draft.docstatus must be 0.": "source_draft.docstatus는 0이어야 합니다.",
    "A {0} exists between {1} and {2} (": "{1}과 {2} 사이에 {0}이 존재합니다 (",
    "From Date must come before To Date": "시작일은 종료일보다 앞서야 합니다",
    "Set the status to {0} if required.": "필요 시 상태를 {0}으로 설정하세요.",
    "To date cannot be before from date": "종료일은 시작일보다 앞설 수 없습니다",
    "apply_plan.actor must match actor.": "apply_plan.actor는 actor와 일치해야 합니다.",
    "audit_log.status must match action.": "audit_log.status는 action과 일치해야 합니다.",
    "{0} is not in Optional Holiday List": "{0}은(는) 선택적 휴일 목록에 없습니다",
    "End time cannot be before start time": "종료 시간은 시작 시간보다 앞설 수 없습니다",
    "Linked Project {} and Tasks deleted.": "연결된 프로젝트 {}와 작업이 삭제되었습니다.",
    "Please set {0} for the Employee: {1}": "직원 {1}에 대해 {0}을 설정하세요",
    "Reason for skipping auto attendance:": "자동 출근기록 건너뜀 사유:",
    "To allow this, enable {0} under {1}.": "허용하려면 {1}에서 {0}을 활성화하세요.",
    "review_action must be a JSON object.": "review_action은 JSON 객체여야 합니다.",
    "Check Error Log {0} for more details.": "자세한 내용은 오류 로그 {0}을 확인하세요.",
    "Default Expense Claim Payable Account": "기본 경비청구 미지급 계정",
    "Fraction of Daily Salary for Half Day": "반일 급여 비율",
    "Score must be less than or equal to 5": "점수는 5 이하여야 합니다",
    "Time taken to fill the open positions": "공석 충원 소요 시간",
    "review_action.actor must match actor.": "review_action.actor는 actor와 일치해야 합니다.",
    "Could not submit some Salary Slips: {}": "일부 급여명세서를 제출하지 못했습니다: {}",
    "No Salary Slip found for Employee: {0}": "직원 {0}의 급여명세서를 찾을 수 없습니다",
    "To date can not be less than from date": "종료일은 시작일보다 앞설 수 없습니다",
    "You haven't created a {0} for {1} yet.": "{1}에 대한 {0}을 아직 생성하지 않았습니다.",
    "{0}. Check error log for more details.": "{0}. 자세한 내용은 오류 로그를 확인하세요.",
    "Are you sure you want to delete the {0}": "{0}을(를) 삭제하시겠습니까?",
    "Please select the salary slips to email": "이메일로 보낼 급여명세서를 선택하세요",
    "Set the default account for the {0} {1}": "{0} {1}에 대한 기본 계정을 설정하세요",
    "Start time and end time cannot be same.": "시작 시간과 종료 시간은 같을 수 없습니다.",
    "Total Expense Claim (via Expense Claim)": "총 경비청구 (경비청구서 기준)",
    "Updated the Job Applicant status to {0}": "입사지원자 상태를 {0}(으)로 업데이트했습니다",
    "Bonus Payment Date cannot be a past date": "보너스 지급일은 과거 날짜가 될 수 없습니다",
    "Date {0} is repeated in Overtime Details": "날짜 {0}이 초과근무 상세에 중복됩니다",
    "Deduct Full Tax on Selected Payroll Date": "선택한 급여처리일에 세금 전액 공제",
    "This error can be due to invalid syntax.": "이 오류는 잘못된 구문으로 인한 것일 수 있습니다.",
    "To Date should be greater than From Date": "종료일은 시작일보다 뒤여야 합니다",
    "Total Expense Claim (via Expense Claims)": "총 경비청구 (경비청구서 복수 기준)",
    "Failed to setup defaults for country {0}.": "국가 {0}에 대한 기본값 설정에 실패했습니다.",
    "Failed to update the Job Applicant status": "입사지원자 상태 업데이트에 실패했습니다",
    "House rent paid days overlapping with {0}": "주거비 지급일이 {0}과 중복됩니다",
    "Maximum encashable leaves for {0} are {1}": "{0}의 최대 현금화 가능 휴가일수는 {1}입니다",
    "Submit this to create the Employee record": "제출하여 직원 레코드를 생성하세요",
    "audit_log.ai_role must be assistant_only.": "audit_log.ai_role은 assistant_only여야 합니다.",
    "Days to Reverse must be greater than zero.": "환원 일수는 0보다 커야 합니다.",
    "Excluded {0} Non-Encashable Leaves for {1}": "{1}의 비현금화 휴가 {0}일 제외됨",
    "Failed to delete defaults for country {0}.": "국가 {0}의 기본값 삭제에 실패했습니다.",
    "Please set a date range less than 90 days.": "90일 미만의 날짜 범위를 설정하세요.",
    "Please set account in Salary Component {0}": "급여항목 {0}에 계정을 설정하세요",
    "Start date cannot be greater than end date": "시작일은 종료일보다 늦을 수 없습니다",
    "Structures have been assigned successfully": "급여체계가 성공적으로 배정되었습니다",
    "apply_plan.ai_role must be assistant_only.": "apply_plan.ai_role은 assistant_only여야 합니다.",
    "Account {0} does not match with Company {1}": "계정 {0}이 회사 {1}과 일치하지 않습니다",
    "Benefit amount of component {0} exceeds {1}": "항목 {0}의 복리후생 금액이 {1}을 초과합니다",
    "More than one selection for {0} not allowed": "{0}에 대한 복수 선택은 허용되지 않습니다",
    "Password policy for Salary Slips is not set": "급여명세서 비밀번호 정책이 설정되지 않았습니다",
    "Please set Relieving Date for employee: {0}": "직원 {0}의 퇴직일을 설정하세요",
    "Route to the custom Job Application Webform": "사용자 정의 입사지원 웹양식으로 이동",
    "Shift has been successfully updated to {0}.": "교대가 {0}(으)로 성공적으로 업데이트되었습니다.",
    "Source and target shifts cannot be the same": "소스와 대상 교대는 같을 수 없습니다",
    "Start date cannot be greater than end date.": "시작일은 종료일보다 늦을 수 없습니다.",
    "Submission of {0} before {1} is not allowed": "{1} 이전의 {0} 제출은 허용되지 않습니다",
    "Employee {0} is not active or does not exist": "직원 {0}이 활성 상태가 아니거나 존재하지 않습니다",
    "Leave of type {0} cannot be longer than {1}.": "{0} 유형의 휴가는 {1}보다 길 수 없습니다.",
    "No Staffing Plans found for this Designation": "해당 직무에 대한 인력계획이 없습니다",
    "No employees found for the selected criteria": "선택한 조건에 해당하는 직원이 없습니다",
    "Please set the Advance Account {0} or in {1}": "선급금 계정 {0} 또는 {1}에 설정하세요",
    "Salary Slip {0} failed for Payroll Entry {1}": "급여명세서 {0}이 급여처리 {1}에 실패했습니다",
    "This method is only meant for developer mode": "이 메서드는 개발자 모드 전용입니다",
    "source_draft.ai_role must be assistant_only.": "source_draft.ai_role은 assistant_only여야 합니다.",
    "Appraisal {0} does not belong to Employee {1}": "평가 {0}은 직원 {1}에 속하지 않습니다",
    "Include holidays in Total no. of Working Days": "총 근무일수에 휴일 포함",
    "Insufficient leave balance for Leave Type {0}": "{0} 유형의 휴가 잔여일수가 부족합니다",
    "Mode of payment is required to make a payment": "지급하려면 지급 방법이 필요합니다",
    "No leave record found for employee {0} on {1}": "직원 {0}의 {1} 휴가 기록을 찾을 수 없습니다",
    "Period start must be on or before period end.": "기간 시작일은 기간 종료일과 같거나 앞서야 합니다.",
    "To(Year) year can not be less than From(year)": "종료 연도는 시작 연도보다 앞설 수 없습니다",
    "Today {0} completed {1} {2} at our Company! 🎉": "오늘 {0}이(가) 우리 회사에서 {1} {2}을(를) 완료했습니다! 🎉",
    "audit_log.audit_actor must match audit_actor.": "audit_log.audit_actor는 audit_actor와 일치해야 합니다.",
    "doctype_insert_preview must be a JSON object.": "doctype_insert_preview는 JSON 객체여야 합니다.",
    "review_action.ai_role must be assistant_only.": "review_action.ai_role은 assistant_only여야 합니다.",
    "Deduct Tax For Unsubmitted Tax Exemption Proof": "미제출 세금 면제 증빙에 대한 세금 공제",
    "Department {0} does not belong to company: {1}": "부서 {0}은 회사 {1}에 속하지 않습니다",
    "No attendance records found for this criteria.": "이 조건에 해당하는 출근기록이 없습니다.",
    "Payout Unclaimed Amount in Final Payroll Cycle": "최종 급여처리에서 미청구 금액 지급",
    "Please set the relieving date for employee {0}": "직원 {0}의 퇴직일을 설정하세요",
    "Row {0}: Goal Score cannot be greater than {1}": "행 {0}: 목표 점수는 {1}보다 클 수 없습니다",
    "Salary breakup based on Earning and Deduction.": "지급 및 공제 기준 급여 내역.",
    "Select Applicable Components for Overtime Type": "초과근무 유형에 적용 가능한 항목 선택",
    "Strictly based on Log Type in Employee Checkin": "직원 체크인의 로그 유형에 엄격히 기반",
    "There are no vacancies under staffing plan {0}": "인력계획 {0}에 공석이 없습니다",
    "audit_log.requires_runtime_apply must be true.": "audit_log.requires_runtime_apply는 true여야 합니다.",
    "audit_log.runtime_action must be preview_only.": "audit_log.runtime_action은 preview_only여야 합니다.",
    "Failed to submit some leave policy assignments:": "일부 휴가 정책 배정 제출에 실패했습니다:",
    "Please create a new {0} for the date {1} first.": "먼저 날짜 {1}에 대한 새 {0}을 생성하세요.",
    "Please set Leave Approver for the Employee: {0}": "직원 {0}의 휴가 승인자를 설정하세요",
    "Please set Payroll based on in Payroll settings": "급여처리 설정에서 급여처리 기준을 설정하세요",
    "Please set the Date Of Joining for employee {0}": "직원 {0}의 입사일을 설정하세요",
    "Please specify the job applicant to be updated.": "업데이트할 입사지원자를 지정하세요.",
    "Select an employee to get the employee advance.": "직원 선급금을 받을 직원을 선택하세요.",
    "Select the end date for your Leave Application.": "휴가신청의 종료일을 선택하세요.",
    "Selected employee advance is not of employee {}": "선택한 직원 선급금은 직원 {}의 것이 아닙니다",
    "Self-approval for Expense Claims is not allowed": "경비청구서 자기 승인은 허용되지 않습니다",
    "Shift Assignment: {0} created for Employee: {1}": "교대 배정: {1} 직원에 대해 {0}이(가) 생성되었습니다",
    "To date can not be equal or less than from date": "종료일은 시작일과 같거나 앞설 수 없습니다",
    "You can not request for your Default Shift: {0}": "기본 교대 {0}에 대한 요청은 할 수 없습니다",
    "apply_plan.requires_runtime_apply must be true.": "apply_plan.requires_runtime_apply는 true여야 합니다.",
    "audit_log.requires_human_approval must be true.": "audit_log.requires_human_approval은 true여야 합니다.",
    "Approval Status must be 'Approved' or 'Rejected'": "승인 상태는 '승인' 또는 '반려'여야 합니다",
    "Failure of Automatic Allocation of Earned Leaves": "적립 휴가 자동 배정 실패",
    "No {0} found for employee {1}. Please set {2} in": "직원 {1}에 대한 {0}을 찾을 수 없습니다. {2}를 설정하세요",
    "Payment Days are linked to Timesheet. To disable": "지급일이 근무표에 연결되어 있습니다. 비활성화하려면",
    "Please fill in the basic details to get started.": "시작하려면 기본 정보를 입력하세요.",
    "Set {0} amount based on Employee Grade to {1} {2}": "직원 등급을 기준으로 {0} 금액을 {1} {2}로 설정",
    "Shift {0}: {1} - {2} overlapping with Employee {3}": "교대 {0}: {1} - {2}가 직원 {3}과 중복됩니다",
    "Total taxable earnings for the current Payroll:": "현재 급여처리의 총 과세 소득:",
    "apply_plan.source_draft_contract_type must be": "apply_plan.source_draft_contract_type은",
    "review_action.would_set_status must be a guarded human-review result status.": "review_action.would_set_status는 감시된 인사 검토 결과 상태여야 합니다.",
    "Allocation was skipped due to exceeding annual allocation set in leave policy": "휴가 정책의 연간 배정 초과로 배정을 건너뛰었습니다",
    "Arrear Component cannot be set for Salary Components based on taxable salary.": "소급분 항목은 과세 급여 기반 급여항목에 설정할 수 없습니다.",
    "Attendance for all the employees under this criteria has been marked already.": "해당 조건의 모든 직원 출근기록이 이미 처리되었습니다.",
    "Enabled only for Employee Benefit components from Salary Structure Assignment": "급여체계 배정의 직원 복리후생 항목에만 활성화됨",
    "Income Tax Slab must be effective on or before Payroll Period Start Date: {0}": "소득세 구간은 급여처리 기간 시작일 {0} 이전에 유효해야 합니다",
    "Korea Payroll Closing Draft already exists for this company/workplace/period.": "이 회사/사업장/기간에 대한 한국 급여 마감 초안이 이미 존재합니다.",
    "Mark attendance for existing check-in/out logs before changing shift settings": "교대 설정 변경 전에 기존 체크인/아웃 로그의 출근기록을 처리하세요",
    "Multipliers that adjust the hourly overtime amount for specific scenarios\n\n": "특정 상황에 따라 시간당 초과근무 금액을 조정하는 배율\n\n",
    "Total of all employee benefits cannot be greater that Max Benefits Amount {0}": "모든 직원 복리후생 합계가 최대 복리후생 금액 {0}을 초과할 수 없습니다",
    "apply_plan.source_draft_contract_type must be korea_payroll_closing_draft_v1.": "apply_plan.source_draft_contract_type은 korea_payroll_closing_draft_v1이어야 합니다.",
    "audit_log.action must be one of approve_draft, reject_draft, request_changes.": "audit_log.action은 approve_draft, reject_draft, request_changes 중 하나여야 합니다.",
    "Only Leave Applications with status 'Approved' and 'Rejected' can be submitted": "상태가 '승인' 또는 '반려'인 휴가신청만 제출할 수 있습니다",
    "Salary Withholding {0} already exists for employee {1} for the selected period": "직원 {1}의 선택 기간에 급여 보류 {0}이(가) 이미 존재합니다",
    "There is no Salary Structure assigned to {0}. First assign a Salary Structure.": "{0}에 배정된 급여체계가 없습니다. 먼저 급여체계를 배정하세요.",
    "audit_log.would_create_doctype must be Korea Payroll Closing Review Audit Log.": "audit_log.would_create_doctype은 Korea Payroll Closing Review Audit Log여야 합니다.",
    "{0} Row #{1}: Formula is set but {2} is disabled for the Salary Component {3}.": "{0} 행 #{1}: 수식이 설정되어 있지만 급여항목 {3}에서 {2}가 비활성화되어 있습니다.",
    "Allows allocating more leaves than the number of days in the allocation period.": "배정 기간의 일수보다 더 많은 휴가를 배정할 수 있습니다.",
    "Attendance for employee {0} is already marked for an overlapping shift {1}: {2}": "직원 {0}의 출근기록이 중복 교대 {1}: {2}에 이미 처리되었습니다",
    "If checked, flexible benefits are considered only if benefit application exists": "선택 시, 복리후생 신청서가 있는 경우에만 유연 복리후생을 고려합니다",
    "If checked, overtime slip creation can be handled as part of payroll processing": "선택 시, 초과근무 명세서 생성을 급여처리의 일부로 처리할 수 있습니다",
    "Please enable default incoming account before creating Daily Work Summary Group": "일일 업무 요약 그룹을 생성하기 전에 기본 수신 계정을 활성화하세요",
    "Select your Leave Approver i.e. the person who approves or rejects your leaves.": "휴가 승인자 즉, 휴가를 승인하거나 반려하는 담당자를 선택하세요.",
    "The metrics for this report are calculated based on {0}. Please set {0} in {1}.": "이 보고서의 지표는 {0}을 기준으로 계산됩니다. {1}에서 {0}을 설정하세요.",
    "This action will prevent making changes to the linked appraisal feedback/goals.": "이 작업은 연결된 평가 피드백/목표 변경을 방지합니다.",
    "To overwrite the salary component amount for a tax component, please enable {0}": "세금 항목의 급여항목 금액을 덮어쓰려면 {0}을 활성화하세요",
    "Cannot create or change transactions against an Appraisal Cycle with status {0}.": "상태가 {0}인 평가 주기에 대한 거래를 생성하거나 변경할 수 없습니다.",
    "If enabled, the component will be considered in the Income Tax Deductions report": "활성화 시, 소득세 공제 보고서에 이 항목이 포함됩니다",
    "Korea Payroll Closing Draft status must stay within guarded human-review states.": "한국 급여 마감 초안 상태는 감시된 인사 검토 상태 내에 있어야 합니다.",
    "Mutation boundary must remain audit_log_only_no_submit_no_send_no_provider_call.": "변경 경계는 audit_log_only_no_submit_no_send_no_provider_call이어야 합니다.",
    "No active or default Salary Structure found for employee {0} for the given dates": "직원 {0}의 해당 날짜에 활성 또는 기본 급여체계가 없습니다",
    "No applicable Earning component found in last salary slip for Gratuity Rule: {0}": "퇴직금 규칙 {0}의 마지막 급여명세서에 적용 가능한 지급 항목이 없습니다",
    "Time after the end of shift during which check-out is considered for attendance.": "교대 종료 후 출근기록으로 인정되는 체크아웃 허용 시간.",
    "audit_log.contract_type must be korea_payroll_closing_draft_review_audit_log_v1.": "audit_log.contract_type은 korea_payroll_closing_draft_review_audit_log_v1이어야 합니다.",
    "Employee {0} already has an Attendance Request {1} that overlaps with this period": "직원 {0}에게 이 기간과 중복되는 출근기록 요청 {1}이 이미 있습니다",
    "If enabled, auto attendance will be marked on holidays if Employee Checkins exist": "활성화 시, 직원 체크인이 있으면 휴일에도 자동 출근기록이 처리됩니다",
    "Mark attendance based on 'Employee Checkin' for Employees assigned to this shift.": "이 교대에 배정된 직원의 출근기록을 '직원 체크인' 기준으로 처리합니다.",
    "No Bank/Cash Account found for currency {0}. Please create one under company {1}.": "통화 {0}에 대한 은행/현금 계정이 없습니다. 회사 {1}에 생성하세요.",
    "Shift Assignments created for the schedule between {0} and {1} via background job": "{0}과 {1} 사이 일정에 대한 교대 배정이 백그라운드 작업으로 생성되었습니다",
    "review_action.contract_type must be korea_payroll_closing_draft_review_action_v1.": "review_action.contract_type은 korea_payroll_closing_draft_review_action_v1이어야 합니다.",
    "source_draft.contract_type must be korea_payroll_closing_draft_runtime_insert_v1.": "source_draft.contract_type은 korea_payroll_closing_draft_runtime_insert_v1이어야 합니다.",
    "Check <a href='/app/List/Error Log?reference_doctype={0}'>{1}</a> for more details": "자세한 내용은 <a href='/app/List/Error Log?reference_doctype={0}'>{1}</a>을 확인하세요",
    "Do you want to update the Job Applicant {0} as {1} based on this interview result?": "면접 결과에 따라 입사지원자 {0}을 {1}(으)로 업데이트하시겠습니까?",
    "Employee {0} already has an active Shift {1}: {2} that overlaps within this period.": "직원 {0}에게 이 기간 내에 중복되는 활성 교대 {1}: {2}이 이미 있습니다.",
    "Income Tax Slab is mandatory since the Salary Structure {0} has a tax component {1}": "급여체계 {0}에 세금 항목 {1}이 있으므로 소득세 구간이 필수입니다",
    "Leave allocation is skipped for {0}, because number of leaves to be allocated is 0.": "{0}의 배정 휴가 일수가 0이므로 휴가 배정을 건너뜁니다.",
    "Select this if you want shift assignments to be automatically created indefinitely.": "교대 배정을 무기한 자동 생성하려면 선택하세요.",
    "The metrics for this report are calculated based on the {0}. Please set {0} in {1}.": "이 보고서의 지표는 {0}을 기준으로 계산됩니다. {1}에서 {0}을 설정하세요.",
    "source_draft.mutation_boundary must remain draft_only_no_submit_no_approve_no_send.": "source_draft.mutation_boundary는 draft_only_no_submit_no_approve_no_send이어야 합니다.",
    "Attendance has been marked for all the employees between the selected payroll dates.": "선택한 급여처리 날짜 사이의 모든 직원 출근기록이 처리되었습니다.",
    "Creation of Salary Structure Assignments has been queued. It may take a few minutes.": "급여체계 배정 생성이 대기열에 추가되었습니다. 몇 분 소요될 수 있습니다.",
    "Employee {0} has already applied for Shift {1}: {2} that overlaps within this period": "직원 {0}이 이 기간 내에 중복되는 교대 {1}: {2}을 이미 신청했습니다",
    "If enabled, Tax Exemption Declaration will be considered for income tax calculation.": "활성화 시, 세금 면제 신고서가 소득세 계산에 사용됩니다.",
    "Please fill in Employee, Posting Date, and Company before fetching overtime details.": "초과근무 상세를 가져오기 전에 직원, 전기일, 회사를 입력하세요.",
    "Row {0}: Paid amount {1} is greater than pending accrued amount {2} against loan {3}": "행 {0}: 지급 금액 {1}이 대출 {3}에 대한 미지급 발생액 {2}보다 큽니다",
    "Salary Component {0} must be of type 'Earning' to be used in Employee Benefit Ledger": "직원 복리후생 원장에 사용하려면 급여항목 {0}은 '지급' 유형이어야 합니다",
    "Warning: {0} already has an active Shift Assignment {1} for some/all of these dates.": "경고: {0}은(는) 일부/모든 날짜에 대해 이미 활성 교대 배정 {1}이 있습니다.",
    "You can not define multiple slabs if you have a slab with no lower and upper limits.": "하한 및 상한이 없는 구간이 있으면 여러 구간을 정의할 수 없습니다.",
    "Accrued amount {0} is less than paid amount {1} for Benefit {2} in payroll period {3}": "급여처리 기간 {3}의 복리후생 {2}에 대한 발생액 {0}이 지급액 {1}보다 적습니다",
    "Additional Salary: {0} already exist for Salary Component: {1} for period {2} and {3}": "추가 급여 {0}이 급여항목 {1}에 대해 기간 {2}부터 {3}까지 이미 존재합니다",
    "If greater than zero, this sets the maximum benefit amount assignable to any employee": "0보다 크면, 모든 직원에게 배정 가능한 최대 복리후생 금액을 설정합니다",
    "Please assign a Salary Structure for Employee {0} applicable from or before {1} first": "먼저 직원 {0}에게 {1} 이전부터 적용되는 급여체계를 배정하세요",
    "The time after the shift start time when check-in is considered as late (in minutes).": "체크인이 지각으로 간주되는 교대 시작 시간 이후 허용 시간 (분).",
    "There are no arrear differences between existing and new salary structure components.": "기존과 신규 급여체계 항목 간에 소급분 차이가 없습니다.",
    "The time before the shift end time when check-out is considered as early (in minutes).": "조기 퇴근으로 간주되는 교대 종료 시간 전 허용 시간 (분).",
    "When set to 'Inactive', employees with conflicting active shifts will not be excluded.": "'비활성'으로 설정하면 충돌하는 활성 교대가 있는 직원이 제외되지 않습니다.",
    " Salary slips starting on or after this date will be considered for arrear calculations": "이 날짜 이후 시작하는 급여명세서가 소급분 계산에 사용됩니다",
    "<b>Total Leaves Allocated</b> are more than the number of days in the allocation period": "<b>총 배정 휴가일수</b>가 배정 기간의 일수보다 많습니다",
    "Salary Slips already exist for employees {}, and will not be processed by this payroll.": "직원 {}의 급여명세서가 이미 존재하며 이번 급여처리에서 제외됩니다.",
    "Source audit log contract type must be korea_payroll_closing_draft_review_audit_log_v1.": "소스 감사 로그 계약 유형은 korea_payroll_closing_draft_review_audit_log_v1이어야 합니다.",
    "This will submit Salary Slips and create accrual Journal Entry. Do you want to proceed?": "급여명세서를 제출하고 발생액 분개를 생성합니다. 진행하시겠습니까?",
    "Changing KRA in this parent goal will align all the child goals to the same KRA, if any.": "상위 목표의 KRA를 변경하면 모든 하위 목표가 동일한 KRA로 정렬됩니다.",
    "Currently, there is no {0} leave period for this date to create/update leave allocation.": "현재 이 날짜에 대한 {0} 휴가 기간이 없어 휴가 배정을 생성/업데이트할 수 없습니다.",
    "If enabled, the component will not be displayed in the salary slip if the amount is zero": "활성화 시, 금액이 0이면 급여명세서에 이 항목이 표시되지 않습니다",
    "Set the properties that should be updated in the Employee master on promotion submission": "승진 제출 시 직원 마스터에서 업데이트할 속성을 설정합니다",
    "You were only present for Half Day on {}. Cannot apply for a full day compensatory leave": "{}에 반일 출근했습니다. 하루 전체의 보상 휴가를 신청할 수 없습니다",
    "Additional Salary for this salary component with {0} enabled already exists for this date": "이 날짜에 {0}이 활성화된 이 급여항목의 추가 급여가 이미 존재합니다",
    "Cannot allocate more leaves due to maximum leaves allowed limit of {0} in {1} leave type.": "{1} 휴가 유형의 최대 허용 한도 {0}으로 인해 더 이상 휴가를 배정할 수 없습니다.",
    "Total allocated leaves {0} cannot be less than already approved leaves {1} for the period": "총 배정 휴가일수 {0}은 해당 기간의 이미 승인된 휴가일수 {1}보다 적을 수 없습니다",
    "Changed the status from {0} to {1} and Status for Other Half to {2} via Attendance Request": "출근기록 요청을 통해 상태를 {0}에서 {1}(으)로, 나머지 반일 상태를 {2}(으)로 변경했습니다",
    "Failed to send the Interview Reschedule notification. Please configure your email account.": "면접 일정 변경 알림 전송에 실패했습니다. 이메일 계정을 설정하세요.",
    "Interview Type {0} is only for Designation {1}. Job Applicant has applied for the role {2}": "면접 유형 {0}은 직무 {1} 전용입니다. 입사지원자가 역할 {2}에 지원했습니다",
    "Leaves for the Leave Type {0} won't be carry-forwarded since carry-forwarding is disabled.": "{0} 휴가 유형은 이월이 비활성화되어 있어 이월되지 않습니다.",
    "The day(s) on which you are applying for leave are holidays. You need not apply for leave.": "휴가를 신청하려는 날짜가 휴일입니다. 휴가 신청이 필요하지 않습니다.",
    "audit_log.mutation_boundary must remain audit_log_only_no_submit_no_send_no_provider_call.": "audit_log.mutation_boundary는 audit_log_only_no_submit_no_send_no_provider_call이어야 합니다.",
    "Criteria based on which employee should be rated in Performance Feedback and Self Appraisal": "성과 피드백 및 자기 평가에서 직원 평가 기준",
    "Evaluation Method cannot be changed as there are existing appraisals created for this cycle": "이 주기에 생성된 평가가 있어 평가 방법을 변경할 수 없습니다",
    "Leave Adjustment for this allocation already exists: {0}. Please amend existing adjustment.": "이 배정에 대한 휴가 조정이 이미 존재합니다: {0}. 기존 조정을 수정하세요.",
    "Appraisal {0} already exists for Employee {1} for this Appraisal Cycle or overlapping period": "직원 {1}에 대한 평가 {0}이 이 평가 주기 또는 중복 기간에 이미 존재합니다",
    "Leave Application period cannot be across two non-consecutive leave allocations {0} and {1}.": "휴가신청 기간이 비연속적인 두 휴가 배정 {0}과 {1}에 걸쳐있을 수 없습니다.",
    "Please share your feedback to the training by clicking on 'Training Feedback' and then 'New'": "'교육 피드백'을 클릭하고 '신규'를 클릭하여 교육 피드백을 제공하세요",
    "Please specify {0} and {1} (if any), for the correct tax calculation in future salary slips.": "향후 급여명세서의 정확한 세금 계산을 위해 {0}과 {1}(있는 경우)을 지정하세요.",
    "Advance Account is mandatory. Please set the {0} in the Company {1} and submit this document.": "선급금 계정은 필수입니다. 회사 {1}에서 {0}을 설정하고 이 문서를 제출하세요.",
    "If not checked, the list will have to be added to each Department where it has to be applied.": "선택하지 않으면 목록을 적용할 각 부서에 추가해야 합니다.",
    "No applicable slab found for the calculation of gratuity amount as per the Gratuity Rule: {0}": "퇴직금 규칙 {0}에 따른 퇴직금 계산에 적용 가능한 구간이 없습니다",
    "review_action.mutation_boundary must be human_review_only_no_submit_no_send_no_provider_call.": "review_action.mutation_boundary는 human_review_only_no_submit_no_send_no_provider_call이어야 합니다.",
    "{0} is an Accrual Component and this will be recorded as a payout in Employee Benefits Ledger": "{0}은 발생 항목이며 직원 복리후생 원장에 지급으로 기록됩니다",
    "If enabled, the amount will be excluded from accounting entries during Journal Entry creation.": "활성화 시, 분개 생성 시 이 금액이 회계 항목에서 제외됩니다.",
    "Loan cannot be repayed from salary for Employee {0} because salary is processed in currency {1}": "직원 {0}의 급여가 통화 {1}로 처리되어 급여에서 대출을 상환할 수 없습니다",
    "No salary slip found to submit for the above selected criteria OR salary slip already submitted": "선택한 조건에 해당하는 제출할 급여명세서가 없거나 이미 제출되었습니다",
    "review_action.source_draft_contract_type must be korea_payroll_closing_draft_runtime_insert_v1.": "review_action.source_draft_contract_type은 korea_payroll_closing_draft_runtime_insert_v1이어야 합니다.",
    "There are multiple shifts assigned to the employee for the same period. Please mention the shift": "같은 기간에 직원에게 여러 교대가 배정되어 있습니다. 교대를 지정하세요",
    "There's no Employee with Salary Structure: {0}. Assign {1} to an Employee to preview Salary Slip": "급여체계 {0}을 가진 직원이 없습니다. 급여명세서 미리보기를 위해 직원에게 {1}을 배정하세요",
    "This field allows you to set the maximum number of consecutive leaves an Employee can apply for.": "직원이 신청할 수 있는 최대 연속 휴가일수를 설정합니다.",
    "Accrual Component must be set for Flexible Benefit Salary Components with accrual payout methods.": "발생 지급 방법을 사용하는 유연 복리후생 급여항목에는 발생 항목을 설정해야 합니다.",
    "The time before the shift start time during which Employee Check-in is considered for attendance.": "출근기록으로 인정되는 교대 시작 시간 전 직원 체크인 허용 시간.",
    "Additional Salary for referral bonus can only be created against Employee Referral with status {0}": "추천 보너스 추가 급여는 상태가 {0}인 직원 추천에 대해서만 생성할 수 있습니다",
    "An Arrear document already exists for employee {0} with salary structure {1} in payroll period {2}": "직원 {0}의 급여체계 {1}에 대한 소급분 문서가 급여처리 기간 {2}에 이미 존재합니다",
    "Note: Total allocated leaves {0} shouldn't be less than already approved leaves {1} for the period": "참고: 총 배정 휴가일수 {0}은 해당 기간의 승인된 휴가일수 {1}보다 적어서는 안 됩니다",
    "Note: Your salary slip is password protected, the password to unlock the PDF is of the format {0}.": "참고: 급여명세서가 비밀번호로 보호되어 있습니다. PDF 잠금 해제 비밀번호 형식은 {0}입니다.",
    "An attendance record is linked to this checkin. Please cancel the attendance before modifying time.": "이 체크인에 출근기록이 연결되어 있습니다. 시간을 수정하기 전에 출근기록을 취소하세요.",
    "Bulk attendance marking is already in progress for employee {0}. You can monitor the job status {1}": "직원 {0}의 일괄 출근기록 처리가 이미 진행 중입니다. 작업 상태 {1}에서 모니터링할 수 있습니다",
    "Cannot allocate more leaves due to maximum leave allocation limit of {0} in leave policy assignment": "휴가 정책 배정의 최대 휴가 배정 한도 {0}으로 인해 더 이상 휴가를 배정할 수 없습니다",
    "Row #{0}: Timesheet amount will overwrite the Earning component amount for the Salary Component {1}": "행 #{0}: 근무표 금액이 급여항목 {1}의 지급 항목 금액을 덮어씁니다",
    "If enabled, the total no. of applications received for this opening will be displayed on the website": "활성화 시, 이 공석에 접수된 지원서 총 수가 웹사이트에 표시됩니다",
    "The currency of {0} should be same as the company's default currency. Please select another account.": "{0}의 통화는 회사 기본 통화와 같아야 합니다. 다른 계정을 선택하세요.",
    "These leaves are holidays permitted by the company however, availing it is optional for an Employee.": "이 휴가는 회사가 허용하는 휴일이지만 직원이 선택적으로 사용할 수 있습니다.",
    "Accrual Component can only be set for Flexible Benefit Salary Components with accrual payout methods.": "발생 항목은 발생 지급 방법을 사용하는 유연 복리후생 급여항목에만 설정할 수 있습니다.",
    "Employees will miss holiday reminders from {} until {}. <br> Do you want to proceed with this change?": "직원들이 {}부터 {}까지 휴일 알림을 받지 못합니다. <br> 변경을 진행하시겠습니까?",
    "Row #{0}: Cannot set amount or formula for Salary Component {1} with Variable Based On Taxable Salary": "행 #{0}: 과세 급여 기반 변동 급여항목 {1}에 금액 또는 수식을 설정할 수 없습니다",
    "Max Exemption Amount cannot be greater than maximum exemption amount {0} of Tax Exemption Category {1}": "최대 면제 금액이 세금 면제 범주 {1}의 최대 면제 금액 {0}을 초과할 수 없습니다",
    "Please set the Appraisal Template for all the {0} or select the template in the Employees table below.": "모든 {0}에 대한 평가 템플릿을 설정하거나 아래 직원 표에서 템플릿을 선택하세요.",
    "The date on which Salary Component with Amount will contribute for Earnings/Deduction in Salary Slip. ": "금액이 있는 급여항목이 급여명세서의 지급/공제에 반영되는 날짜.",
    "Link the cycle and tag KRA to your goal to update the appraisal's goal score based on the goal progress": "주기와 KRA를 목표에 연결하여 목표 진행 상황에 따라 평가의 목표 점수를 업데이트하세요",
    "No Holiday List was found for Employee {0} or their company {1} for date {2}. Please assign through {3}": "날짜 {2}에 직원 {0} 또는 회사 {1}에 대한 휴일 목록이 없습니다. {3}을 통해 배정하세요",
    "For a day of leave taken, if you still pay (say) 50% of the daily salary, then enter 0.50 in this field.": "하루 휴가 시 일급의 50%를 지급하는 경우 이 필드에 0.50을 입력하세요.",
    "Leave Ledger Entry's To date needs to be after From date. Currently, From Date is {0} and To Date is {1}": "휴가 원장 항목의 종료일이 시작일 이후여야 합니다. 현재 시작일: {0}, 종료일: {1}",
    "Multiple Additional Salaries with overwrite property exist for Salary Component {0} between {1} and {2}.": "급여항목 {0}에 대해 {1}부터 {2}까지 덮어쓰기 속성이 있는 여러 추가 급여가 존재합니다.",
    "<b>Example:</b> SAL-{first_name}-{date_of_birth.year} <br>This will generate a password like SAL-Jane-1972": "<b>예시:</b> SAL-{first_name}-{date_of_birth.year} <br>SAL-길동-1972와 같은 비밀번호가 생성됩니다",
    "Earned Leaves are auto-allocated via scheduler based on the annual allocation set in the Leave Policy: {0}": "적립 휴가는 휴가 정책 {0}의 연간 배정을 기준으로 스케줄러에 의해 자동 배정됩니다",
    "Employee can be named by Employee ID if you assign one, or via Naming Series. Select your preference here.": "직원 ID를 배정하거나 명명 시리즈를 통해 직원에게 이름을 붙일 수 있습니다. 원하는 방법을 선택하세요.",
    "Salary components of type Provident Fund, Additional Provident Fund or Provident Fund Loan are not set up.": "퇴직연금, 추가 퇴직연금 또는 퇴직연금 대출 유형의 급여항목이 설정되지 않았습니다.",
    "Select type of leave the employee wants to apply for, like Sick Leave, Privilege Leave, Casual Leave, etc.": "직원이 신청할 휴가 유형을 선택하세요. 예: 병가, 특별휴가, 일반휴가 등.",
    "You cannot reverse more than the total LWP days {0}. You have already reversed {1} days for this employee.": "총 무급결근일수 {0}보다 더 많이 환원할 수 없습니다. 이 직원에 대해 이미 {1}일을 환원했습니다.",
    "Added tax components from the Salary Component master as the salary structure didn't have any tax component.": "급여체계에 세금 항목이 없어 급여항목 마스터에서 세금 항목을 추가했습니다.",
    "Benefit amount {0} for Salary Component {1} should not be greater than maximum benefit amount {2} set in {3}": "급여항목 {1}의 복리후생 금액 {0}이 {3}에 설정된 최대 복리후생 금액 {2}를 초과해서는 안 됩니다",
    "Job Openings for the designation {0} are already open or the hiring is complete as per the Staffing Plan {1}": "인력계획 {1}에 따르면 직무 {0}의 채용 공고가 이미 오픈되었거나 채용이 완료되었습니다",
    "Leave application is linked with leave allocations {0}. Leave application cannot be set as leave without pay": "휴가신청이 휴가 배정 {0}에 연결되어 있습니다. 무급휴가로 설정할 수 없습니다",
    "Password policy cannot contain spaces or simultaneous hyphens. The format will be restructured automatically": "비밀번호 정책에 공백이나 연속 하이픈을 사용할 수 없습니다. 형식이 자동으로 재구성됩니다",
    "Shift assignments for {0} after {1} are already created. Please change {2} date to a date later than {3} {4}": "{1} 이후 {0}의 교대 배정이 이미 생성되었습니다. {2} 날짜를 {3} {4}보다 늦은 날짜로 변경하세요",
    "Default Bank / Cash account will be automatically updated in Salary Journal Entry when this mode is selected.": "이 모드를 선택하면 급여 분개에 기본 은행/현금 계정이 자동으로 업데이트됩니다.",
    "If enabled, total no. of working days will include holidays, and this will reduce the value of Salary Per Day": "활성화 시, 총 근무일수에 휴일이 포함되어 일급이 감소합니다",
    "Automatic Leave Allocation has failed for the following Earned Leaves: {0}. Please check {1} for more details.": "다음 적립 휴가에 대한 자동 휴가 배정이 실패했습니다: {0}. 자세한 내용은 {1}을 확인하세요.",
    "LWP Days Reversed ({0}) does not match actual Payroll Corrections total ({1}) for employee {2} from {3} to {4}": "환원된 무급결근일수 ({0})가 직원 {2}의 {3}부터 {4}까지 실제 급여 수정 합계 ({1})와 일치하지 않습니다",
    "If enabled, deducts payment days for absent attendance on holidays. By default, holidays are considered as paid": "활성화 시, 휴일 결근에 대한 지급일을 공제합니다. 기본적으로 휴일은 유급으로 처리됩니다",
    "Total salary booked for this employee from the beginning of the month up to the current salary slip's end date.": "이 직원의 이달 초부터 현재 급여명세서 종료일까지의 총 급여.",
    "Bulk attendance marking is queued with a background job. It may take a while. You can monitor the job status {0}": "일괄 출근기록 처리가 백그라운드 작업으로 대기열에 추가되었습니다. 잠시 소요될 수 있습니다. 작업 상태 {0}에서 모니터링하세요",
    "Feedback already submitted for the Interview {0}. Please cancel the previous Interview Feedback {1} to continue.": "면접 {0}에 대한 피드백이 이미 제출되었습니다. 계속하려면 이전 면접 피드백 {1}을 취소하세요.",
    "No employees found for the mentioned criteria:<br>Company: {0}<br> Currency: {1}<br>Payroll Payable Account: {2}": "언급된 조건에 해당하는 직원이 없습니다:<br>회사: {0}<br> 통화: {1}<br>급여미지급 계정: {2}",
    "Overwrite Salary Structure Amount is disabled as the Salary Component: {0} not part of the Salary Structure: {1}": "급여항목 {0}이 급여체계 {1}의 일부가 아니어서 급여체계 금액 덮어쓰기가 비활성화되었습니다",
    "You can only plan for upto {0} vacancies and budget {1} for {2} as per staffing plan {3} for parent company {4}.": "상위 회사 {4}의 인력계획 {3}에 따라 {2}에 대해 최대 {0}개 공석과 예산 {1}까지 계획할 수 있습니다.",
    "No arrear components found in the salary slip. Ensure Arrear Component is checked in the Salary Component master.": "급여명세서에 소급분 항목이 없습니다. 급여항목 마스터에서 소급분 항목이 선택되어 있는지 확인하세요.",
    "Optional Leaves are holidays that Employees can choose to avail from a list of holidays published by the company.": "선택적 휴가는 회사가 공표한 휴일 목록에서 직원이 선택적으로 사용할 수 있는 휴일입니다.",
    "Select the salary components whose total will be used from the salary slip to calculate the hourly overtime rate.": "시간당 초과근무 요율 계산을 위해 급여명세서에서 합산할 급여항목을 선택하세요.",
    "Total allocated leaves are more than maximum allocation allowed for {0} leave type for employee {1} in the period": "총 배정 휴가일수가 해당 기간 직원 {1}의 {0} 휴가 유형에 허용된 최대 배정을 초과합니다",
    "Enable this to use a specific multiplier for weekends. If unchecked, the standard multiplier will be used instead.": "주말에 특정 배율을 사용하려면 활성화하세요. 선택하지 않으면 표준 배율이 사용됩니다.",
    "Maximum annual taxable income eligible for full tax relief. No tax is applied if income does not exceed this limit": "전액 세금 감면이 적용되는 최대 연간 과세 소득. 소득이 이 한도를 초과하지 않으면 세금이 적용되지 않습니다",
    "Payroll date cannot be in the past. This is to ensure that claims are made for the current or future payroll cycles.": "급여처리일은 과거일 수 없습니다. 현재 또는 미래 급여처리 주기에 대한 청구를 보장하기 위함입니다.",
    "Salary already processed for period between {0} and {1}, Leave application period cannot be between this date range.": "{0}과 {1} 사이 기간의 급여가 이미 처리되었습니다. 이 날짜 범위의 휴가신청은 할 수 없습니다.",
    "Row No {0}: Amount cannot be greater than the Outstanding Amount against Expense Claim {1}. Outstanding Amount is {2}": "행 번호 {0}: 금액이 경비청구서 {1}의 미결 금액 {2}보다 클 수 없습니다",
    "This will overwrite the tax component {0} in the salary slip and tax won't be calculated based on the Income Tax Slabs": "급여명세서의 세금 항목 {0}을 덮어쓰며 소득세 구간에 따른 세금이 계산되지 않습니다",
    "No active Salary Structure Assignment found for employee {0} with salary structure {1} on or after arrear start date {2}": "직원 {0}의 소급분 시작일 {2} 이후 급여체계 {1}에 대한 활성 급여체계 배정이 없습니다",
    "Advance Account {} currency should be same as Salary Currency of Employee {}. Please select same currency Advance Account": "선급금 계정 {}의 통화는 직원 {}의 급여 통화와 같아야 합니다. 동일 통화의 선급금 계정을 선택하세요",
    "Enable this to use a specific multiplier for public holidays. If unchecked, the standard multiplier will be used instead.": "공휴일에 특정 배율을 사용하려면 활성화하세요. 선택하지 않으면 표준 배율이 사용됩니다.",
    "Whereas allocation for Compensatory Leaves is automatically created or updated on submission of Compensatory Leave Request.": "보상 휴가는 보상 휴가 요청 제출 시 자동으로 생성되거나 업데이트됩니다.",
    "Attendance is pending for these employees between the selected payroll dates. Mark attendance to proceed. Refer {0} for details.": "선택한 급여처리 날짜 사이에 이 직원들의 출근기록이 미처리 상태입니다. 계속하려면 출근기록을 처리하세요. 자세한 내용은 {0}을 참조하세요.",
    "The salary slip emailed to the employee will be password protected, the password will be generated based on the password policy.": "직원에게 이메일로 전송되는 급여명세서는 비밀번호로 보호되며, 비밀번호 정책에 따라 생성됩니다.",
    "Job Applicants are not allowed to appear twice for the same Interview Type. Interview {0} already scheduled for Job Applicant {1}": "입사지원자는 같은 면접 유형에 두 번 참여할 수 없습니다. 면접 {0}이 입사지원자 {1}에게 이미 예정되어 있습니다",
    "Leave cannot be allocated before {0}, as leave balance has already been carry-forwarded in the future leave allocation record {1}": "{0} 이전에는 휴가를 배정할 수 없습니다. 미래 휴가 배정 레코드 {1}에 휴가 잔여일수가 이미 이월되었습니다",
    "Error while evaluating the {doctype} {doclink} at row {row_id}. <br><br> <b>Error:</b> {error} <br><br> <b>Hint:</b> {description}": "{doctype} {doclink}의 행 {row_id} 평가 중 오류가 발생했습니다. <br><br> <b>오류:</b> {error} <br><br> <b>힌트:</b> {description}",
    "Allocation was skipped due to maximum leave allocation limit set in leave type. Please increase the limit and retry failed allocation.": "휴가 유형의 최대 배정 한도로 인해 배정을 건너뛰었습니다. 한도를 늘리고 실패한 배정을 다시 시도하세요.",
    "Leave cannot be applied/cancelled before {0}, as leave balance has already been carry-forwarded in the future leave allocation record {1}": "{0} 이전에는 휴가를 신청/취소할 수 없습니다. 미래 휴가 배정 레코드 {1}에 휴가 잔여일수가 이미 이월되었습니다",
    "Reducing maximum leaves allowed after allocation may cause scheduler to allocate incorrect number of earned leaves. Proceed with caution.": "배정 후 최대 허용 휴가를 줄이면 스케줄러가 잘못된 수의 적립 휴가를 배정할 수 있습니다. 주의하여 진행하세요.",
    "Skipping Salary Structure Assignment for the following employees, as Salary Structure Assignment records already exists against them. {0}": "다음 직원들에 대한 급여체계 배정을 건너뜁니다. 이미 급여체계 배정 레코드가 존재합니다. {0}",
    "If checked, the full amount will be deducted from taxable income before calculating income tax without any declaration or proof submission.": "선택 시, 신고 또는 증빙 제출 없이 소득세 계산 전 과세 소득에서 전액이 공제됩니다.",
    "No active employee found associated with the email ID {0}. Try logging in with your employee email ID or contact your HR manager for access.": "이메일 ID {0}에 연결된 활성 직원이 없습니다. 직원 이메일 ID로 로그인하거나 HR 관리자에게 문의하세요.",
    "This field allows you to set the maximum number of leaves that can be allocated annually for this Leave Type while creating the Leave Policy": "휴가 정책 생성 시 이 휴가 유형에 연간 배정 가능한 최대 휴가일수를 설정합니다",
    "If enabled, the component will be considered as a tax component and the amount will be auto-calculated as per the configured income tax slabs": "활성화 시, 이 항목이 세금 항목으로 처리되며 설정된 소득세 구간에 따라 금액이 자동 계산됩니다",
    "Total salary booked for this employee from the beginning of the year (payroll period or fiscal year) up to the current salary slip's end date.": "이 직원의 연초(급여처리 기간 또는 회계연도)부터 현재 급여명세서 종료일까지의 총 급여.",
    "Disable {0} for the {1} component, to prevent the amount from being deducted twice, as its formula already uses a payment-days-based component.": "{1} 항목의 수식에 이미 지급일 기반 항목이 사용되어 이중 공제를 방지하려면 {0}을 비활성화하세요.",
    "Enter the number of Leave Without Pay (LWP) days you want to reverse. This value cannot exceed the total LWP days recorded for the selected month": "환원할 무급결근(LWP) 일수를 입력하세요. 이 값은 선택한 월에 기록된 총 무급결근 일수를 초과할 수 없습니다",
    "Leaves you can avail against a holiday you worked on. You can claim Compensatory Off Leave using Compensatory Leave Request. Click {0} to know more": "근무한 휴일에 대해 사용할 수 있는 휴가입니다. 보상 휴가 요청을 통해 보상 휴가를 청구할 수 있습니다. 자세히 보려면 {0}을 클릭하세요",
    "By default, the Final Score is calculated as the average of Goal Score, Feedback Score, and Self Appraisal Score. Enable this to set a different formula": "기본적으로 최종 점수는 목표 점수, 피드백 점수, 자기 평가 점수의 평균으로 계산됩니다. 다른 수식을 설정하려면 활성화하세요",
    "If you are using loans in salary slips, please install the {0} app from Frappe Cloud Marketplace or GitHub to continue using loan integration with payroll.": "급여명세서에서 대출을 사용하는 경우 급여처리와의 대출 연동을 계속 사용하려면 Frappe Cloud Marketplace 또는 GitHub에서 {0} 앱을 설치하세요.",
    "In case of any error during this background process, the system will add a comment about the error on this Payroll Entry and revert to the Submitted status": "백그라운드 처리 중 오류가 발생하면 시스템이 이 급여처리에 오류 관련 댓글을 추가하고 제출됨 상태로 되돌립니다",
    "This check-in is outside assigned shift hours and will not be considered for attendance. If a shift is assigned, adjust its time window and Fetch Shift again.": "이 체크인은 배정된 교대 시간 외로 출근기록에 고려되지 않습니다. 교대가 배정되어 있으면 시간 창을 조정하고 교대를 다시 불러오세요.",
    "Employee {0} has already claimed the benefit '{1}' for {2} ({3}).<br>To prevent overpayments, only one claim per benefit type is allowed in each payroll cycle.": "직원 {0}이 {2} ({3})에 대한 복리후생 '{1}'을 이미 청구했습니다.<br>초과 지급 방지를 위해 각 급여처리 주기에서 복리후생 유형당 하나의 청구만 허용됩니다.",
    "Total salary booked against this component for this employee from the beginning of the year (payroll period or fiscal year) up to the current salary slip's end date.": "이 직원의 연초(급여처리 기간 또는 회계연도)부터 현재 급여명세서 종료일까지 이 항목에 대해 기록된 총 급여.",
    "Last Known Successful Sync of Employee Checkin. Reset this only if you are sure that all Logs are synced from all the locations. Please don't modify this if you are unsure.": "직원 체크인의 마지막으로 알려진 성공적인 동기화입니다. 모든 위치에서 모든 로그가 동기화되었다고 확신하는 경우에만 재설정하세요. 확실하지 않으면 수정하지 마세요.",
    "Enter the Standard Working Hours for a normal work day. These hours will be used in calculations of reports such as Employee Hours Utilization and Project Profitability analysis.": "일반 근무일의 표준 근무시간을 입력하세요. 이 시간은 직원 시간 활용 및 프로젝트 수익성 분석 등의 보고서 계산에 사용됩니다.",
    "If enabled, this component allows to accrue amounts without adding them to earnings. The accrued balance is tracked in the Employee Benefit Ledger and can be paid out later as needed.": "활성화 시, 이 항목은 지급에 추가하지 않고 금액을 발생시킵니다. 발생 잔액은 직원 복리후생 원장에 추적되며 필요 시 나중에 지급할 수 있습니다.",
    "Actual balances aren't available because the leave application spans over different leave allocations. You can still apply for leaves which would be compensated during the next allocation.": "휴가신청이 여러 휴가 배정에 걸쳐 있어 실제 잔여일수를 확인할 수 없습니다. 다음 배정 시 보상될 휴가는 여전히 신청할 수 있습니다.",
    "Subsidiary companies have already planned for {1} vacancies at a budget of {2}. Staffing Plan for {0} should allocate more vacancies and budget for {3} than planned for its subsidiary companies": "자회사들이 이미 예산 {2}으로 {1}개 공석을 계획했습니다. {0}의 인력계획은 {3}에 대해 자회사들보다 더 많은 공석과 예산을 배정해야 합니다",
    "{0} leaves from allocation for {1} leave type have expired and will be processed during the next scheduled job. It is recommended to expire them now before creating new leave policy assignments.": "{1} 휴가 유형의 배정에서 {0}일의 휴가가 만료되어 다음 예약 작업에서 처리됩니다. 새 휴가 정책 배정을 생성하기 전에 지금 만료하는 것을 권장합니다.",
    "{0} vacancies and {1} budget for {2} already planned for subsidiary companies of {3}. You can only plan for upto {4} vacancies and and budget {5} as per staffing plan {6} for parent company {3}.": "{3}의 자회사들에 대해 {2}에 {0}개 공석과 예산 {1}이 이미 계획되었습니다. 상위 회사 {3}의 인력계획 {6}에 따라 최대 {4}개 공석과 예산 {5}까지만 계획할 수 있습니다.",
    "If enabled, the value specified or calculated in this component will not contribute to the earnings or deductions. However, it's value can be referenced by other components that can be added or deducted. ": "활성화 시, 이 항목에서 지정되거나 계산된 값이 지급 또는 공제에 포함되지 않습니다. 그러나 다른 항목에서 참조하여 추가하거나 공제할 수 있습니다.",
    "If selected, the value specified or calculated in this component will not contribute to the earnings or deductions. However, it's value can be referenced by other components that can be added or deducted. ": "선택 시, 이 항목에서 지정되거나 계산된 값이 지급 또는 공제에 포함되지 않습니다. 그러나 다른 항목에서 참조하여 추가하거나 공제할 수 있습니다.",
    "Indicates the number of leaves that cannot be encashed from the leave balance. E.g. with a leave balance of 10 and 4 Non-Encashable Leaves, you can encash 6, while the remaining 4 can be carried forward or expired": "현금화할 수 없는 휴가 잔여일수를 나타냅니다. 예를 들어 잔여 휴가 10일 중 비현금화 4일이면 6일을 현금화할 수 있고 나머지 4일은 이월하거나 만료됩니다",
    "Earned Leaves are leaves earned by an Employee after working with the company for a certain amount of time. Enabling this will allocate leaves on pro-rata basis by automatically updating Leave Allocation for leaves of this type at intervals set by 'Earned Leave Frequency.": "적립 휴가는 직원이 일정 기간 근무 후 적립하는 휴가입니다. 활성화 시 '적립 휴가 빈도'로 설정된 간격으로 이 유형의 휴가 배정을 자동 업데이트하여 비례 배분합니다.",
    # These have tricky partial content
    "Please set \\'": "설정하세요 \\'",
    "Set \\'": "설정 \\'",
    "A friendly reminder of an important date for our team.": "팀의 중요한 날짜를 알려드립니다.",
    "Add unused leaves from previous leave period's allocation to this allocation": "이전 휴가 기간의 미사용 휴가를 이 배정에 추가",
    "Accrual Component can only be set for Earning Salary Component": "발생 항목은 지급 급여항목에만 설정할 수 있습니다",
    " Unlink Payment on Cancellation of Employee Advance": "직원 선급금 취소 시 지급 연결 해제",
    '"From Date" can not be greater than or equal to "To Date"': '"시작일"은 "종료일"보다 같거나 클 수 없습니다',
    "A Job Requisition for {0} requested by {1} already exists: {2}": "{1}이 요청한 {0}에 대한 채용 요청이 이미 존재합니다: {2}",
    "<table class='table table-bordered'><tr><th>{0}</th><th>{1}</th></tr>": "<table class='table table-bordered'><tr><th>{0}</th><th>{1}</th></tr>",
}


def validate_placeholders(msgid, msgstr):
    """Ensure all {N} and %s placeholders from msgid are in msgstr"""
    if not msgstr:
        return True
    # Find all placeholders in msgid
    placeholders = re.findall(r'\{[^}]+\}|\%s|\%d|\%\([^)]+\)[sd]', msgid)
    for ph in placeholders:
        if ph not in msgstr:
            return False
    return True


def apply_translations(po_path, translations):
    with open(po_path, 'r', encoding='utf-8') as f:
        content = f.read()

    applied = 0
    skipped_placeholder = 0
    not_found = 0

    for msgid, msgstr in translations.items():
        # Validate placeholder preservation
        if not validate_placeholders(msgid, msgstr):
            print(f"SKIP (placeholder fail): {repr(msgid[:60])}")
            skipped_placeholder += 1
            continue

        # Escape the msgid for searching in po file
        escaped_msgid = msgid.replace('\\', '\\\\').replace('"', '\\"')

        # Build the search pattern: msgid "..." followed by msgstr ""
        # We need to find the exact entry
        old_pattern = f'msgid "{escaped_msgid}"\nmsgstr ""'
        new_str = f'msgid "{escaped_msgid}"\nmsgstr "{msgstr}"'

        if old_pattern in content:
            content = content.replace(old_pattern, new_str, 1)
            applied += 1
        else:
            # Try with the literal msgid (no extra escaping)
            old_pattern2 = f'msgid "{msgid}"\nmsgstr ""'
            new_str2 = f'msgid "{msgid}"\nmsgstr "{msgstr}"'
            if old_pattern2 in content:
                content = content.replace(old_pattern2, new_str2, 1)
                applied += 1
            else:
                not_found += 1
                if not_found <= 10:
                    print(f"NOT FOUND: {repr(msgid[:60])}")

    print(f"\nApplied: {applied}")
    print(f"Placeholder fails: {skipped_placeholder}")
    print(f"Not found: {not_found}")

    # Write back
    with open(po_path, 'w', encoding='utf-8') as f:
        f.write(content)

    return applied


def count_stats(po_path):
    with open(po_path, 'r') as f:
        content = f.read()
    total = content.count('msgstr "')
    empty = content.count('msgstr ""')
    translated = total - empty
    return total, translated, empty


if __name__ == "__main__":
    print("=" * 60)
    print("HRMS ko.po Batch 3 Translation")
    print(f"Target: {KO_PO_PATH}")
    print("=" * 60)

    # Stats before
    total, translated_before, empty_before = count_stats(KO_PO_PATH)
    print(f"\nBEFORE: {translated_before}/{total} translated ({100*translated_before/total:.1f}%)")
    print(f"Empty: {empty_before}")

    # Backup
    backup_path = KO_PO_PATH + f".backup_batch3_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(KO_PO_PATH, backup_path)
    print(f"\nBackup: {backup_path}")

    # Apply translations
    print(f"\nApplying {len(BATCH3_TRANSLATIONS)} translations...")
    applied = apply_translations(KO_PO_PATH, BATCH3_TRANSLATIONS)

    # Stats after
    total, translated_after, empty_after = count_stats(KO_PO_PATH)
    print(f"\nAFTER: {translated_after}/{total} translated ({100*translated_after/total:.1f}%)")
    print(f"Empty: {empty_after}")
    print(f"Net new translations: {translated_after - translated_before}")

    if translated_after >= 1900:
        print(f"\n✓ TARGET MET: {translated_after} >= 1900 (80%+ coverage)")
    else:
        print(f"\n⚠ Target not yet met: {translated_after} < 1900")
