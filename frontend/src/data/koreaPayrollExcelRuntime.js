/**
 * 급여 엑셀 업/다운로드 런타임 데이터 — F5.
 * backend: hrms.regional.south_korea.payroll_excel_api
 *
 * 설계 원칙:
 * - framework-free (frappe-ui import 없음) — node --test에서 직접 import 가능.
 *   createResource 3종은 화면(KoreaPayrollExcel.vue)에서 이 URL 상수로 생성한다.
 * - 개인 급여액은 화면 표시용으로만 사용하고 로그로 남기지 않는다(콘솔 출력 금지).
 */

export const DOWNLOAD_URL =
	"hrms.regional.south_korea.payroll_excel_api.download_payroll_workbook"

export const VALIDATE_URL =
	"hrms.regional.south_korea.payroll_excel_api.validate_payroll_upload"

export const APPLY_URL =
	"hrms.regional.south_korea.payroll_excel_api.apply_payroll_upload"

/** 원화 표시 — 정수 콤마 + '원'. 숫자 아님/빈값 → '-'. */
export function formatWon(value) {
	if (value === null || value === undefined || value === "") return "-"
	const n = Number(value)
	if (!Number.isFinite(n)) return "-"
	return `${Math.round(n).toLocaleString("ko-KR")}원`
}

/** 증감 표시 — 부호(+/−) 포함 원화. 0 → '±0원'. 숫자 아님/빈값 → '-'. */
export function formatSignedWon(value) {
	if (value === null || value === undefined || value === "") return "-"
	const n = Number(value)
	if (!Number.isFinite(n)) return "-"
	const rounded = Math.round(n)
	if (rounded === 0) return "±0원"
	const sign = rounded > 0 ? "+" : "−"
	return `${sign}${Math.abs(rounded).toLocaleString("ko-KR")}원`
}

/** 'YYYY-MM' 형식 여부 (월 01-12). */
export function isValidPeriod(period) {
	if (!/^\d{4}-\d{2}$/.test(String(period ?? ""))) return false
	const month = Number(String(period).slice(5, 7))
	return month >= 1 && month <= 12
}

/** 기준 날짜의 직전 월을 'YYYY-MM' 으로 — 급여는 통상 지난달 마감. */
export function defaultPeriod(now = new Date()) {
	const year = now.getFullYear()
	const month = now.getMonth() // 0-based → 직전 월
	const d = new Date(year, month - 1, 1)
	const mm = String(d.getMonth() + 1).padStart(2, "0")
	return `${d.getFullYear()}-${mm}`
}

/**
 * 검증 응답을 화면 표시 모델로 정규화.
 * @param {object|null} data validate_payroll_upload 응답
 * @returns {{
 *   status: string, ok: boolean, hasError: boolean,
 *   period: string, company: string, count: number,
 *   counts: {new:number, changed:number, same:number, missing:number},
 *   changedRows: Array<{name:string, netDelta:number, grossDelta:number, fromNet:number, toNet:number}>,
 *   newRows: Array<{name:string}>, missingRows: Array<{name:string}>,
 *   errors: string[]
 * }}
 */
export function buildValidationView(data) {
	const empty = {
		status: "none",
		ok: false,
		hasError: false,
		period: "",
		company: "",
		count: 0,
		counts: { new: 0, changed: 0, same: 0, missing: 0 },
		changedRows: [],
		newRows: [],
		missingRows: [],
		errors: [],
	}
	if (!data || typeof data !== "object") return empty

	const status = data.status ?? "none"
	if (status !== "ok") {
		return {
			...empty,
			status,
			hasError: true,
			period: data.period ?? "",
			count: Number(data.count) || 0,
			errors: Array.isArray(data.errors) ? data.errors.map(String) : [],
		}
	}

	const diff = data.diff ?? {}
	const counts = diff.counts ?? { new: 0, changed: 0, same: 0, missing: 0 }
	return {
		status,
		ok: true,
		hasError: false,
		period: data.period ?? "",
		company: data.company ?? "",
		count: Number(data.count) || 0,
		counts: {
			new: Number(counts.new) || 0,
			changed: Number(counts.changed) || 0,
			same: Number(counts.same) || 0,
			missing: Number(counts.missing) || 0,
		},
		changedRows: (diff.changed ?? []).map((r) => ({
			name: r.name,
			netDelta: Number(r.net_delta) || 0,
			grossDelta: Number(r.gross_delta) || 0,
			fromNet: Number(r.from_net) || 0,
			toNet: Number(r.to_net) || 0,
		})),
		newRows: (diff.new ?? []).map((r) => ({ name: r.name })),
		missingRows: (diff.missing ?? []).map((r) => ({ name: r.name })),
		errors: [],
	}
}

/** 검증 결과가 실제 반영할 변경(신규·변경·누락)을 포함하는지. */
export function hasPayrollChanges(view) {
	const c = view?.counts
	if (!c) return false
	return (c.new || 0) + (c.changed || 0) + (c.missing || 0) > 0
}

/**
 * 반영(apply) 응답을 화면 표시 모델로 정규화.
 * @returns {{status:string, blocked:boolean, applied:boolean,
 *   created:number, updated:number, skipped:number, count:number,
 *   totalGross:number, errors:string[]}}
 */
export function buildApplyView(data) {
	const base = {
		status: data?.status ?? "none",
		blocked: false,
		applied: false,
		created: 0,
		updated: 0,
		skipped: 0,
		count: 0,
		totalGross: 0,
		errors: [],
	}
	if (!data || typeof data !== "object") return base
	if (data.status === "blocked") {
		return { ...base, blocked: true }
	}
	if (data.status === "applied") {
		return {
			...base,
			applied: true,
			created: Number(data.created) || 0,
			updated: Number(data.updated) || 0,
			skipped: Number(data.skipped) || 0,
			count: Number(data.count) || 0,
			totalGross: Number(data.total_gross) || 0,
		}
	}
	return {
		...base,
		errors: Array.isArray(data.errors) ? data.errors.map(String) : [],
	}
}
