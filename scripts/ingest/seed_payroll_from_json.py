# 급여 JSON → 테넌트 사이트 시드 (기존 데이터 임베딩 2/2). bench console에서 실행.
#
# 사용 (서버):
#   docker cp payroll.json docker-frappe-1:/tmp/payroll.json
#   echo "PAYROLL_JSON='/tmp/payroll.json'; exec(open('/tmp/seed_payroll_from_json.py').read())" \
#     | docker exec -i -w /home/frappe/frappe-bench docker-frappe-1 bench --site <site> console
#
# 동작: 구성항목→직원(upsert)→기간별 급여구조→배정→명세서(draft) 생성 후
#       gross/net을 원본 엑셀 기대값과 1원 단위 비교. 불일치는 전부 출력한다.
# 노호 5월분(32명)으로 실검증: 32/32 일치, 총 실지급 95,940,486원 일치.
import calendar
import json

import frappe

PATH = globals().get("PAYROLL_JSON", "/tmp/payroll.json")
payload = json.load(open(PATH, encoding="utf-8"))
DATA = payload["employees"]
year, month = map(int, payload["period"].split("-"))
START = f"{year:04d}-{month:02d}-01"
END = f"{year:04d}-{month:02d}-{calendar.monthrange(year, month)[1]:02d}"
COMPANY = globals().get("PAYROLL_COMPANY") or frappe.get_all("Company", limit_page_length=1)[0]["name"]

earn_names = sorted({k for e in DATA for k in e["earnings"]})
ded_names = sorted({k for e in DATA for k in e["deductions"]})
for comp, ctype in [(c, "Earning") for c in earn_names] + [(c, "Deduction") for c in ded_names]:
    if not frappe.db.exists("Salary Component", comp):
        doc = frappe.get_doc({"doctype": "Salary Component", "salary_component": comp, "type": ctype, "company": COMPANY})
        if "비과세" in comp:
            doc.is_tax_applicable = 0
        doc.insert(ignore_permissions=True)
frappe.db.commit()

report = []
for e in DATA:
    emp_name = e["name"]
    emp_id = frappe.db.get_value("Employee", {"employee_name": emp_name, "company": COMPANY}, "name")
    if not emp_id:
        emp = frappe.get_doc({
            "doctype": "Employee", "first_name": emp_name, "company": COMPANY,
            "date_of_joining": min(e.get("join") or START, START),
            "date_of_birth": "1990-01-01", "gender": "Male", "status": "Active",
            "personal_email": e.get("email") or None,
        })
        emp.insert(ignore_permissions=True)
        emp_id = emp.name

    ss_name = f"{payload['period']} {emp_name}"
    if not frappe.db.exists("Salary Structure", ss_name):
        ss = frappe.get_doc({
            "doctype": "Salary Structure", "__newname": ss_name, "company": COMPANY,
            "payroll_frequency": "Monthly",
            "earnings": [{"salary_component": c, "amount": a} for c, a in e["earnings"].items()],
            "deductions": [{"salary_component": c, "amount": a} for c, a in e["deductions"].items()],
        })
        ss.insert(ignore_permissions=True)
        ss.submit()
    if not frappe.db.exists("Salary Structure Assignment", {"employee": emp_id, "salary_structure": ss_name}):
        ssa = frappe.get_doc({
            "doctype": "Salary Structure Assignment", "employee": emp_id, "salary_structure": ss_name,
            "from_date": START, "company": COMPANY, "base": e["earnings"].get("기본급", 0),
        })
        ssa.insert(ignore_permissions=True)
        ssa.submit()

    if frappe.db.exists("Salary Slip", {"employee": emp_id, "start_date": START, "docstatus": ("<", 2)}):
        slip = frappe.get_doc("Salary Slip", frappe.db.get_value("Salary Slip", {"employee": emp_id, "start_date": START}, "name"))
    else:
        slip = frappe.get_doc({"doctype": "Salary Slip", "employee": emp_id, "start_date": START, "end_date": END, "company": COMPANY})
        slip.insert(ignore_permissions=True)
    gross, net = int(round(slip.gross_pay or 0)), int(round(slip.net_pay or 0))
    ok = gross == e["expected_gross"] and net == e["expected_net"]
    report.append((emp_name, gross, e["expected_gross"], net, e["expected_net"], "OK" if ok else "MISMATCH"))

frappe.db.commit()
ok_count = sum(1 for r in report if r[5] == "OK")
print(f"RESULT {ok_count}/{len(report)} match | period {payload['period']} | company {COMPANY}")
for r in report:
    if r[5] != "OK":
        print("MISMATCH", r)
print("system net total:", sum(r[3] for r in report), "/ excel net total:", sum(e["expected_net"] for e in DATA))
