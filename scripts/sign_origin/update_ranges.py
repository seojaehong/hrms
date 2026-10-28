"""Prepare CloudFront origin IPv4 rules; apply only after explicit network approval."""
from __future__ import annotations
import argparse
import ipaddress
import json
import os
import pathlib
import subprocess
import urllib.request

OWNER = "safeclaw-sign-origin-v1"
SET_NAME = "sc_cf_origin_v4"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--nsg-id-file", type=pathlib.Path)
    parser.add_argument("--oci", default="oci")
    parser.add_argument("--oci-config")
    parser.add_argument("--last-good", type=pathlib.Path, default=pathlib.Path("/var/lib/safeclaw-sign/last-good-ipv4.txt"))
    args = parser.parse_args()
    with urllib.request.urlopen("https://ip-ranges.amazonaws.com/ip-ranges.json", timeout=20) as response:
        document = json.load(response)
    networks = sorted({item["ip_prefix"] for item in document["prefixes"] if item["service"] == "CLOUDFRONT_ORIGIN_FACING"})
    if not 1 <= len(networks) <= 200:
        raise ValueError("Unexpected range count; existing rules retained")
    for cidr in networks:
        network = ipaddress.ip_network(cidr, strict=True)
        if network.version != 4 or network.prefixlen < 8:
            raise ValueError("Unsafe CIDR; existing rules retained")
    args.out.mkdir(parents=True, exist_ok=True)
    def rule(cidr: str) -> dict[str, object]:
        return {"description": OWNER, "direction": "INGRESS", "protocol": "6", "source": cidr, "sourceType": "CIDR_BLOCK", "isStateless": False, "tcpOptions": {"destinationPortRange": {"min": 8443, "max": 8443}}}
    for offset in range(0, len(networks), 25):
        (args.out / f"rules-{offset // 25:03}.json").write_text(json.dumps([rule(cidr) for cidr in networks[offset:offset + 25]], indent=2), encoding="utf-8")
    (args.out / "cloudfront-ipv4.txt").write_text("\n".join(networks) + "\n", encoding="utf-8")
    if not args.apply:
        print(f"PLAN ONLY: IPv4 origin ranges={len(networks)}; port=8443; network changes=0")
        return
    if os.geteuid() != 0 or args.nsg_id_file is None or not args.oci_config:
        raise RuntimeError("Apply requires root and explicit dedicated NSG ID file")
    nsg = args.nsg_id_file.read_text(encoding="utf-8").strip()
    if not nsg.startswith("ocid1.networksecuritygroup."):
        raise ValueError("Invalid NSG ID")
    cli = [args.oci, "--config-file", args.oci_config, "--output", "json", "network", "nsg"]
    result = subprocess.run(cli + ["get", "--nsg-id", nsg], capture_output=True, text=True, check=True)
    group = json.loads(result.stdout)["data"]
    if group["display-name"] != "SafeClawSignOrigin" or group.get("freeform-tags", {}).get("managed-by") != OWNER:
        raise ValueError("Refusing to modify a non-dedicated NSG")
    result = subprocess.run(cli + ["rules", "list", "--nsg-id", nsg, "--all"], capture_output=True, text=True, check=True)
    # OCI CLI emits no stdout for a successful empty collection.
    current = json.loads(result.stdout)["data"] if result.stdout.strip() else []
    for item in current:
        ports = (item.get("tcp-options") or {}).get("destination-port-range") or {}
        if item.get("description") != OWNER or item.get("direction") != "INGRESS" or item.get("protocol") != "6" or ports != {"min": 8443, "max": 8443}:
            raise ValueError("Unexpected NSG rule; no rules changed")
    additions = sorted(set(networks) - {item["source"] for item in current})
    removals = [item["id"] for item in current if item["source"] not in networks]
    # Prepare the new host set completely before mutating cloud rules.
    temporary = f"{SET_NAME}_next"
    subprocess.run(["ipset", "create", SET_NAME, "hash:net", "family", "inet", "-exist"], check=True)
    subprocess.run(["ipset", "create", temporary, "hash:net", "family", "inet", "-exist"], check=True)
    subprocess.run(["ipset", "flush", temporary], check=True)
    commands = "".join(f"add {temporary} {cidr}\n" for cidr in networks)
    subprocess.run(["ipset", "restore"], input=commands, text=True, check=True)
    for offset in range(0, len(additions), 25):
        path = args.out / f"add-{offset // 25:03}.json"
        path.write_text(json.dumps([rule(cidr) for cidr in additions[offset:offset + 25]]), encoding="utf-8")
        subprocess.run(cli + ["rules", "add", "--nsg-id", nsg, "--security-rules", f"file://{path}"], check=True, stdout=subprocess.DEVNULL)
    for offset in range(0, len(removals), 25):
        path = args.out / f"remove-{offset // 25:03}.json"
        path.write_text(json.dumps(removals[offset:offset + 25]), encoding="utf-8")
        subprocess.run(cli + ["rules", "remove", "--nsg-id", nsg, "--security-rule-ids", f"file://{path}", "--force"], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["ipset", "swap", temporary, SET_NAME], check=True)
    state = args.last_good.with_name(args.last_good.name + ".tmp")
    state.write_text("\n".join(networks) + "\n", encoding="utf-8")
    state.chmod(0o600)
    state.replace(args.last_good)
    # The *_next set retains the previous host list until the next update.
    print(f"APPLIED: ranges={len(networks)}; added={len(additions)}; removed={len(removals)}")


if __name__ == "__main__":
    main()
