---
name: private-connectivity-troubleshooting
title: Troubleshoot "cannot connect" over an Atlas private endpoint or peering
summary: A decision tree that separates DNS, endpoint state, network rules, access list, TLS and connection-string problems, with the exact test command for each branch.
applies_to: [atlas]
sources:
  - skills/mongodb-atlas-expert/references/mongodb-aws-networking.md
  - skills/mongodb-atlas-expert/references/mongodb-atlas-azure.md
  - skills/mongodb-atlas-expert/references/mongodb-atlas-gcp.md
  - skills/mongodb-atlas-expert/references/mongodb-atlas-multicloud.md
  - skills/mongodb-atlas-expert/references/mongodb-atlas-terraform.md
  - skills/mongodb-expert/references/mongodb-driver-internals.md
  - skills/mongodb-expert/references/mongodb-connection-string.md
  - skills/mongodb-expert/references/mongodb-error-codes.md
---
# Troubleshoot "cannot connect" over an Atlas private endpoint or peering

## When to use
- An application or `mongosh` cannot reach an Atlas cluster through a private endpoint (AWS PrivateLink, Azure Private Link, GCP Private Service Connect) or a VPC/VNet peering.
- Symptoms: `getaddrinfo ENOTFOUND`, `MongoServerSelectionError`, connection timeouts, TLS handshake errors, "authentication failed", or a connection that works from one subnet and not another.

## Prerequisites (checklist)
- [ ] A shell on a host in the same network, subnet and DNS configuration as the failing application (a debug pod for Kubernetes). Testing from your laptop proves nothing about a private path.
- [ ] The exact connection string the application uses, with the password removed.
- [ ] `nslookup` or `dig`, `nc` (or `telnet`), `openssl` and `mongosh` on that host.
- [ ] Read access to the Atlas project (endpoint status, access list) and to the cloud network settings (security groups / NSGs / firewall rules, DNS zones).

## Steps

1. Classify the string. Decide which path the string is meant to use.
   ```bash
   echo "$MONGODB_URI" | sed -E 's#//[^@]*@#//<redacted>@#'
   ```
   Expect: a `mongodb+srv://` host. A standard host like `cluster0.xxxxx.mongodb.net` is the public name; a private-endpoint-aware or peering string has a different host (the Azure corpus example is `cluster0-pl-0.<id>.mongodb.net`). If the application uses the public string, it goes to the public path and the access list decides, not the private endpoint. Fix the string first and retest.

2. Branch A, DNS: resolve the SRV record.
   ```bash
   nslookup -type=SRV _mongodb._tcp.<srv-host>
   dig _mongodb._tcp.<srv-host> SRV +short
   dig <srv-host> TXT +short
   ```
   Expect: one SRV answer per node, each with a port, and a TXT record carrying default options. Outcomes:
   - NXDOMAIN, empty answer, or timeout: go to step 3.
   - Answers exist: go to step 4.

3. Fix DNS resolution.
   - Confirm DNS egress on port 53 is allowed and the host uses the resolver you think it does (`cat /etc/resolv.conf`). On Azure the VM nameserver should be the Azure resolver unless you forward deliberately.
   - Custom or corporate DNS that does not forward `*.mongodb.net` to the cloud resolver: add a conditional forwarder for `mongodb.net`. A public `mongodb.net` zone on the custom server shadows the private zone (split-horizon conflict); forward only to the resolver that knows the private records.
   - Azure: the Private DNS Zone must be linked to every VNet that needs it, including spokes and the AKS node VNet.
     ```bash
     az network private-dns link vnet list --zone-name <cluster-id>.mongodb.net --resource-group <rg>
     az network private-dns record-set a list --zone-name <cluster-id>.mongodb.net --resource-group <rg>
     ```
   - GKE: if CoreDNS does not forward `.mongodb.net`, add `mongodb.net:53 { forward . /etc/resolv.conf }` to its ConfigMap.
   - GCP manual A records: if the forwarding rule IP changed after the endpoint was recreated, update the records.
   - Intermittent `ENOTFOUND` after hours of success: query repeatedly with `dig +short SRV ...` and compare; check the resolver's negative-cache TTL. A temporary workaround is a `mongodb://host1,host2,host3/...` string that skips SRV.
   Expect: the SRV query now returns answers. Return to step 2.

4. Branch B, address: resolve each node host from the SRV answer.
   ```bash
   nslookup <node-host-from-srv-answer>
   ```
   Expect on a private path: a private address (your endpoint IP or an address in the peering container range). A public address means this host is resolving through public DNS, so traffic will leave the private path. Azure uses A records for the `pl-N-<region>` names; AWS uses CNAMEs, so an AWS answer showing a CNAME chain is normal.
   - Public address where private was expected: go back to step 3 (zone link, forwarder, shadowing).
   - Private address: go to step 5.

