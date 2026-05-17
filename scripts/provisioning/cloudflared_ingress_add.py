#!/usr/bin/env python3
"""
cloudflared_ingress_add.py — ~/.cloudflared/config.yml에 새 호스트 ingress 추가

사용법:
    python scripts/provisioning/cloudflared_ingress_add.py <tenant_id> [frappe_port]

    tenant_id   : 테넌트 식별자
    frappe_port : Frappe 웹서버 포트 (기본값: 8000)

동작:
    1. ~/.cloudflared/config.yml 읽기
    2. ingress 규칙 목록에서 catch-all(service: http_status:404) 직전에
       새 hostname 규칙 삽입 (멱등 — 이미 존재하면 스킵)
    3. 변경 사항 저장
    4. cloudflared 프로세스에 SIGHUP 전송 (설정 재로드)

환경변수:
    CLOUDFLARE_ZONE_NAME    (선택, 기본값: safeclaw.kr)
    CLOUDFLARED_CONFIG_PATH (선택, 기본값: ~/.cloudflared/config.yml)

종료 코드:
    0 — 성공
    1 — 오류
"""

import os
import pathlib
import signal
import subprocess
import sys

try:
    import yaml  # PyYAML
except ImportError:
    print(
        "[오류] PyYAML이 설치되어 있지 않습니다. pip install pyyaml 후 재실행하세요.",
        file=sys.stderr,
    )
    sys.exit(1)


ZONE_NAME_DEFAULT = "safeclaw.kr"
FRAPPE_PORT_DEFAULT = 8000
CATCH_ALL_SERVICE = "http_status:404"


def load_config(config_path: pathlib.Path) -> dict:
    if not config_path.exists():
        raise FileNotFoundError(f"cloudflared 설정 파일 없음: {config_path}")
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_config(config_path: pathlib.Path, config: dict) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)


def find_ingress_rules(config: dict) -> list:
    return config.setdefault("ingress", [])


def hostname_already_exists(rules: list, hostname: str) -> bool:
    return any(r.get("hostname") == hostname for r in rules)


def insert_before_catch_all(rules: list, new_rule: dict) -> bool:
    """catch-all 직전에 new_rule 삽입. 삽입 성공 시 True."""
    for i, rule in enumerate(rules):
        service = rule.get("service", "")
        if CATCH_ALL_SERVICE in str(service):
            rules.insert(i, new_rule)
            return True
    # catch-all이 없으면 마지막에 추가
    rules.append(new_rule)
    return True


def reload_cloudflared() -> bool:
    """실행 중인 cloudflared 프로세스에 SIGHUP으로 설정 재로드 요청."""
    try:
        result = subprocess.run(
            ["pgrep", "-x", "cloudflared"],
            capture_output=True, text=True
        )
        pids = result.stdout.strip().split()
        if not pids:
            print("  [경고] 실행 중인 cloudflared 프로세스를 찾지 못했습니다. 수동 재시작이 필요합니다.")
            return False
        for pid in pids:
            os.kill(int(pid), signal.SIGHUP)
            print(f"  SIGHUP 전송 → PID {pid}")
        return True
    except (ProcessLookupError, ValueError, FileNotFoundError) as exc:
        print(f"  [경고] cloudflared 재로드 실패: {exc}")
        return False


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(f"사용법: {argv[0]} <tenant_id> [frappe_port]", file=sys.stderr)
        return 1

    tenant_id = argv[1].strip().lower()
    frappe_port = int(argv[2]) if len(argv) > 2 else FRAPPE_PORT_DEFAULT

    zone_name = os.environ.get("CLOUDFLARE_ZONE_NAME", ZONE_NAME_DEFAULT)
    config_path_str = os.environ.get(
        "CLOUDFLARED_CONFIG_PATH",
        str(pathlib.Path.home() / ".cloudflared" / "config.yml"),
    )
    config_path = pathlib.Path(config_path_str)

    hostname = f"{tenant_id}.hrms.{zone_name}"
    service_url = f"http://localhost:{frappe_port}"

    print(f"[cloudflared ingress] {hostname} → {service_url}")
    print(f"  설정 파일: {config_path}")

    try:
        config = load_config(config_path)
    except FileNotFoundError as exc:
        print(f"[오류] {exc}", file=sys.stderr)
        return 1

    rules = find_ingress_rules(config)

    if hostname_already_exists(rules, hostname):
        print(f"  [OK] 이미 등록된 호스트: {hostname} (변경 없음)")
        return 0

    new_rule = {
        "hostname": hostname,
        "service": service_url,
    }
    insert_before_catch_all(rules, new_rule)
    save_config(config_path, config)
    print(f"  [OK] ingress 규칙 추가 완료: {hostname}")

    print("  cloudflared 설정 재로드 중...")
    reload_cloudflared()

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
