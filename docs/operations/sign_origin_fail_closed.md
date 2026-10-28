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

## WAF compatibility before a signing URL cutover

Test request-body size as well as tokenless HTML and assets. The managed core
rule set blocks request bodies over 8192 bytes (`SizeRestrictions_BODY`), which
can reject a base64 signature image before application session validation.
An accessible page is therefore not sufficient evidence of signing support.

Keep the IP rate rule and other managed protections. If an approved exception
is necessary, first add a trailing Block rule matching the managed
`awswaf:managed:aws:core-rule-set:SizeRestrictions_Body` label unless BOTH the
URI exactly equals the configured signing API and the method exactly equals
POST. Then override only `SizeRestrictions_BODY` to Count. The compensating
rule must run after the core group; never add an early Allow rule that skips
other threat checks. Keep the origin's actual request-body cap (1 MiB in the
provided nginx template). Obtain approval before relaxing body protection.

Flat-rate Free eligibility does not establish support for these custom WAF
statements. Validate through AWS and retain any feature-not-in-plan rejection
as evidence. If the required protection is unsupported, use an approved
pay-as-you-go configuration rather than weakening it to fit a plan. Read back
the deployed web ACL: only one Count override, exact path/method exception,
correct trailing priority, and unchanged IP limit and other managed actions.

Use synthetic invalid sessions only: small and large signing POST bodies
should reach application session rejection; other large-body paths and GET
requests should remain WAF-blocked; a body over the origin cap should be 413.
This proves request routing and body limits, not successful authenticated
signing. Configuration propagation can take time: preserve the initial failed
probe and rerun after confirming the actual deployed configuration.
