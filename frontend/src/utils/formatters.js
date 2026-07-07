import { createResource } from "frappe-ui"

import dayjs from "@/utils/dayjs"

// System Settings 문서 직접 조회는 일반 직원 권한에서 PermissionError를
// 발생시켜 서버 로그를 오염시킴 → 권한 불필요한 whitelisted 엔드포인트 사용
const settings = createResource({
	url: "hrms.api.get_system_locale_settings",
	auto: true,
})

export const formatCurrency = (value, currency) => {
	if (!currency) return value

	// hack: if value contains a space, it is already formatted
	if (value?.toString().trim().includes(" ")) return value

	const locale = settings.data?.country == "India" ? "en-IN" : settings.data?.language

	const formatter = Intl.NumberFormat(locale, {
		style: "currency",
		currency: currency,
		trailingZeroDisplay: "stripIfInteger",
		currencyDisplay: "narrowSymbol",
	})
	return (
		formatter
			.format(value)
			// add space between the digits and symbol
			.replace(/^(\D+)/, "$1 ")
			// remove extra spaces if any (added by some browsers)
			.replace(/\s+/, " ")
	)
}

export const formatTimestamp = (timestamp) => {
	const formattedTime = dayjs(timestamp).format("hh:mm a")

	if (dayjs(timestamp).isToday()) return formattedTime
	else if (dayjs(timestamp).isYesterday()) return `${formattedTime} yesterday`
	else if (dayjs(timestamp).isSame(dayjs(), "year"))
		return `${formattedTime} on ${dayjs(timestamp).format("D MMM")}`

	return `${formattedTime} on ${dayjs(timestamp).format("D MMM, YYYY")}`
}
