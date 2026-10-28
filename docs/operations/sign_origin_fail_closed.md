# Signing origin boot guard

The origin port is separate from existing listeners. A constant IPv4/IPv6 DROP
for TCP 8443 is added to existing persistent filter tables without a global
firewall restore. Unrelated rules remain byte-for-byte unchanged.

`scripts/sign_origin/firewall.py install` prepares this guard. `restore` first
locks the origin chain, validates the root-owned last-good IPv4 state, populates
an IP set, then enables only loopback and origin-facing source ranges. Missing,
empty, corrupt, or broad CIDRs fail with the terminal DROP still installed.

The firewall unit runs after netfilter-persistent and before network-pre/Docker.
The proxy unit Requires/BindsTo the guard, verifies it before every start, and
does not use Docker restart policies or port publishing. No certificate means
the proxy unit stays inactive. Its TLS files and nginx configuration are supplied
outside the public repository; never commit origin tokens or customer hosts.

Hourly IP updates use an exclusive lock and a dedicated tagged cloud NSG. Only
the signing origin rules may change. Keep the last-good file root-only and save
it after a successful update. Failure must never fall back to unrestricted IPs.

Validation:

```sh
python3 scripts/sign_origin/test_firewall.py -v
sudo python3 /usr/local/lib/safeclaw-sign/firewall.py check
```

Before claiming reboot verification, perform a real approved host reboot and
inspect boot ID, service ordering, firewall rules, source ranges, listening
addresses, and external denial. Fault injection alone is not a reboot test.
On shared hosts, inventory workloads without automatic restart and obtain a
maintenance window including their restoration before rebooting.

Before publishing a signing URL, verify direct external denial while the origin
is actually running, missing/wrong secret denial, /app and /login denial with a
valid secret, TLS name/chain, and signing page/assets through CloudFront. Do not
send employee messages or change signing links as part of infrastructure tests.

Render `scripts/sign_origin/nginx.conf.template` with an explicit envsubst
allowlist (`envsubst '${ORIGIN_HOST} ${FRAPPE_SITE}'`); nginx request variables
must remain literal. Keep the rendered tenant-specific file outside Git.
Both `/esign` and the framework's canonical `/hrms/esign` must be allowed for
GET/HEAD: the client router changes to the canonical path, and refreshes must
still work. The 64-character origin token requires map_hash_bucket_size 128;
test with a realistic-length synthetic token, not a short placeholder.
