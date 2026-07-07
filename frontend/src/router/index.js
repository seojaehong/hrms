import { createRouter, createWebHistory } from "@ionic/vue-router"

import TabbedView from "@/views/TabbedView.vue"
import attendanceRoutes from "./attendance"
import leaveRoutes from "./leaves"
import claimRoutes from "./claims"
import employeeAdvanceRoutes from "./advances"
import salarySlipRoutes from "./salary_slips"
import koreaApprovalInboxRoutes from "./koreaApprovalInbox"
import koreaRoutes from "./korea"
import koreaSubscriptionRoutes from "./korea_subscription"

const routes = [
	{
		path: "/",
		redirect: "/home",
	},
	{
		path: "/",
		component: TabbedView,
		children: [
			{
				path: "",
				redirect: "/home",
			},
			{
				path: "/home",
				name: "Home",
				component: () => import("@/views/Home.vue"),
			},
			{
				path: "/dashboard/attendance",
				name: "AttendanceDashboard",
				component: () => import("@/views/attendance/Dashboard.vue"),
			},
			{
				path: "/dashboard/leaves",
				name: "LeavesDashboard",
				component: () => import("@/views/leave/Dashboard.vue"),
			},
			{
				path: "/dashboard/expense-claims",
				name: "ExpenseClaimsDashboard",
				component: () => import("@/views/expense_claim/Dashboard.vue"),
			},
			{
				path: "/dashboard/salary-slips",
				name: "SalarySlipsDashboard",
				component: () => import("@/views/salary_slip/Dashboard.vue"),
			},
			{
				path: "/dashboard/korea-payroll-closing",
				name: "KoreaPayrollClosingDashboard",
				component: () => import("@/views/KoreaPayrollClosing.vue"),
			},
			{
				path: "/korea-payroll-closing-session/:name",
				name: "KoreaPayrollClosingSessionPreview",
				component: () => import("@/views/KoreaPayrollClosing.vue"),
			},
			{
				path: "/dashboard/korea-payroll-review-audit-logs",
				name: "KoreaPayrollReviewAuditLogs",
				component: () => import("@/views/KoreaPayrollReviewAuditLogs.vue"),
			},
			{
				path: "/korea-payroll-review-audit-logs/:name",
				name: "KoreaPayrollReviewAuditLogDetail",
				component: () => import("@/views/KoreaPayrollReviewAuditLogDetail.vue"),
			},
			{
				path: "/dashboard/korea-annual-leave",
				name: "KoreaAnnualLeaveDashboard",
				component: () => import("@/views/KoreaAnnualLeaveDashboard.vue"),
			},
			{
				path: "/korea-annual-leave/:employeeId",
				name: "KoreaAnnualLeaveDetail",
				component: () => import("@/views/KoreaAnnualLeaveDetail.vue"),
			},
			{
				// 하단탭 canonical 급여 화면 — 탭 레이아웃 유지를 위해 TabbedView 하위에 배치 (경로 동일)
				path: "/dashboard/korea-wage-statement",
				name: "KoreaWageStatementDashboard",
				component: () => import("@/views/korea/KoreaWageStatementDashboard.vue"),
			},
			{
				path: "/dashboard/korea-attendance",
				name: "KoreaAttendanceDashboard",
				component: () => import("@/views/KoreaAttendanceDashboard.vue"),
			},
			{
				path: "/dashboard/korea-mobile-checkin",
				name: "KoreaMobileCheckin",
				component: () => import("@/views/KoreaMobileCheckin.vue"),
			},
			{
				path: "/dashboard/korea-ai-chat",
				name: "KoreaAIChat",
				component: () => import("@/views/KoreaAIChat.vue"),
			},
			// Korea 대시보드류 — 하단탭 레이아웃 유지를 위해 TabbedView 하위 (경로 동일)
			...koreaApprovalInboxRoutes,
			...koreaRoutes,
		],
	},
	{
		path: "/search",
		name: "KoreaGlobalSearch",
		component: () => import("@/views/KoreaGlobalSearch.vue"),
	},
	{
		path: "/offline",
		name: "Offline",
		component: () => import("@/views/Offline.vue"),
	},
	{
		path: "/login",
		name: "Login",
		component: () => import("@/views/Login.vue"),
	},
	{
		path: "/profile",
		name: "Profile",
		component: () => import("@/views/Profile.vue"),
	},
	{
		path: "/notifications",
		name: "Notifications",
		component: () => import("@/views/Notifications.vue"),
	},
	{
		path: "/settings",
		name: "Settings",
		component: () => import("@/views/AppSettings.vue"),
	},
	{
		path: "/invalid-employee",
		name: "InvalidEmployee",
		component: () => import("@/views/InvalidEmployee.vue"),
	},
	...attendanceRoutes,
	...leaveRoutes,
	...claimRoutes,
	...employeeAdvanceRoutes,
	...salarySlipRoutes,
	...koreaSubscriptionRoutes,
]

const router = createRouter({
	history: createWebHistory("/hrms"),
	routes,
})

export default router
