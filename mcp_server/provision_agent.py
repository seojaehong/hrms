# -*- coding: utf-8 -*-
"""에이전트 자동 프로비저닝 CLI — 가입 시 개통을 실행하는 진입점.

사용:
  python3 mcp_server/provision_agent.py <site> [--telegram-chat-id N] \
      --gateway-url URL [--provider hermes] [--api-key K --api-secret S] [--apply]

fail-safe: **--apply 가 없으면 dry-run**(계획만 출력, 부수효과 0)이 기본이다.
--apply 시에만 실제 수행(frappe 유저/토큰/config/바인딩)한다. frappe 가 없으면
(주입 deps 도 없으면) dry-run 으로 안전 강등한다. dry-run 출력은 시크릿을 마스킹한다.

순수 코어(agent_provisioning.py)는 '실행할 스텝을 데이터로' 만들고, 이 파일은
그 스텝을 실제 부수효과로 옮긴다. 부수효과는 deps(주입식 callable)로 분리해
테스트에서 fake 로 대체 가능하다(insurance_filing_api.py 조건부 frappe 패턴).
"""

from __future__ import annotations

import argparse
import importlib.util as _ilu
import pathlib as _pl
import sys

# ---------------------------------------------------------------------------
# Frappe 조건부 import — framework-free 테스트 환경에서 안전하게 로드
# ---------------------------------------------------------------------------
try:
	import frappe as _frappe  # noqa: PLC0415

	_FRAPPE_AVAILABLE = True
except ModuleNotFoundError:
	_frappe = None  # type: ignore[assignment]
	_FRAPPE_AVAILABLE = False


_MODULE_DIR = _pl.Path(__file__).resolve().parent


def _load_core():
	"""순수 코어(agent_provisioning.py)를 frappe 우회로 직접 로드."""
	spec = _ilu.spec_from_file_location(
		"korea_agent_provisioning_core", _MODULE_DIR / "agent_provisioning.py"
	)
	module = _ilu.module_from_spec(spec)
	assert spec.loader is not None
	spec.loader.exec_module(module)
	return module


_core = _load_core()


def _parse_args(argv):
	parser = argparse.ArgumentParser(
		prog="provision_agent.py",
		description="가입 사업장 에이전트 자동 프로비저닝(기본 dry-run, --apply 로 실행).",
	)
	parser.add_argument("site", help="테넌트 사이트 (예: noho.safeclaw.kr)")
	parser.add_argument("--telegram-chat-id", type=int, default=None)
	parser.add_argument("--gateway-url", default=None, help="hermes 게이트웨이 주소")
	parser.add_argument("--provider", default="hermes")
	parser.add_argument("--api-key", default=None, help="서비스 유저 Frappe API key")
	parser.add_argument("--api-secret", default=None, help="서비스 유저 Frappe API secret")
	parser.add_argument(
		"--apply",
		action="store_true",
		help="실제 수행(생략 시 dry-run — 부수효과 0).",
	)
	return parser.parse_args(argv)


def _binding_preview(args):
	"""dry-run 에서 보여줄(마스킹 전) 바인딩 미리보기. 자격 미제공 시 None."""
	if not (args.api_key or args.api_secret):
		return None
	return {
		"site": args.site,
		"api_key": args.api_key,
		"api_secret": args.api_secret,
		"frappe_url": f"https://{args.site}",
	}


def run(argv, *, deps=None, out=None):
	"""CLI 실행 진입점(테스트 주입식).

	deps: {action: callable(step)} — 부수효과를 옮기는 실행자(기본 default_deps).
	      주입되면 frappe 유무와 무관하게 apply 가능(테스트 seam).
	out:  줄 출력 callable(기본 print).
	반환: {"mode": "dry-run"|"apply", "plan": [...], "applied": bool}.
	"""
	args = _parse_args(argv)
	out = out or (lambda line: print(line))

	plan = _core.build_agent_provisioning_plan(
		args.site,
		telegram_chat_id=args.telegram_chat_id,
		provider=args.provider,
		gateway_url=args.gateway_url,
	)

	apply = bool(args.apply)
	if apply and deps is None and not _FRAPPE_AVAILABLE:
		# 실 apply 요청이나 frappe 미탑재 → 안전하게 dry-run 강등(fail-safe).
		out("frappe 미탑재 — 실제 적용을 건너뛰고 dry-run 으로 강등합니다.")
		apply = False

	if not apply:
		out("DRY-RUN — 아래 계획을 실제 실행하려면 --apply 를 붙이세요:")
		for step in plan:
			out("  · " + str(_core.mask_binding(step)))
		preview = _binding_preview(args)
		if preview is not None:
			out("  binding preview: " + str(_core.mask_binding(preview)))
		return {"mode": "dry-run", "plan": plan, "applied": False}

	deps = deps or default_deps()
	for step in plan:
		action = step["action"]
		handler = deps.get(action)
		if handler is None:
			raise KeyError(f"deps 에 '{action}' 실행자가 없습니다.")
		handler(step)
	out(f"적용 완료: {args.site} ({len(plan)} 스텝).")
	return {"mode": "apply", "plan": plan, "applied": True}


# ---------------------------------------------------------------------------
# 기본(실) 실행자 — --apply + frappe 환경에서만 사용된다(테스트에서는 fake 주입).
# 실제 유저/토큰/config/바인딩을 수행하는 프로덕션 경로.
# ---------------------------------------------------------------------------


def default_deps():
	return {
		"ensure_service_user": _apply_ensure_service_user,
		"issue_mcp_token": _apply_issue_mcp_token,
		"set_site_config": _apply_set_site_config,
		"bind_channel": _apply_bind_channel,
	}


def _apply_ensure_service_user(step):  # pragma: no cover - frappe 런타임 전용
	if not (_FRAPPE_AVAILABLE and _frappe is not None):
		raise RuntimeError("frappe 런타임이 필요합니다.")
	email = step["email"]
	if not _frappe.db.exists("User", email):
		user = _frappe.new_doc("User")
		user.email = email
		user.first_name = "AI HR Agent"
		user.user_type = "System User"
		for role in step.get("roles", []):
			user.append("roles", {"role": role})
		user.insert(ignore_permissions=True)


def _apply_issue_mcp_token(step):  # pragma: no cover - frappe 런타임 전용
	# 토큰 발급은 mcp_server/issue_token.py 를 별도 호출(평문은 1회 노출·파일 저장).
	# 여기서는 계획 스텝을 로그로만 남긴다(시크릿 비노출).
	_frappe.logger().info(
		f"issue_mcp_token: site={step['site']} scope={step['scope']} label={step['label']}"
	)


def _apply_set_site_config(step):  # pragma: no cover - frappe 런타임 전용
	for key, value in step["keys"].items():
		_frappe.conf[key] = value
	_frappe.logger().info(f"set_site_config: {list(step['keys'])}")


def _apply_bind_channel(step):  # pragma: no cover - frappe 런타임 전용
	_frappe.logger().info(
		f"bind_channel: {step['channel']} chat_id={step['chat_id']}"
	)


def main(argv=None):  # pragma: no cover - CLI 엔트리
	# Windows cp949 콘솔에서 한글/em-dash 출력 깨짐 방지(CLAUDE.md 규약).
	try:
		sys.stdout.reconfigure(encoding="utf-8")
	except (AttributeError, ValueError):
		pass
	run(list(sys.argv[1:] if argv is None else argv))


if __name__ == "__main__":  # pragma: no cover
	main()