5. Branch C, endpoint or peering state in Atlas and the cloud.
   ```bash
   atlas privateEndpoints aws list --projectId <project-id>        # or azure / gcp
   atlas privateEndpoints aws describe <endpoint-service-id> --projectId <project-id>
   atlas networking peering list --projectId <project-id>
   ```
   Expect: the endpoint service and the registered interface are available (Azure path in the corpus: Atlas `Creating -> Available`, yours `Initiating -> Available`), or the peering is available. Common non-ready states:
   - GCP "Waiting for User" for more than 30 minutes: the Atlas side has not received a matching forwarding rule. Verify the forwarding rule exists in the right project and region, is active, targets the Atlas service attachment, and that the **name** (not IP) was submitted. If not fixable, delete and recreate both sides.
   - Azure connection pending: approve it in Atlas or on the Azure endpoint.
   - AWS: the VPC endpoint must target the service name Atlas returned and be registered with Atlas.
   - Region mismatch: a multi-region cluster needs one endpoint per Atlas region. If one region has none, nodes in it are unreachable even though others work.
   - Peering: confirm it was accepted on the cloud side and routes exist in the route table of the failing subnet (`aws ec2 describe-route-tables`).

6. Branch D, TCP reachability and security rules. Use the host and port from the SRV answer.
   ```bash
   nc -zv <node-host> <port-from-srv>
   ```
   (`telnet <node-host> <port>` also works.) Expect: succeeded or connected. On timeout:
   - Private-endpoint SRV strings advertise per-node ports starting at 1024 (Azure and GCP notes). Allow TCP 1024-65535 outbound from the application to the endpoint IP or subnet, and inbound on the endpoint's security group (AWS) when it filters. A rule for 27017 alone blocks them.
   - AWS: the corpus note lists 27015-27017 for outbound rules and an inbound rule on the endpoint ENI from application security groups. Verify in the current MongoDB docs: the port range for your connection type.
   - Azure: NSG on the application subnet outbound; NSG on the endpoint subnet only applies if network policies are enabled on that subnet (`--private-endpoint-network-policies Enabled`). Azure Firewall in the path needs a network rule for TCP 1024-65535. `az network watcher test-connectivity --source-resource <vm-id> --dest-address <endpoint-ip> --dest-port <port> --resource-group <rg>` shows which hop blocks.
   - GCP: egress firewall rule to the PSC subnet for TCP 1024-65535; Shared VPC service projects need `roles/compute.networkUser` on the host subnet; cross-region clients need Global Access on the forwarding rule.
   - Peering: security groups and NACLs must allow the Atlas container CIDR; the source must be in a subnet whose route table has the peering route.
   - Connection refused (not timeout): port closed or cluster paused. Check the cluster state in Atlas.
   Expect: `nc` succeeds on every port from the SRV answer.

7. Branch E, access list and authentication.
   ```bash
   atlas accessLists list --projectId <project-id>
   ```
   Expect: an entry covering the client's source (peered CIDR or security group for peering). For private endpoints the corpus says an access list entry may be optional (Azure note); Verify in the current MongoDB docs: whether your project needs an entry for private endpoint traffic. A missing entry shows as timeout or a rejected connection in the Atlas activity feed; a bad user shows as "Authentication failed" (check `authSource=admin` for SCRAM users and the password encoding). Entries propagate in about five minutes.

8. Branch F, TLS.
   ```bash
   openssl s_client -connect <node-host>:<port> -servername <node-host> </dev/null 2>/dev/null | openssl x509 -noout -subject -issuer -dates
   ```
   Expect: a certificate chain that validates against the system CA store. Atlas uses a public CA, so `tlsCAFile` is not normally needed. If it fails:
   - An old OS CA bundle: update it. Drivers must support TLS 1.2 or later.
   - A TLS-inspecting corporate proxy replaced the chain: bypass `*.mongodb.net` or add the corporate CA with `tlsCAFile`.
   - Handshake hangs for 5 to 10 seconds: OCSP lookups blocked by egress rules. Allow outbound port 80 to the CA's OCSP responder, or as a stopgap set `tlsDisableOCSPEndpointCheck=true`.
   - Hostname mismatch after you connected by IP or an alias: use the Atlas host names. Do not use `tlsAllowInvalidHostnames` or `tlsInsecure` outside a short test.

