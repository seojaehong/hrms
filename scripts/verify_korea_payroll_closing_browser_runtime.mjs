#!/usr/bin/env node
import { spawn } from "node:child_process"
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import {
	KOREA_PAYROLL_CLOSING_BROWSER_ROUTE,
	assertKoreaPayrollClosingBrowserWalkthrough,
	buildKoreaPayrollClosingBrowserProbe,
} from "../frontend/src/data/koreaPayrollClosingBrowserRuntime.js"

const DEFAULT_BASE_URL = "http://hrms.localhost:8000"
const DEFAULT_COMPANY = "노란봉투법 데모"
const MUTATION_BOUNDARY = "read_only_no_save_submit_approve_send_provider"
const READ_ONLY_RUNTIME_METHODS = new Set([
	"hrms.regional.south_korea.admin_dashboard_runtime_api.get_korea_admin_dashboard_runtime",
	"hrms.regional.south_korea.payroll_closing_worklist_runtime_api.list_korea_payroll_closing_worklist_runtime",
])

async function main() {
	const args = parseArgs(process.argv.slice(2))
	const baseUrl = String(args["base-url"] || DEFAULT_BASE_URL).replace(/\/$/, "")
	const company = String(args.company || DEFAULT_COMPANY)
	const username = args.username || process.env.FRAPPE_BROWSER_USERNAME || process.env.FRAPPE_USERNAME
	const password = process.env.FRAPPE_BROWSER_PASSWORD || process.env.FRAPPE_PASSWORD
	const chromium = String(args.chromium || process.env.CHROMIUM_BIN || "chromium-browser")
	const reportFile = args["report-file"] ? String(args["report-file"]) : null

	let report
	try {
		report = await verifyBrowserRuntime({ baseUrl, company, username, password, chromium })
	} catch (error) {
		report = {
			contract_type: "korea_payroll_closing_browser_runtime_walkthrough_v1",
			runtime_action: "browser_runtime_read_only",
			requires_runtime_apply: false,
			requires_human_approval: true,
			ai_role: "assistant_only",
			mutation_boundary: MUTATION_BOUNDARY,
			runtime_verified: false,
			fixture_fallback_required: true,
			browser_blockers: [error instanceof Error ? error.message : String(error)],
		}
		if (!args["no-throw"]) {
			if (reportFile) await writeFile(reportFile, `${JSON.stringify(report, null, 2)}\n`)
			console.log(JSON.stringify(report, null, 2))
			process.exitCode = 1
			return
		}
	}
	if (reportFile) await writeFile(reportFile, `${JSON.stringify(report, null, 2)}\n`)
	console.log(JSON.stringify(report, null, 2))
	if (!report.runtime_verified && !args["no-throw"]) process.exitCode = 1
}

export async function verifyBrowserRuntime({ baseUrl = DEFAULT_BASE_URL, company = DEFAULT_COMPANY, username, password, chromium = "chromium-browser" } = {}) {
	username = requireNonEmptyOption(username, "username")
	password = requireNonEmptyOption(password, "password")
	const cookies = await loginAndGetCookies({ baseUrl, username, password })
	const userDataDir = await mkdtemp(join(tmpdir(), "korea-payroll-browser-"))
	const chrome = spawn(chromium, [
		"--headless=new",
		"--no-sandbox",
		"--disable-gpu",
		"--disable-dev-shm-usage",
		"--remote-debugging-address=127.0.0.1",
		"--remote-debugging-port=0",
		`--user-data-dir=${userDataDir}`,
		"about:blank",
	], { stdio: ["ignore", "ignore", "pipe"] })
	let stderr = ""
	chrome.stderr.on("data", (chunk) => {
		stderr += chunk.toString()
	})
	try {
		const port = await readDevToolsActivePort(userDataDir, () => stderr)
		const tab = await openDevtoolsTab({ port, url: "about:blank" })
		const cdp = await connectCdp(tab.webSocketDebuggerUrl)
		try {
			await cdp.send("Page.enable")
			await cdp.send("Runtime.enable")
			await cdp.send("Network.enable")
			const requestObserver = observeReadOnlyBrowserRuntimeRequests(cdp)
			for (const cookie of cookies) {
				await cdp.send("Network.setCookie", {
					name: cookie.name,
					value: cookie.value,
					url: baseUrl,
					path: "/",
					httpOnly: cookie.httpOnly,
				})
			}
			await cdp.send("Page.navigate", { url: `${baseUrl}${KOREA_PAYROLL_CLOSING_BROWSER_ROUTE}` })
			await waitForRuntime(cdp)
			await waitForSelectorText(cdp, "body", /Korea Payroll Closing/i)
			await waitForFrappe(cdp)
			const probeSource = buildKoreaPayrollClosingBrowserProbe({ company })
			const evaluated = await cdp.send("Runtime.evaluate", {
				expression: probeSource,
				awaitPromise: true,
				returnByValue: true,
				timeout: 30000,
			})
			if (evaluated.result?.exceptionDetails) {
				throw new Error(evaluated.result.exceptionDetails.text || "browser runtime probe failed")
			}
			const report = assertKoreaPayrollClosingBrowserWalkthrough(evaluated.result?.result?.value)
			report.observedBrowserApiMethods = requestObserver.assertReadOnly()
			return report
		} finally {
			cdp.close()
		}
	} finally {
		await terminateChrome(chrome)
		await rm(userDataDir, { recursive: true, force: true })
		if (stderr && process.env.DEBUG_BROWSER_RUNTIME) process.stderr.write(stderr)
	}
}

