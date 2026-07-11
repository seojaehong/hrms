// KoreaWageStatementDashboard 라우트는 하단탭 canonical 통일을 위해 router/index.js의 TabbedView 하위로 이동 (경로 동일)
const routes = [
	{
		name: "KoreaSeverancePreview",
		path: "/dashboard/korea-severance-preview",
		component: () => import("@/views/korea/KoreaSeverancePreview.vue"),
	},
	{
		name: "KoreaComplianceDashboard",
		path: "/dashboard/korea-compliance",
		component: () => import("@/views/korea/KoreaComplianceDashboard.vue"),
	},
	{
		name: "KoreaTimeInput",
		path: "/dashboard/korea-time-input",
		component: () => import("@/views/korea/KoreaTimeInput.vue"),
	},
	{
		name: "KoreaComplianceCategoryDetail",
		path: "/dashboard/korea-compliance/category/:categoryKey",
		component: () => import("@/views/korea/KoreaComplianceCategoryDetail.vue"),
	},
	{
		name: "KoreaOnboardingRequest",
		path: "/dashboard/korea-onboarding-request",
		component: () => import("@/views/korea/KoreaOnboardingRequest.vue"),
	},
	{
		name: "KoreaPayrollExcel",
		path: "/dashboard/korea-payroll-excel",
		component: () => import("@/views/korea/KoreaPayrollExcel.vue"),
	},
	{
		name: "KoreaSeveranceSettlement",
		path: "/dashboard/korea-severance-settlement",
		component: () => import("@/views/korea/KoreaSeveranceSettlement.vue"),
	},
	{
		name: "KoreaInclusiveWage",
		path: "/dashboard/korea-inclusive-wage",
		component: () => import("@/views/korea/KoreaInclusiveWage.vue"),
	},
	{
		name: "KoreaLeavePromotion",
		path: "/dashboard/korea-leave-promotion",
		component: () => import("@/views/korea/KoreaLeavePromotion.vue"),
	},
	{
		name: "KoreaPayslipBreakdown",
		path: "/dashboard/korea-payslip-breakdown",
		component: () => import("@/views/korea/KoreaPayslipBreakdown.vue"),
	},
	{
		name: "KoreaServiceRequests",
		path: "/dashboard/korea-service-requests",
		component: () => import("@/views/korea/KoreaServiceRequests.vue"),
	},
	{
		name: "KoreaEmploymentContractDoc",
		path: "/dashboard/korea-employment-contract-doc",
		component: () => import("@/views/korea/KoreaEmploymentContractDoc.vue"),
	},
]

export default routes
