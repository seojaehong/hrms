"""Port-specific boot guard. Never restore or flush unrelated firewall rules."""
from __future__ import annotations
import argparse
import ipaddress
import os
import pathlib
import shlex
import subprocess

CHAIN = "SC_SIGN_ORIGIN"
SET = "sc_cf_origin_v4"
GUARD_ARGS = ["-p", "tcp", "-m", "tcp", "--dport", "8443", "-m", "comment", "--comment", "safeclaw-sign-boot-guard", "-j", "DROP"]
JUMP_ARGS = ["-p", "tcp", "-m", "tcp", "--dport", "8443", "-m", "comment", "--comment", "safeclaw-sign-runtime", "-j", CHAIN]
GUARD_LINE = "-A INPUT " + " ".join(GUARD_ARGS)


def with_guard(source: str) -> str:
    lines = source.splitlines(keepends=True)
    try:
        begin = next(index for index, line in enumerate(lines) if line.strip() == "*filter")
        end = next(index for index in range(begin + 1, len(lines)) if lines[index].strip() == "COMMIT")
    except StopIteration as exc:
        raise ValueError("Missing filter table; no persistent rules changed") from exc
    if any(line.strip() == GUARD_LINE for line in lines[begin:end]):
        return source
    position = next((index for index in range(begin + 1, end) if lines[index].startswith("-A INPUT ")), end)
    lines.insert(position, GUARD_LINE + "\n")
    return "".join(lines)


def parse_ranges(source: str) -> list[str]:
    networks = sorted(set(source.split()))
    if not 1 <= len(networks) <= 200:
        raise ValueError("Empty or unexpected range count")
    for value in networks:
        network = ipaddress.ip_network(value, strict=True)
        if network.version != 4 or network.prefixlen < 8:
            raise ValueError("Unsafe origin range")
    return networks


def run(arguments: list[str], content: str | None = None) -> str:
    return subprocess.run(arguments, input=content, text=True, capture_output=True, check=True).stdout


def exists(arguments: list[str]) -> bool:
    result = subprocess.run(arguments, capture_output=True)
    if result.returncode not in (0, 1):
        raise RuntimeError(f"Firewall query failed: {arguments[0]}")
    return result.returncode == 0


def ensure_guard() -> None:
    for program in ("iptables", "ip6tables"):
        if not exists([program, "-w", "-C", "INPUT", *GUARD_ARGS]):
            run([program, "-w", "-I", "INPUT", "1", *GUARD_ARGS])


def install_persistent() -> None:
    # Validate both files before writing either. Do NOT run a global restore.
    prepared: list[tuple[pathlib.Path, str, str]] = []
    for family in ("v4", "v6"):
        path = pathlib.Path(f"/etc/iptables/rules.{family}")
        original = path.read_text(encoding="utf-8")
        updated = with_guard(original)
        program = "iptables-restore" if family == "v4" else "ip6tables-restore"
        run([program, "--test"], updated)
        prepared.append((path, original, updated))
    for path, original, updated in prepared:
        backup = path.with_name(path.name + ".before-safeclaw-sign")
        if not backup.exists():
            backup.write_text(original, encoding="utf-8")
            backup.chmod(0o600)
        temporary = path.with_name(path.name + ".safeclaw-sign.tmp")
        temporary.write_text(updated, encoding="utf-8")
        temporary.chmod(0o640)
        temporary.replace(path)
    ensure_guard()


def set_chain(allow: bool) -> None:
    ensure_guard()
    if not exists(["iptables", "-w", "-S", CHAIN]):
        run(["iptables", "-w", "-N", CHAIN])
    # The permanent DROP below this chain covers the transient empty chain.
    run(["iptables", "-w", "-F", CHAIN])
    run(["iptables", "-w", "-A", CHAIN, "-i", "lo", "-j", "ACCEPT"])
    if allow:
        run(["iptables", "-w", "-A", CHAIN, "-m", "set", "--match-set", SET, "src", "-j", "ACCEPT"])
    run(["iptables", "-w", "-A", CHAIN, "-j", "DROP"])
    if exists(["iptables", "-w", "-C", "INPUT", *JUMP_ARGS]):
        run(["iptables", "-w", "-D", "INPUT", *JUMP_ARGS])
    run(["iptables", "-w", "-I", "INPUT", "1", *JUMP_ARGS])


def restore(path: pathlib.Path) -> None:
    set_chain(False)
    # Missing/corrupt state leaves the chain locked, including on reboot.
    networks = parse_ranges(path.read_text(encoding="utf-8"))
    temporary = SET + "_boot"
    for name in (SET, temporary):
        run(["ipset", "create", name, "hash:net", "family", "inet", "-exist"])
    run(["ipset", "flush", temporary])
    run(["ipset", "restore"], "".join(f"add {temporary} {cidr}\n" for cidr in networks))
    run(["ipset", "swap", temporary, SET])
    set_chain(True)
    check(path)


def check(path: pathlib.Path) -> None:
    expected = set(parse_ranges(path.read_text(encoding="utf-8")))
    actual = {line.split()[2] for line in run(["ipset", "save", SET]).splitlines() if line.startswith(f"add {SET} ")}
    if actual != expected:
        raise RuntimeError("Origin IP set does not match last-good state")
    inputs = [shlex.split(line) for line in run(["iptables", "-w", "-S", "INPUT"]).splitlines() if line.startswith("-A ")]
    if not inputs or inputs[0] != ["-A", "INPUT", *JUMP_ARGS]:
        raise RuntimeError("Origin guard is not the first INPUT rule")
    chain = [shlex.split(line) for line in run(["iptables", "-w", "-S", CHAIN]).splitlines() if line.startswith("-A ")]
    expected_chain = [["-A", CHAIN, "-i", "lo", "-j", "ACCEPT"], ["-A", CHAIN, "-m", "set", "--match-set", SET, "src", "-j", "ACCEPT"], ["-A", CHAIN, "-j", "DROP"]]
    if chain != expected_chain:
        raise RuntimeError("Unexpected origin chain")
    for program in ("iptables", "ip6tables"):
        if not exists([program, "-w", "-C", "INPUT", *GUARD_ARGS]):
            raise RuntimeError(f"Permanent IPv4/IPv6 DROP missing: {program}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("install", "lock", "restore", "check"))
    parser.add_argument("--ranges", type=pathlib.Path, default=pathlib.Path("/var/lib/safeclaw-sign/last-good-ipv4.txt"))
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise PermissionError("Root is required")
    if args.mode == "install":
        install_persistent()
        set_chain(False)
    elif args.mode == "lock":
        set_chain(False)
    elif args.mode == "restore":
        restore(args.ranges)
    else:
        check(args.ranges)
    print(f"Origin firewall {args.mode}: OK; unrelated ports unchanged")


if __name__ == "__main__":
    main()