function requireNonEmptyOption(value, label) {
	if (typeof value !== "string" || !value.trim()) {
		throw new Error(`${label} is required for authenticated browser runtime verification`)
	}
	return value.trim()
}

async function loginAndGetCookies({ baseUrl, username, password }) {
	const response = await fetch(`${baseUrl}/api/method/login`, {
		method: "POST",
		headers: { "Content-Type": "application/x-www-form-urlencoded" },
		body: new URLSearchParams({ usr: username, pwd: password }),
	})
	if (!response.ok) throw new Error(`Frappe login failed with HTTP ${response.status}`)
	const payload = await response.json().catch(() => ({}))
	if (payload.message !== "Logged In") throw new Error("Frappe login did not return Logged In")
	const setCookies = response.headers.getSetCookie()
	const cookies = setCookies.map(parseSetCookie).filter((cookie) => cookie.name && cookie.value)
	if (!cookies.some((cookie) => cookie.name === "sid")) throw new Error("Frappe login did not return a sid cookie")
	return cookies
}

function parseSetCookie(header) {
	const parts = String(header).split(";").map((part) => part.trim())
	const [name, ...valueParts] = parts[0].split("=")
	return {
		name,
		value: valueParts.join("="),
		httpOnly: parts.some((part) => part.toLowerCase() === "httponly"),
	}
}

export async function readDevToolsActivePort(userDataDir, readStderr = () => "") {
	const path = join(userDataDir, "DevToolsActivePort")
	const deadline = Date.now() + 10000
	let lastError
	while (Date.now() < deadline) {
		try {
			const text = await readFile(path, "utf8")
			const [portLine] = text.split(/\r?\n/)
			const port = Number(portLine)
			if (Number.isInteger(port) && port > 0 && port < 65536) return port
			lastError = new Error("Chrome DevToolsActivePort did not contain a valid port")
		} catch (error) {
			lastError = error
		}
		const stderrPort = extractDevtoolsPortFromText(readStderr())
		if (stderrPort) return stderrPort
		await sleep(100)
	}
	const stderrPort = extractDevtoolsPortFromText(readStderr())
	if (stderrPort) return stderrPort
	throw new Error(`Chrome DevToolsActivePort did not become available: ${lastError?.message || "unknown error"}`)
}

