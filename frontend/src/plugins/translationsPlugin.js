// 번역 로딩 — Frappe 버전별 API 이름이 다르다 (노호 런칭 검증에서 발견).
//   구버전 v15: frappe.translate.get_boot_translations
//   신버전:     frappe.translate.load_all_translations
// 한 이름만 부르면 반대 버전에서 조용히 영어 폴백되므로 후보를 순서대로 시도한다.
export const TRANSLATION_ENDPOINT_CANDIDATES = [
	"frappe.translate.get_boot_translations",
	"frappe.translate.load_all_translations",
]

export async function fetchTranslationMessages(win) {
	if (win.frappe?.boot?.__messages) {
		return win.frappe.boot.__messages
	}
	const lang = win.frappe?.boot?.lang ?? win.navigator?.language
	const hash = win.frappe?.boot?.translations_hash || win._version_number || Date.now()
	for (const method of TRANSLATION_ENDPOINT_CANDIDATES) {
		const url = new URL(`/api/method/${method}`, win.location.origin)
		url.searchParams.append("lang", lang)
		url.searchParams.append("hash", hash) // for cache busting
		try {
			const response = await win.fetch(url)
			if (!response.ok) continue
			let payload = await response.json()
			// HTTP 200 이어도 frappe 예외 페이로드일 수 있다 — 다음 후보로.
			if (!payload || typeof payload !== "object" || payload.exc_type) continue
			// frappe whitelisted 메서드는 {message: {...}} 로 래핑해 반환한다 — 언랩.
			if (payload.message && typeof payload.message === "object") payload = payload.message
			return payload
		} catch (error) {
			console.error(`Failed to fetch translations via ${method}:`, error)
		}
	}
	return {}
}

function makeTranslationFunction() {
	let messages = {};
	return {
		translate,
		load: () => Promise.allSettled([
			setup(),
			// TODO: load dayjs locales
		]),
	}

	async function setup() {
		messages = await fetchTranslationMessages(window)
	}

	function translate(txt, replace, context = null) {
		if (!txt || typeof txt != "string") return txt;

		let translated_text = "";
		let key = txt;
		if (context) {
			translated_text = messages[`${key}:${context}`];
		}
		if (!translated_text) {
			translated_text = messages[key] || txt;
		}
		if (replace && typeof replace === "object") {
			translated_text = format(translated_text, replace);
		}

		return translated_text;
	}

	function format(str, args) {
		if (str == undefined) return str;

		let unkeyed_index = 0;
		return str.replace(
			/\{(\w*)\}/g,
			(match, key) => {
				if (key === "") {
					key = unkeyed_index;
					unkeyed_index++;
				}
				if (key == +key) {
					return args[key] !== undefined ? args[key] : match;
				}
			}
		);
	}
}

const { translate, load } = makeTranslationFunction();

export const translationsPlugin = {
	async isReady() {
		await load();
	},
	install(/** @type {import('vue').App} */ app, options) {
		const __ = translate;
		// app.mixin({ methods: { __ } })
		app.config.globalProperties.__ = __;
		app.provide("$translate", __);
	},
}