9. Branch G, the driver and a clean client test.
   ```bash
   mongosh "<connection-string>" --username <db-user> --eval 'db.runCommand({ ping: 1 })'
   ```
   Expect: `{ ok: 1 }`. If `mongosh` works and the application does not, compare:
   - the exact string the app reads (environment variable, secrets store, trailing characters, special characters in the password that are not percent-encoded);
   - driver version (old drivers may not handle SRV or TLS 1.2 well);
   - `serverSelectionTimeoutMS` (default 30000 ms) so the app does not fail before DNS or the TCP check can recover;
   - `directConnection=true` (rarely correct for Atlas), `srvMaxHosts`, or a port added to an SRV URI (a port or a second host in a `mongodb+srv://` string is rejected);
   - pool settings in serverless or Kubernetes workloads: set `maxPoolSize` small (5 to 10) for many replicas.

10. Branch H, nothing above fits. Collect evidence and escalate.
    - Run steps 2, 4, 6 and 9 from the failing host and from a working host; keep the outputs.
    - Atlas activity feed and the driver log with connection debug logging on.
    - NSG flow logs or VPC flow logs for the failing source and destination.

## Decision summary
| Observation | Likely cause | Go to |
|---|---|---|
| SRV query fails | resolver or forwarder, zone link | step 3 |
| Node host resolves to public IP | private zone not linked, shadowed, wrong string | steps 1, 3 |
| Resolves private, `nc` times out | security group, NSG, firewall, route, endpoint not available | steps 5, 6 |
| `nc` works, mongosh times out or is rejected | access list, user, or TLS | steps 7, 8 |
| mongosh works, app fails | string, driver, timeout, pool | step 9 |
| One region fails, others work | missing endpoint for that region | step 5 |

## Verify
```bash
nslookup -type=SRV _mongodb._tcp.<srv-host>
nc -zv <node-host> <port>
mongosh "<connection-string>" --eval 'db.runCommand({ ping: 1 })'
```
Expect: private answers, an open port for every node, and `ok: 1`. Then confirm the application's own health check, and repeat from each network that should connect.

## Rollback / abort
- Do not widen the access list to `0.0.0.0/0` to "see if it works". If you do it for a short test, set an expiry (`atlas accessLists create ... --deleteAfterDate "<timestamp>"`) and remove it after. Verify in the current MongoDB docs: the spelling of this flag differs by CLI version (`--deleteAfter` in the current CLI); run `atlas accessLists create --help` and use the flag it lists.
- Revert any DNS forwarder or zone change that made things worse; keep a copy of the previous configuration.
- Do not delete an endpoint to fix a state problem until traffic has moved to another path.

## Pitfalls
- Testing from a laptop or a different subnet and concluding the endpoint works or fails.
- Opening only port 27017 for a private SRV string that uses ports from 1024.
- A single DNS zone link: new spokes, AKS node networks and CI runners are not linked.
- Public DNS zone for `mongodb.net` on the corporate resolver shadows the private zone.
- Stale hand-made A records after an endpoint was recreated.
- Assuming one endpoint covers all regions of a multi-region cluster.
- Using `tlsInsecure=true` "for now".
- Using the standard public string against a private-only project.
- Treating a transient `HostUnreachable` (error code 6) as an outage: the driver retries when retryable reads/writes are on. If it persists, it is infrastructure.

## Sources
- skills/mongodb-atlas-expert/references/mongodb-aws-networking.md:142 (DNS/SRV, split-horizon, `dig` SRV), :179 (security groups), :188 (error table and diagnostic steps)
- skills/mongodb-atlas-expert/references/mongodb-atlas-azure.md:52 (A records vs CNAME), :84 (NSG ports, policies, flow logs), :1161 (DNS failures), :1195 (NSG blocking, test-connectivity), :1217 (AKS), :1427 (anti-patterns)
- skills/mongodb-atlas-expert/references/mongodb-atlas-gcp.md:145 (SRV chain, ports), :1109 (stuck state), :1123 (ENOTFOUND diagnosis, CoreDNS), :1167 (Shared VPC), :1301 (anti-patterns)
- skills/mongodb-atlas-expert/references/mongodb-atlas-multicloud.md:672 (one endpoint per region)
- skills/mongodb-expert/references/mongodb-driver-internals.md:871 (SRV resolution, TXT), :895 (SRV pitfalls), :915 (Atlas TLS), :930 (OCSP), :1047 (intermittent SRV failures)
- skills/mongodb-expert/references/mongodb-connection-string.md:159 (SRV format), :661 (`serverSelectionTimeoutMS` default 30000)
- skills/mongodb-expert/references/mongodb-error-codes.md:128 (code 6 HostUnreachable)
