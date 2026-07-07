"""seed_korea_masters.py — 한국형 HR 마스터데이터 시드 (Tier 1 프로비저닝 재료)

휴가 유형(Leave Type) 한글 5종 카테고리 중 4종 생성, 연차 배정(Leave Allocation,
근로기준법 제60조 산식), 승인자(leave/expense approver) 지정, 교대 유형(Shift Type)
주간/야간 2종을 idempotent하게 시드한다.

사용법 (컨테이너 내부, apps/hrms/hrms/ 아래에 두고):
    bench --site {site} execute hrms.seed_korea_masters.run
    bench --site {site} execute hrms.seed_korea_masters.run \
        --kwargs "{'approver': 'moon@noho.im', 'year': 2026}"

특징:
    - 이미 존재하는 레코드는 skip (idempotent). 삭제/개명 없음.
    - 기존 "Leave Without Pay" 등 표준 레코드는 건드리지 않는다.
    - 회사명/승인자/연도 파라미터화 — 10,000 사업장 프로비저닝 마법사 재료.
"""

import frappe
from frappe.utils import getdate, nowdate


# ---------------------------------------------------------------------------
# 근로기준법 제60조 연차 산식
# ---------------------------------------------------------------------------

def annual_leave_days(date_of_joining, as_of=None):
    """입사일 기반 연차 부여일수 (근로기준법 제60조).

    - 입사 1년 미만: 월 개근당 1일 (만근한 개월수, 최대 11)
    - 1년 이상: 15일, 3년차부터 계속근로 2년당 +1일, 최대 25일
    """
    doj = getdate(date_of_joining)
    ref = getdate(as_of or nowdate())
    # 만 근속연수
    years = ref.year - doj.year - ((ref.month, ref.day) < (doj.month, doj.day))
    if years < 1:
        months = (ref.year - doj.year) * 12 + (ref.month - doj.month)
        if ref.day < doj.day:
            months -= 1
        return max(0, min(months, 11))
    extra = max(0, (years - 1) // 2)  # 3년차(만2년)부터 2년당 +1
    return min(15 + extra, 25)


# ---------------------------------------------------------------------------
# 1. 휴가 유형 (Leave Type)
# ---------------------------------------------------------------------------

LEAVE_TYPES = [
    {"leave_type_name": "연차", "is_carry_forward": 1, "max_leaves_allowed": 25,
     "is_earned_leave": 0, "include_holiday": 0, "is_lwp": 0},
    {"leave_type_name": "경조휴가", "is_lwp": 0, "max_leaves_allowed": 5},
    {"leave_type_name": "병가(무급)", "is_lwp": 1},
    {"leave_type_name": "출산전후휴가", "is_lwp": 0, "max_leaves_allowed": 90,
     "is_ppl": 0},
]


def seed_leave_types():
    created, skipped = [], []
    for row in LEAVE_TYPES:
        name = row["leave_type_name"]
        if frappe.db.exists("Leave Type", name):
            skipped.append(name)
            continue
        doc = frappe.new_doc("Leave Type")
        doc.update(row)
        doc.insert(ignore_permissions=True)
        created.append(name)
    return {"created": created, "skipped": skipped}


# ---------------------------------------------------------------------------
# 2. 연차 배정 (Leave Allocation)
# ---------------------------------------------------------------------------

def seed_leave_allocations(company=None, leave_type="연차", year=None):
    year = int(year or getdate(nowdate()).year)
    from_date, to_date = f"{year}-01-01", f"{year}-12-31"
    filters = {"status": "Active"}
    if company:
        filters["company"] = company
    employees = frappe.get_all(
        "Employee", filters=filters,
        fields=["name", "employee_name", "date_of_joining", "company"],
        order_by="name")
    allocated, skipped = [], []
    for emp in employees:
        if frappe.db.exists("Leave Allocation", {
                "employee": emp.name, "leave_type": leave_type,
                "docstatus": 1, "from_date": ("<=", to_date),
                "to_date": (">=", from_date)}):
            skipped.append(emp.name)
            continue
        days = annual_leave_days(emp.date_of_joining)
        if days <= 0:
            skipped.append(emp.name + " (0일)")
            continue
        alloc = frappe.new_doc("Leave Allocation")
        alloc.update({
            "employee": emp.name, "leave_type": leave_type,
            "from_date": from_date, "to_date": to_date,
            "new_leaves_allocated": days, "company": emp.company})
        alloc.insert(ignore_permissions=True)
        alloc.submit()
        allocated.append((emp.name, emp.employee_name,
                          str(emp.date_of_joining), days))
    return {"allocated": allocated, "skipped": skipped}


# ---------------------------------------------------------------------------
# 3. 승인자 지정
# ---------------------------------------------------------------------------

def seed_approvers(approver, company=None):
    # 승인자 유저에 역할 부여 (역할이 존재할 때만)
    roles_added = []
    if frappe.db.exists("User", approver):
        user = frappe.get_doc("User", approver)
        have = {r.role for r in user.roles}
        for role in ("Leave Approver", "Expense Approver"):
            if frappe.db.exists("Role", role) and role not in have:
                user.append("roles", {"role": role})
                roles_added.append(role)
        if roles_added:
            user.save(ignore_permissions=True)
    # Employee 필드 존재 확인 후 세팅
    meta = frappe.get_meta("Employee")
    fields = [f for f in ("leave_approver", "expense_approver")
              if meta.has_field(f)]
    filters = {"status": "Active"}
    if company:
        filters["company"] = company
    count = 0
    for emp in frappe.get_all("Employee", filters=filters, pluck="name"):
        updates = {f: approver for f in fields
                   if frappe.db.get_value("Employee", emp, f) != approver}
        if updates:
            frappe.db.set_value("Employee", emp, updates)
        count += 1
    return {"fields": fields, "employees": count, "roles_added": roles_added}


# ---------------------------------------------------------------------------
# 4. 교대 유형 (Shift Type)
# ---------------------------------------------------------------------------

SHIFT_TYPES = [
    {"name": "주간 (09:00-18:00)", "start_time": "09:00:00", "end_time": "18:00:00"},
    {"name": "야간 (22:00-07:00)", "start_time": "22:00:00", "end_time": "07:00:00"},
]


def seed_shift_types():
    created, skipped = [], []
    for row in SHIFT_TYPES:
        if frappe.db.exists("Shift Type", row["name"]):
            skipped.append(row["name"])
            continue
        doc = frappe.new_doc("Shift Type")
        doc.__newname = row["name"]
        doc.start_time = row["start_time"]
        doc.end_time = row["end_time"]
        doc.insert(ignore_permissions=True)
        created.append(row["name"])
    return {"created": created, "skipped": skipped}


# ---------------------------------------------------------------------------
# 엔트리포인트
# ---------------------------------------------------------------------------

def run(company=None, approver="moon@noho.im", year=None, leave_type="연차"):
    out = {}
    out["leave_types"] = seed_leave_types()
    out["allocations"] = seed_leave_allocations(company=company,
                                                leave_type=leave_type, year=year)
    out["approvers"] = seed_approvers(approver, company=company)
    out["shift_types"] = seed_shift_types()
    frappe.db.commit()
    print("=== seed_korea_masters 결과 ===")
    print("Leave Type  created:", out["leave_types"]["created"],
          "/ skipped:", out["leave_types"]["skipped"])
    print("Allocation  new:", len(out["allocations"]["allocated"]),
          "/ skipped:", len(out["allocations"]["skipped"]))
    for emp, name, doj, days in out["allocations"]["allocated"]:
        print(f"  {emp}  {name}  입사 {doj}  → {days}일")
    if out["allocations"]["skipped"]:
        print("  skipped:", out["allocations"]["skipped"])
    print("Approver    fields:", out["approvers"]["fields"],
          "/ employees:", out["approvers"]["employees"],
          "/ roles_added:", out["approvers"]["roles_added"])
    print("Shift Type  created:", out["shift_types"]["created"],
          "/ skipped:", out["shift_types"]["skipped"])
    return out
