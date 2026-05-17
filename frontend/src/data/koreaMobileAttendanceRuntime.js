/**
 * Korea Mobile Attendance Runtime
 *
 * Provides:
 *   recordMobileCheckin(params)  — call backend, return contract envelope
 *   getCurrentGps()              — Promise<GeolocationPosition>
 *   captureSelfiePicker()        — Promise<File>  (native <input capture> picker)
 *   toBase64(file)               — Promise<string>  (strips data-URL prefix)
 *
 * Design notes:
 *  - captureSelfiePicker() uses a hidden <input type="file" accept="image/*" capture="user">
 *    element.  This is the most reliable cross-platform approach on iOS/Android.
 *  - recordMobileCheckin() accepts an optional selfieFile (browser File object).
 *    If provided it calls hrms.api.upload_base64_file first, then passes the
 *    returned File docname to the backend record_mobile_checkin endpoint.
 *  - All GPS/distance warnings surface as result.warnings[].
 */

import { createResource } from "frappe-ui"

// ---------------------------------------------------------------------------
// GPS helper
// ---------------------------------------------------------------------------

/**
 * Request the current GPS position.
 *
 * @param {PositionOptions} [options]
 * @returns {Promise<GeolocationPosition>}
 */
export function getCurrentGps(options = {}) {
	const defaults = {
		enableHighAccuracy: true,
		timeout: 15_000,
		maximumAge: 0,
	}
	return new Promise((resolve, reject) => {
		if (!navigator?.geolocation) {
			reject(new Error("Geolocation is not supported by this browser"))
			return
		}
		navigator.geolocation.getCurrentPosition(resolve, reject, { ...defaults, ...options })
	})
}

// ---------------------------------------------------------------------------
// Camera / selfie picker helper
// ---------------------------------------------------------------------------

/**
 * Open the device camera / photo library picker using a hidden file input.
 * Returns a Promise that resolves with the chosen browser File object,
 * or rejects if the user cancels (no file chosen).
 *
 * @returns {Promise<File>}
 */
export function captureSelfiePicker() {
	return new Promise((resolve, reject) => {
		const input = document.createElement("input")
		input.type = "file"
		input.accept = "image/*"
		input.capture = "user" // front-facing camera by default
		input.style.display = "none"
		document.body.appendChild(input)

		const cleanup = () => {
			document.body.removeChild(input)
		}

		input.addEventListener("change", () => {
			const file = input.files?.[0]
			cleanup()
			if (file) {
				resolve(file)
			} else {
				reject(new Error("No file selected"))
			}
		})

		// If the user dismisses the picker without choosing a file, 'change'
		// never fires.  We use a focus-back event to detect cancellation.
		const onFocus = () => {
			window.removeEventListener("focus", onFocus)
			// Give the 'change' event a tick to fire first.
			setTimeout(() => {
				if (!input.files?.length) {
					cleanup()
					reject(new Error("Camera/picker dismissed without selection"))
				}
			}, 500)
		}
		window.addEventListener("focus", onFocus)

		input.click()
	})
}

// ---------------------------------------------------------------------------
// Base64 conversion
// ---------------------------------------------------------------------------

/**
 * Convert a browser File to a raw base64 string (no data-URL prefix).
 *
 * @param {File} file
 * @returns {Promise<string>}
 */
export function toBase64(file) {
	return new Promise((resolve, reject) => {
		const reader = new FileReader()
		reader.onload = () => {
			const result = reader.result
			// Strip the "data:<mime>;base64," prefix.
			const base64 = result.split(",")[1]
			resolve(base64)
		}
		reader.onerror = () => reject(new Error("FileReader error: " + reader.error?.message))
		reader.readAsDataURL(file)
	})
}

// ---------------------------------------------------------------------------
// Upload selfie via existing hrms endpoint
// ---------------------------------------------------------------------------

/**
 * Upload a selfie File to Frappe and return the File docname.
 *
 * @param {File} selfieFile
 * @returns {Promise<string>} File docname
 */
async function _uploadSelfie(selfieFile) {
	const base64Content = await toBase64(selfieFile)

	return new Promise((resolve, reject) => {
		const resource = createResource({
			url: "hrms.api.upload_base64_file",
			params: {
				content: base64Content,
				filename: selfieFile.name || `selfie_${Date.now()}.jpg`,
			},
			onSuccess(data) {
				// Frappe File insert() returns the doc; name is the docname.
				resolve(data?.name || data)
			},
			onError(err) {
				reject(new Error("Selfie upload failed: " + (err?.message || JSON.stringify(err))))
			},
		})
		resource.submit()
	})
}

// ---------------------------------------------------------------------------
// Main API call
// ---------------------------------------------------------------------------

/**
 * Record a Korea mobile check-in / check-out.
 *
 * @param {Object} params
 * @param {string}  params.employee           — Frappe Employee docname
 * @param {"IN"|"OUT"} params.checkType       — "IN" or "OUT"
 * @param {string}  params.timestamp          — "YYYY-MM-DD HH:mm:ss" (local)
 * @param {number}  params.gpsLatitude
 * @param {number}  params.gpsLongitude
 * @param {number}  params.accuracyMeters
 * @param {File}    [params.selfieFile]       — optional browser File from captureSelfiePicker()
 *
 * @returns {Promise<{
 *   contract_type: string,
 *   status: string,
 *   warnings: string[],
 *   data: {
 *     checkin_name: string,
 *     employee: string,
 *     check_type: string,
 *     time: string,
 *     gps_latitude: number,
 *     gps_longitude: number,
 *     accuracy_meters: number,
 *     selfie_file_doc_name: string|null,
 *   }
 * }>}
 */
export async function recordMobileCheckin({
	employee,
	checkType,
	timestamp,
	gpsLatitude,
	gpsLongitude,
	accuracyMeters,
	selfieFile = null,
}) {
	// Validate required fields client-side before network calls.
	if (!employee) throw new Error("employee is required")
	if (!checkType || !["IN", "OUT"].includes(checkType.toUpperCase())) {
		throw new Error("checkType must be IN or OUT")
	}
	if (!timestamp) throw new Error("timestamp is required")
	if (gpsLatitude === undefined || gpsLatitude === null) throw new Error("gpsLatitude is required")
	if (gpsLongitude === undefined || gpsLongitude === null) throw new Error("gpsLongitude is required")
	if (accuracyMeters === undefined || accuracyMeters === null) throw new Error("accuracyMeters is required")

	// Upload selfie first (if provided) to get File docname.
	let selfieFileDocName = null
	if (selfieFile instanceof File) {
		selfieFileDocName = await _uploadSelfie(selfieFile)
	}

	// Call backend endpoint.
	return new Promise((resolve, reject) => {
		const params = {
			employee,
			check_type: checkType.toUpperCase(),
			timestamp,
			gps_latitude: gpsLatitude,
			gps_longitude: gpsLongitude,
			accuracy_meters: accuracyMeters,
			human_approved: true,
		}
		if (selfieFileDocName) {
			params.selfie_file_doc_name = selfieFileDocName
		}

		const resource = createResource({
			url: "hrms.regional.south_korea.mobile_attendance.record_mobile_checkin",
			params,
			onSuccess(data) {
				resolve(data)
			},
			onError(err) {
				reject(err)
			},
		})
		resource.submit()
	})
}
