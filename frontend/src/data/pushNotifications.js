/**
 * 노란봉투법 HRMS — Push Notification 기반 모듈 (스케치)
 *
 * v1: 권한 요청 + 브라우저 로컬 알림 헬퍼
 * v2(예정): 서버 VAPID 키 연동 → Web Push 실제 발송
 *
 * ⚠️ 실제 푸시 파이프라인은 public/frappe-push-notification.js (Firebase FCM) 기반.
 *    이 파일은 권한 요청 헬퍼 + 로컬 알림 유틸이며, FCM 파이프라인을 대체하지 않음.
 */

// ── 지원 여부 체크 ────────────────────────────────────────────────────────────

/** 브라우저가 Push + Service Worker를 지원하는지 확인 */
export function isPushSupported() {
	return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window
}

/** 현재 알림 권한 상태 반환 */
export function getPermissionState() {
	if (!("Notification" in window)) return "unsupported"
	return Notification.permission // "granted" | "denied" | "default"
}

// ── 권한 요청 ─────────────────────────────────────────────────────────────────

/**
 * 알림 권한 요청
 * @returns {Promise<"granted"|"denied"|"default">}
 */
export async function requestNotificationPermission() {
	if (!isPushSupported()) {
		console.warn("[NBP Push] Push 알림이 지원되지 않는 브라우저입니다.")
		return "unsupported"
	}

	const permission = await Notification.requestPermission()
	return permission
}

// ── 로컬 브라우저 알림 (Service Worker 없이) ──────────────────────────────────

/**
 * 로컬 알림 표시 (개발/테스트용)
 * @param {string} title
 * @param {NotificationOptions} options
 */
export function showLocalNotification(title, options = {}) {
	if (Notification.permission !== "granted") {
		console.warn("[NBP Push] 알림 권한이 없습니다.")
		return
	}
	const defaultOptions = {
		icon: "/assets/hrms/manifest/manifest-icon-192.maskable.png",
		badge: "/assets/hrms/manifest/manifest-icon-192.maskable.png",
		lang: "ko-KR",
		...options,
	}
	return new Notification(title, defaultOptions)
}

// ── Service Worker 기반 알림 ──────────────────────────────────────────────────

/**
 * SW를 통해 알림 표시 (백그라운드 포함)
 * @param {string} title
 * @param {NotificationOptions} options
 */
export async function showSwNotification(title, options = {}) {
	if (Notification.permission !== "granted") {
		console.warn("[NBP Push] 알림 권한이 없습니다.")
		return
	}
	const reg = await navigator.serviceWorker.ready
	return reg.showNotification(title, {
		icon: "/assets/hrms/manifest/manifest-icon-192.maskable.png",
		badge: "/assets/hrms/manifest/manifest-icon-192.maskable.png",
		lang: "ko-KR",
		...options,
	})
}

// ── HRMS 전용 알림 타입 ───────────────────────────────────────────────────────

/**
 * 결재 요청 알림
 * @param {{ title: string, requester: string, url: string }} params
 */
export function notifyApprovalRequest({ title, requester, url }) {
	return showSwNotification(`결재 요청: ${title}`, {
		body: `${requester}님이 결재를 요청했습니다.`,
		tag: "approval-request",
		data: { url },
		actions: [
			{ action: "approve", title: "승인" },
			{ action: "view", title: "상세보기" },
		],
	})
}

/**
 * 출퇴근 알림
 * @param {"checkin"|"checkout"} type
 * @param {string} time
 */
export function notifyAttendance(type, time) {
	const label = type === "checkin" ? "출근" : "퇴근"
	return showSwNotification(`${label} 처리 완료`, {
		body: `${time} ${label}이 기록되었습니다.`,
		tag: `attendance-${type}`,
	})
}

/**
 * 급여명세서 발행 알림
 * @param {string} period — "2026년 4월분"
 */
export function notifyPayslipPublished(period) {
	return showSwNotification("급여명세서 발행", {
		body: `${period} 급여명세서가 발행되었습니다.`,
		tag: "payslip-published",
		data: { url: "/hrms/dashboard/salary-slips" },
	})
}

// ── v2 서버 구독 stub ─────────────────────────────────────────────────────────
// TODO(v2): VAPID 공개키 기반 구독 → /api/method/hrms.push.subscribe 전송

/**
 * 서버에 푸시 구독 정보 전송 (v2 구현 예정)
 * @returns {Promise<void>}
 */
export async function subscribeToServerPush() {
	// eslint-disable-next-line no-console
	console.info(
		"[NBP Push] subscribeToServerPush() — v2에서 VAPID 구독 구현 예정. " +
		"현재는 Firebase FCM(frappe-push-notification.js)을 통해 처리됩니다."
	)
}