export function extractDevtoolsPortFromText(text) {
	const match = String(text || "").match(/DevTools listening on ws:\/\/127\.0\.0\.1:(\d+)\//)
	if (!match) return null
	const port = Number(match[1])
	return Number.isInteger(port) && port > 0 && port < 65536 ? port : null
}

export function extractFrappeApiMethodFromUrl(url) {
	let parsed
	try {
		parsed = new URL(url)
	} catch {
		return null
	}
	const prefix = "/api/method/"
	if (!parsed.pathname.startsWith(prefix)) return null
	return decodeURIComponent(parsed.pathname.slice(prefix.length)) || null
}

export function assertReadOnlyBrowserRuntimeRequests(requests) {
	const observed = []
	for (const request of requests || []) {
		const method = extractFrappeApiMethodFromUrl(request?.url)
		if (!method) continue
		observed.push(method)
		if (!READ_ONLY_RUNTIME_METHODS.has(method)) {
			throw new Error(`browser runtime observed non-read-only Frappe method: ${method}`)
		}
		const payload = String(request?.postData || "")
		if (containsMutationMarker(`${method} ${payload}`)) {
			throw new Error(`browser runtime observed mutation marker in Frappe request: ${method}`)
		}
	}
	return [...new Set(observed)]
}

function observeReadOnlyBrowserRuntimeRequests(cdp) {
	const requests = []
	cdp.on("Network.requestWillBeSent", ({ request } = {}) => {
		if (!request?.url) return
		requests.push({ url: request.url, postData: request.postData || "" })
	})
	return {
		assertReadOnly() {
			return assertReadOnlyBrowserRuntimeRequests(requests)
		},
	}
}

function containsMutationMarker(value) {
	const normalized = String(value || "").toLowerCase().replace(/[^a-z0-9]+/g, "")
	return ["save", "submit", "approve", "send", "providercall"].some((marker) => normalized.includes(marker))
}

async function openDevtoolsTab({ port, url }) {
	await waitForDevtools(port)
	const response = await fetch(`http://127.0.0.1:${port}/json/new?${encodeURIComponent(url)}`, { method: "PUT" })
	if (!response.ok) throw new Error(`Chrome DevTools new tab failed with HTTP ${response.status}`)
	return response.json()
}

async function waitForDevtools(port) {
	const deadline = Date.now() + 10000
	while (Date.now() < deadline) {
		try {
			const response = await fetch(`http://127.0.0.1:${port}/json/version`)
			if (response.ok) return
		} catch {}
		await sleep(100)
	}
	throw new Error("Chrome DevTools endpoint did not become ready")
}

async function waitForRuntime(cdp) {
	await pollEvaluate(cdp, "document.readyState === 'complete' || document.readyState === 'interactive'", Boolean, "browser page did not finish loading")
}

async function waitForFrappe(cdp) {
	await pollEvaluate(cdp, "Boolean(window.frappe && typeof window.fetch === 'function')", Boolean, "Frappe/fetch runtime did not become available in browser")
}

async function waitForSelectorText(cdp, selector, pattern) {
	await pollEvaluate(
		cdp,
		`document.querySelector(${JSON.stringify(selector)})?.innerText || ''`,
		(value) => pattern.test(String(value)),
		`browser DOM did not contain ${pattern}`,
	)
}

async function pollEvaluate(cdp, expression, predicate, message) {
	const deadline = Date.now() + 30000
	let lastValue
	while (Date.now() < deadline) {
		const result = await cdp.send("Runtime.evaluate", { expression, returnByValue: true })
		lastValue = result.result?.result?.value
		if (predicate(lastValue)) return lastValue
		await sleep(250)
	}
	throw new Error(`${message}; last=${JSON.stringify(lastValue)}`)
}

async function terminateChrome(chrome) {
	if (chrome.exitCode !== null || chrome.signalCode !== null) return
	const closed = new Promise((resolve) => chrome.once("close", resolve))
	chrome.kill("SIGTERM")
	const timeout = sleep(3000).then(() => "timeout")
	if ((await Promise.race([closed, timeout])) === "timeout") {
		chrome.kill("SIGKILL")
		await Promise.race([closed, sleep(3000)])
	}
}

function connectCdp(url) {
	const socket = new WebSocket(url)
	let nextId = 1
	const pending = new Map()
	const eventHandlers = new Map()
	socket.addEventListener("message", (event) => {
		const message = JSON.parse(event.data)
		if (message.id && pending.has(message.id)) {
			const { resolve, reject } = pending.get(message.id)
			pending.delete(message.id)
			if (message.error) reject(new Error(message.error.message || JSON.stringify(message.error)))
			else resolve(message)
			return
		}
		if (message.method && eventHandlers.has(message.method)) {
			for (const handler of eventHandlers.get(message.method)) handler(message.params || {})
		}
	})
	function rejectPending(error) {
		for (const { reject } of pending.values()) reject(error)
		pending.clear()
	}
	socket.addEventListener("close", () => rejectPending(new Error("Chrome DevTools WebSocket closed")))
	socket.addEventListener("error", () => rejectPending(new Error("Chrome DevTools WebSocket error")))
	return new Promise((resolve, reject) => {
		socket.addEventListener("open", () => {
			resolve({
				send(method, params = {}) {
					const id = nextId++
					socket.send(JSON.stringify({ id, method, params }))
					return new Promise((resolveSend, rejectSend) => pending.set(id, { resolve: resolveSend, reject: rejectSend }))
				},
				on(method, handler) {
					if (!eventHandlers.has(method)) eventHandlers.set(method, new Set())
					eventHandlers.get(method).add(handler)
					return () => eventHandlers.get(method)?.delete(handler)
				},
				close() {
					socket.close()
				},
			})
		})
		socket.addEventListener("error", () => reject(new Error("Chrome DevTools WebSocket connection failed")))
	})
}

function parseArgs(argv) {
	const parsed = {}
	for (let index = 0; index < argv.length; index += 1) {
		const item = argv[index]
		if (!item.startsWith("--")) continue
		const key = item.slice(2)
		if (key === "password") throw new Error("--password is not supported; use FRAPPE_BROWSER_PASSWORD from a secret environment")
		if (key === "no-throw") parsed[key] = true
		else parsed[key] = argv[++index]
	}
	return parsed
}

function sleep(ms) {
	return new Promise((resolve) => setTimeout(resolve, ms))
}

if (import.meta.url === `file://${process.argv[1]}`) {
	main()
}
