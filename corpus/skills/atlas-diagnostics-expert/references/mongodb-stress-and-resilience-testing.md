<!-- hub-reference-banner -->
> **Reference file — part of the `atlas-diagnostics-expert` hub.**
> Sibling MongoDB sub-topics are reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-stress-and-resilience-testing
title: MongoDB Stress, Soak, and Chaos-Resilience Testing
version: "1.0.0"
last-updated: "2026-07-14"
category: mongodb
description: >
  MongoDB/Atlas breaking-point, soak, and chaos-resilience testing — pushing a deployment past its
  limits to find failure modes (the inverse of capacity benchmarking's "how fast" question).
  TRIGGER: soak/endurance testing (long-duration runs surfacing memory leaks, connection-pool
  exhaustion, WiredTiger cache thrashing, ticket starvation, oplog window shrinkage);
  breaking-point/overload testing to find the first bottleneck past the saturation ceiling;
  chaos-style resilience testing under load (primary kill, network partition, disk-full/IO-stall
  injection); safe non-prod Atlas execution guardrails; Atlas Test Failover API/CLI/UI;
  Toxiproxy/Chaos Mesh/Gremlin fault injection.
  SKIP: capacity/throughput benchmarking (mongodb-performance-benchmarking), tier sizing with no
  fault-injection angle (mongodb-capacity-planning), diagnosing an already-slow system with no
  deliberate test (mongodb-performance-troubleshooting), generic chaos engineering unrelated to
  MongoDB (devops-containers-cicd).
tags:
  - stress-testing
  - soak-testing
  - endurance-testing
  - chaos-engineering
  - resilience-testing
  - overload-testing
  - breaking-point
  - atlas-test-failover
  - wiredtiger
  - connection-pool
keywords:
  - mongodb stress testing
  - soak testing mongodb
  - endurance testing mongodb
  - breaking point testing
  - overload testing mongodb
  - chaos engineering mongodb
  - kill primary under load
  - network partition under load
  - atlas test failover
  - toxiproxy mongodb
  - chaos mesh mongodb
  - gremlin mongodb
  - wiredtiger cache eviction thrashing
  - connection pool exhaustion sustained load
  - oplog window shrinkage
  - ticket starvation
  - non-production atlas cluster safety
  - w:majority split brain
  - thundering herd reconnect
whenToUse:
  - Running a long-duration (hours to days) soak test to surface memory leaks or connection pool exhaustion
  - Deliberately ramping load past a known saturation ceiling to find the actual failure mode
  - Combining fault injection (kill primary, partition network, stall disk I/O) with active load
  - Designing a safe blast-radius-contained overload or chaos test against a non-production Atlas cluster
  - Investigating WiredTiger cache eviction thrashing, ticket starvation, or oplog window collapse under sustained write pressure
  - Validating application resilience to a primary failover during peak write load
  - Choosing between Atlas's built-in Test Failover feature and third-party chaos tooling (Gremlin, Chaos Mesh, Toxiproxy)
whenNotToUse:
  - Proactive throughput/capacity benchmarking (YCSB, thread-sweep saturation, Atlas tier selection) — use mongodb-performance-benchmarking
  - Working-set sizing, IOPS forecasting, tier right-sizing with no breaking-point or fault-injection component — use mongodb-capacity-planning
  - Diagnosing symptoms in a production system that is already slow, with no deliberate test involved — use mongodb-performance-troubleshooting
  - Generic chaos-engineering platform mechanics with no MongoDB-specific angle — use devops-containers-cicd
related_skills:
  - mongodb-performance-benchmarking
  - mongodb-capacity-planning
  - mongodb-performance-troubleshooting
  - mongodb-wiredtiger-internals
  - mongodb-replication
  - mongodb-atlas-expert
  - devops-containers-cicd
---

# MongoDB Stress, Soak, and Chaos-Resilience Testing

## Overview

This reference covers the "find where it breaks" side of MongoDB testing — deliberately pushing a
MongoDB/Atlas deployment past its operating limits to discover failure modes, as opposed to
`mongodb-performance-benchmarking`'s "how fast does it go" proactive capacity methodology (YCSB
workloads, thread-sweep saturation, tool selection for throughput measurement). The two are
complementary and run in sequence: capacity benchmarking establishes the saturation ceiling; this
reference covers what happens when you deliberately go past it, sustain pressure on it for a long
time, or knock out a component while under it.

Three distinct testing disciplines are covered:

1. **Sustained overload / soak testing** — long-duration runs (hours to days) at or near peak load
   to surface issues that only manifest over time: memory leaks, connection pool exhaustion,
   WiredTiger cache thrashing, ticket starvation, oplog window shrinkage, replication lag drift.
2. **Breaking-point / overload testing** — ramping load past the known saturation point to find the
   actual failure mode (cascading failure, thundering herd, cache eviction death spiral) rather than
   just the throughput ceiling.
3. **Chaos-style resilience testing under load** — combining fault injection (kill a primary,
   partition the network, stall disk I/O) with active load to observe failover behavior, write
   availability windows, and split-brain risk.

A fourth section covers how to run all of the above safely against a non-production Atlas cluster
without customer-impacting side effects.

## When to Use vs. `mongodb-performance-benchmarking`

| Question being asked | Use this reference | Use `mongodb-performance-benchmarking` |
|---|---|---|
| "How many ops/sec can this cluster sustain?" | No | Yes |
| "Will M30 be enough for this workload?" | No | Yes |
| "What happens if we run 3x our benchmarked throughput for 48 hours?" | Yes | No |
| "Where does this cluster actually fail, and how?" | Yes | No |
| "What happens to in-flight writes if the primary dies during peak load?" | Yes | No |
| "Is our app resilient to a network partition while under load?" | Yes | No |
| "Did this index change improve query latency?" | No | Yes |

---

## 1. Sustained Overload / Soak Testing

### What soak testing is and why it differs from load/stress testing

Soak testing (also called endurance testing) applies **sustained, consistent load — usually at or
near peak, not extreme — for an extended duration** (typically 12–72 hours, sometimes longer for
complex systems) to surface problems that short tests cannot show at all.[^1] The distinguishing
variable is *time*, not *intensity*: a load test proves the system meets expected traffic for an
hour or two; a soak test proves it still works after running continuously for days.[^1][^2]

| Test type | Load volume | Duration | Key question |
|---|---|---|---|
| Load testing | Expected/peak | Short (1–2 hrs) | "Does it work as promised?" |
| Stress/breaking-point testing | Extreme, beyond capacity | Short bursts | "What happens when it breaks, and can it recover?" |
| Soak/endurance testing | Sustained, at or below peak | Long (12–72+ hrs) | "Will it still be running smoothly in three days?" |

*Comparison per [^1].*

A memory leak that accumulates at 50MB/hour is invisible in a 30-minute test but produces an
out-of-memory crash after roughly 20 hours of continuous traffic; a connection leak of 2
connections/minute exhausts a 500-connection pool in about 4 hours.[^2] These failure classes are
*definitionally* unreachable by short capacity benchmarking runs — soak testing is the only way to
surface them before a customer's production system does.

### Failure classes soak testing surfaces

**Driver- and application-side memory leaks.** Heap size that grows linearly with runtime, unclosed
cursors, and accumulating unbounded in-memory caches show up as steadily rising RSS over the test
window rather than a single spike.[^1][^2]

**Connection pool exhaustion over time.** A `MongoServerError: connection pool exhausted` surfaces
when concurrent demand outpaces `maxPoolSize` (default 100 connections per server in most drivers)
and `waitQueueTimeoutMS` is either unset (requests hang indefinitely) or too short relative to
sustained queue buildup.[^3] Under sustained load this presents as *slowly climbing* connection
counts and *growing* wait-queue latency rather than an immediate cliff — `db.serverStatus().connections`
and driver-level pool-monitoring events are the diagnostic surface.[^3] Because the failure is
gradual, a short capacity-benchmarking run at the same concurrency can look completely healthy while
a multi-hour soak test at identical load reveals the leak.

**WiredTiger cache thrashing / eviction storms under sustained write pressure.** WiredTiger's
internal cache defaults to the larger of 50% of (RAM − 1GB) or 0.256GB, and is not partitioned
between reads and writes or by database/collection — the whole `mongod` shares one cache.[^4] Under
sustained heavy write load, dirty pages accumulate faster than checkpoint and eviction threads can
flush them; once the dirty-cache trigger is hit, application threads themselves are recruited to
perform eviction, which manifests as a sudden, sustained latency cliff rather than gradual
degradation. This is a `mongodb-expert` WiredTiger-internals-depth topic (cross-load
`mongodb-expert/references/mongodb-wiredtiger-internals.md` for eviction-thread/dirty-trigger
mechanics) — this reference's scope is recognizing that a **soak test is what exposes it**, since
eviction storms are a function of sustained dirty-cache accumulation, not point-in-time throughput.

**Ticket / concurrency-queue starvation.** MongoDB 7.0+ dynamically adjusts the number of concurrent
storage-engine read/write "tickets" (never exceeding 128 each), replacing the older static
`wiredTigerConcurrentReadTransactions`/`wiredTigerConcurrentWriteTransactions` parameters.[^5][^6] A
low `available` value in `queues.execution` does **not** by itself indicate overload — the
*queued* count is the actual overload signal.[^6] Under sustained overload, tickets queue instead of
being denied, so a soak test reveals rising `queues.execution` queue depth and rising ticket wait
time as a slow-building symptom, distinct from the instantaneous ticket unavailability a short spike
test might show.

**Oplog window shrinkage under sustained write load.** The Replication Oplog Window alert fires when
the time available in the primary's oplog before secondaries would fall off falls at or below a
configured threshold; the common trigger is intensive, *sustained* write/update volume that exceeds
the configured oplog size's headroom.[^7] A soak test at realistic sustained write throughput is the
only way to observe this degrade over hours, since the oplog window is a function of sustained write
rate, not instantaneous throughput. Symptoms include the "we are too stale to use `<node>` as a sync
source" log line and a node stuck in `STARTUP2`/`RECOVERING` requiring a full initial resync.[^7]
Mitigations: increase oplog size above the *peak* observed GB/hour rate, and enforce `w:majority`
write concern so the primary cannot outrun what secondaries can durably apply.[^7]

**Replication lag divergence over long runs.** Heavy sustained workloads tax secondaries applying
oplog entries; lag that is negligible in a short benchmark can widen progressively over a multi-hour
soak run, especially without an index on fields used by updates (each update then requires a
collection scan on the secondary to apply).[^8]

### Soak test design checklist

1. **Duration**: minimum ~12 hours; 48–72+ hours for complex, stateful, or connection-heavy systems.[^1][^2]
2. **Load level**: sustained at or near (not beyond) the previously benchmarked saturation point —
   soak testing is about *time*, not *intensity*; combine with Section 2 for intensity.
3. **Environment parity**: the test environment should mirror production infrastructure, network
   topology, and database configuration; using unrealistic or oversimplified test data produces
   misleading trend curves.[^2]
4. **Metrics to trend continuously** (not just point-sample): heap/RSS, CPU, disk I/O, network,
   connection counts, WiredTiger cache dirty %, ticket queue depth, oplog window size, replication
   lag, thread/queue counts, log growth rate, error rate.[^1][^2]
5. **Correlate against a baseline**: every trended metric needs a rate-of-change and a projected
   time-to-failure, not just an absolute reading — a upward-trending metric that does not
   asymptotically flatten is the soak-test failure signal.[^2]
6. **Isolation**: keep the soak environment free of unrelated maintenance jobs, backups, or other
   noisy-neighbor processes that could produce false trend signals.[^2]
7. **Common mistakes to avoid**: running too short a duration, monitoring only a subset of metrics,
   using unrealistic test data, and treating soak testing as a one-time pre-launch gate rather than a
   recurring practice ahead of major releases.[^1][^2]

---

## 2. Breaking-Point / Overload Testing Methodology

### Distinguishing the throughput ceiling from the failure mode

`mongodb-performance-benchmarking`'s thread-sweep saturation methodology finds the point at which
throughput stops increasing with concurrency — the **capacity ceiling**. Breaking-point testing
picks up from there: it deliberately **ramps load past that ceiling** to observe *how* the system
fails, not just *that* it stops scaling.[^9] This is a meaningfully different question because the
first component to visibly degrade (e.g., rising query latency) is frequently not the first
component to actually saturate (e.g., WiredTiger ticket queues or disk IOPS) — the visible symptom
and the root bottleneck are often different subsystems.

### What overload testing looks for

Per MongoDB's own guidance on the distinction: stress/breaking-point testing "intentionally pushes
systems past normal operating limits to identify breaking points, failure behavior, and recovery
characteristics" — the emphasis is on **error handling, stability, and "graceful" failure**, not
correctness under expected load.[^9] Concretely, an overload test should identify:

- **The first bottleneck to fail**, not the most visible symptom. Query latency rising is a
  downstream effect; the actual saturated resource is commonly WiredTiger ticket queue depth, disk
  IOPS, or available connections — inspect `queues.execution` queue depth (not just `available`),
  disk queue depth/latency, and connection-pool wait-queue length simultaneously with app-level
  latency to identify which saturates *first*.[^6]
- **Cascading failure paths**: does one exhausted resource (e.g., a stalled disk) cause a second,
  unrelated failure (e.g., replication lag growing until the oplog window is exceeded, forcing an
  initial resync) that outlasts the original overload event?
- **Thundering-herd effects on recovery**: when an overloaded cluster's bottleneck clears (e.g., a
  restart, a scale-up, a network recovery), do all queued/retrying clients reconnect and resend
  simultaneously, re-triggering the same saturation immediately? This is the client-side mirror of
  the server-side cache-eviction death spiral below, and is a well-documented failure mode in driver
  reconnection after a partition — see Section 3.
- **Cache-eviction "death spirals."** Once WiredTiger's dirty-cache trigger recruits application
  threads into eviction work, throughput drops, which increases the backlog of unflushed writes,
  which increases dirty-cache pressure further — a positive-feedback loop that a controlled overload
  test can trigger and measure the recovery time for, rather than encountering unexpectedly in
  production.
- **Recovery behavior**, not just failure behavior: how quickly does the system return to baseline
  once the overload is removed, and does it recover cleanly or require manual intervention (e.g., a
  node stuck in `RECOVERING` needing an initial resync)?[^7][^9]

### Practical overload test design

1. Start from the saturation ceiling already established via `mongodb-performance-benchmarking`'s
   thread-sweep methodology.
2. Ramp concurrency/throughput in controlled increments *past* that ceiling — incremental escalation
   makes it possible to isolate which resource saturates at which load level, rather than jumping
   straight to a chaotic maximum.[^9]
3. Instrument **every** candidate bottleneck simultaneously: WiredTiger ticket queues, disk I/O
   queue depth/latency, connection pool wait-queue depth, CPU run-queue length, and oplog window —
   not just application-level response time.
4. Record which metric crosses its threshold **first**, in wall-clock order — this identifies the
   true root bottleneck versus the symptom users would notice first.
5. Once a failure mode is triggered, stop adding load and measure **recovery time and recovery
   completeness** (did all secondaries catch up, did the ticket queue drain, did the app's
   connection pool recover without a restart) — this is the resilience half of the exercise, not
   just the breaking half.
6. Repeat with a targeted fix (index, config change, capacity increase) applied, to confirm the fix
   actually moved the bottleneck rather than just improving the symptom that was previously visible.

---

## 3. Chaos-Style Resilience Testing Under Load

### Why fault injection needs active load to be meaningful

Chaos engineering is "the discipline of experimenting on a distributed system in order to build
confidence in the system's capability to withstand turbulent conditions in production."[^10][^11] A
fault injected against an idle cluster (e.g., killing a primary with no in-flight writes) tests a
materially easier scenario than the same fault under peak write load, where in-flight,
not-yet-majority-replicated writes and saturated connection pools are also part of the picture. The
distinctive value of this section is **combining** the fault-injection tooling below with an active
load generator (Locust, YCSB, or the app itself) rather than running either in isolation.

### Killing a primary during peak write load

**Atlas's built-in Test Failover feature** is the safest, first-choice tool for this specific
experiment against Atlas clusters. Requesting a test failover causes Atlas to shut down the current
primary; the replica set holds an election (typically ~5 seconds) among secondaries, favoring the
one with the most complete oplog; the original primary then rejoins as a secondary and resyncs.[^12][^13]
Required prerequisites before Atlas will accept the request: all members healthy with up-to-date
monitoring, less than 10 seconds of replication lag, at least 5% free disk space on all nodes, and
enough oplog headroom for a 3-hour operation on the primary.[^12] This is deliberately conservative —
Atlas will reject the test if the cluster isn't already healthy, which is also why it is not itself
a substitute for combining the test with your OWN active load generator to observe behavior *during*
the controlled fault:

- **Invocation surfaces**: Atlas UI (Clusters → `...` → Test Resilience → Primary Failover →
  Restart Primary), Atlas CLI (`atlas clusters failover <clusterName>`), or the Atlas Admin API v2
  `Test Failover` endpoint.[^12] Not available on Free or Flex tier clusters, and not available on
  multi-tenant/shared clusters — a dedicated (M10+) cluster is required.[^13]
- **What to observe while the load generator keeps writing**: whether writes with `w:majority`
  correctly block/retry during the ~5-second election rather than silently failing; whether writes
  acknowledged with a weaker write concern before the old primary stepped down get rolled back when
  it rejoins as a secondary (expected MongoDB behavior — always inspect rollback data after a
  partition/failover under `w:1`);[^13][^14] whether the driver reconnects to the new primary without
  application-level errors (requires SRV connection format, a current driver version, and retryable
  writes / appropriate retry logic in the app).[^12]
- **Retryable writes**: enabling `retryWrites=true` on the Atlas connection string lets the driver
  transparently retry a write once against the newly elected primary, which is the standard
  mitigation for the write-availability gap during the election window.[^12]

**Third-party chaos tooling** (Gremlin, Chaos Mesh, Toxiproxy) is appropriate when the experiment
needs to go beyond what Atlas's Test Failover covers — e.g., self-managed MongoDB, Kubernetes-hosted
deployments, or fault types Atlas doesn't expose a button for (CPU/memory pressure, arbitrary disk
I/O faults, asymmetric network partitions).

- **Gremlin**: a chaos-engineering SaaS supporting CPU, memory, I/O, network-latency, and
  packet-loss "attacks" against MongoDB nodes; the documented workflow is: enable the MongoDB
  database profiler (`db.setProfilingLevel(2)`) to record per-operation `millis`, establish a
  baseline query-latency measurement, run an attack (e.g., a 50% memory-consumption attack) while
  repeating the same query, and compare — a documented example showed a query's execution time
  rising from ~0ms baseline to 150–580ms under a memory attack.[^11] Gremlin explicitly lists node
  shutdown, packet loss (affecting leader elections), and network latency between `mongod` instances
  as MongoDB-relevant attack types.[^11]
- **Chaos Mesh**: a Kubernetes-native, CRD-based chaos platform appropriate for
  Kubernetes-hosted/self-managed MongoDB. Relevant fault types: `PodChaos` (kill/restart a primary
  pod), `NetworkChaos` (latency, packet loss, packet reordering, and network partitions),
  `IOChaos` (simulates disk I/O errors, delays, and read/write failures at the file-system layer),
  and `StressChaos` (CPU/memory race conditions).[^15] Because every fault is expressed as a
  Kubernetes CRD, experiments are version-controlled and fit into existing GitOps pipelines.[^15]
- **Toxiproxy**: a TCP proxy (originally built at Shopify) for simulating network conditions —
  latency, bandwidth limits, connection resets, and timeouts — positioned as a local/CI/dev-friendly
  tool distinct from a full chaos platform.[^16] For MongoDB specifically, the documented pattern is
  routing replica-set connections through Toxiproxy so the proxy ports stand in for the real
  `mongod` hosts, then adding timeout toxics on both upstream and downstream legs to simulate a
  network partition between the driver and the primary (or between replica set members) without
  touching the underlying network or hosts.[^16] This is the lightest-weight option for the
  driver-reconnect and thundering-herd experiments below, since it requires no cluster-level access.

### Network partition under load

A network partition that isolates the primary from a majority of voting members forces it to step
down (it cannot remain primary without majority reachability), which is the core mechanism by which
MongoDB avoids split-brain.[^14] Under active write load during a partition:

- With `w:majority`, unacknowledged writes on the isolated (former) primary are never at risk of a
  silent split-brain-style divergence, because a write is not acknowledged until a majority of the
  set has it — this is the documented split-brain defense, not a side effect.[^14]
- With a weaker write concern (`w:1`), writes accepted by the old primary before it detects
  isolation and steps down **may be rolled back** once it rejoins and resyncs with the new primary,
  if the new primary never received them — inspect the rollback data directory after any
  partition-under-load experiment to quantify exactly how many writes were affected.[^14]
- The load generator should keep issuing writes with the write concern the real application uses
  (not just `w:1` for simplicity) — the whole point of the experiment is measuring the actual
  write-availability gap and rollback exposure your application would experience, which is a
  function of its own write concern choice.
- Toxiproxy (timeout toxics on both directions) or Chaos Mesh `NetworkChaos` are the practical
  injection mechanisms for a partition that Atlas's Test Failover button does not directly expose
  (Test Failover simulates a primary *shutdown*, not an asymmetric network split).[^12][^15][^16]

### Disk-full / IO-stall injection under load

Atlas's own Test Resilience checklist treats "running out of disk space" and "oversaturating the
available IOPS" as first-class chaos scenarios worth pre-production testing.[^13] For self-managed or
Kubernetes-hosted MongoDB, Chaos Mesh's `IOChaos` is the direct tool for injecting I/O delays and
read/write faults at the file-system layer to simulate this without physically filling a disk.[^15]
Combine with active write load to observe: does the primary step down or block writes gracefully
when disk I/O stalls, or does it hang indefinitely; does the Atlas alerting layer's disk-usage and
IOPS thresholds fire with enough lead time before actual write-blocking risk.

### Thundering herd on reconnect

When a fault clears (partition heals, primary election completes, disk I/O recovers), every client
whose driver was queuing or retrying operations may reconnect and resubmit simultaneously,
re-saturating the very resource that just recovered. This is the client-population mirror of the
WiredTiger cache-eviction death spiral in Section 2, and is a documented pattern in MongoDB driver
issue trackers around reconnection behavior after extended partitions.[^16] Mitigation validation
during a chaos-under-load test should specifically check for: jittered/backoff reconnect logic in
the driver or connection-pool client, whether the server-side ticket/connection admission control
absorbs the reconnect burst gracefully (see Section 1's ticket-queue metrics), and whether the
resulting queue depth spike is transient or itself triggers a secondary cascading failure.

---

## 4. Safe Execution Against Non-Production Atlas

Every technique above is, by design, destructive or load-intensive. Running any of it against a
customer's production cluster — or a shared-tenant cluster where other customers' workloads share
the underlying infrastructure — is not acceptable. This section is the guardrail layer.

### Cluster isolation practices

- **Use a dedicated, non-shared-tenant cluster.** Atlas's Test Failover feature itself will not run
  on Free-tier or Flex clusters, and is unavailable on shared/multi-tenant infrastructure — this is
  an intentional Atlas-side guardrail, not just a recommendation.[^12][^13] The same boundary should
  be treated as a hard requirement for third-party fault-injection tooling too: never point Gremlin,
  Chaos Mesh, or a load generator at anything but an M10+ dedicated cluster.
- **Separate project/org from production.** Keep stress/chaos-test clusters in a dedicated Atlas
  project (and ideally a dedicated organization) so that project-scoped alerting, IP access lists,
  and RBAC cannot be confused with production configuration, and so a mistaken API call using a
  saved profile cannot reach a production project.
- **Environment parity without shared infrastructure.** The test cluster's tier, region, and
  configuration should mirror production closely enough that findings transfer, while its data and
  network path remain fully isolated — generate realistic synthetic data rather than exercising
  against a copy of live customer data, per the soak-testing environment-parity guidance in
  Section 1.[^2]

### Guardrails against accidentally targeting production

- **Connection-string / cluster-name verification before every destructive call.** Because the Test
  Failover API, `atlas clusters failover`, and third-party agents (Gremlin, Chaos Mesh) all act on a
  named cluster or a proxied connection string, build a pre-flight check into any tooling or runbook
  that confirms the target cluster/project ID against an explicit non-prod allowlist before issuing
  a failover, kill, or fault-injection call.
- **Tagging discipline.** Tag non-production stress/chaos clusters distinctly (e.g., `env:stress-test`)
  in Atlas resource tags, and have any automation that drives load generators or chaos tooling
  refuse to run unless the target cluster carries that tag.
- **Least-privilege access.** Test Failover itself requires `Organization Owner`, `Project Owner`,
  `Project Cluster Manager`, or `Project Stream Processing Owner` access[^12] — scope the credentials
  used by chaos/load-testing automation to only the non-prod project, never an org-wide credential
  that also has access to production projects.
- **Pre-flight health check, not blind execution.** Atlas itself will reject a Test Failover request
  if the cluster isn't already healthy (lagging replication, low disk space, insufficient oplog
  headroom)[^12] — treat that same checklist as a mandatory pre-flight gate for any home-grown
  chaos/overload run too, so a test doesn't compound an already-degraded non-prod cluster into an
  unrecoverable state.

### Cost and cleanup discipline

- Soak tests by definition run for many hours to days on a dedicated (billed) cluster tier — budget
  and schedule the cluster teardown or pause immediately after the test window, rather than leaving
  a dedicated non-prod cluster running indefinitely "just in case." Confirm the teardown actually
  happened (an empty cluster list in the non-prod project, not just a calendar reminder) before
  closing out the test cycle.
- Prefer ephemeral, single-purpose non-prod clusters/projects created specifically for a test cycle
  over a long-lived shared "staging" cluster that accumulates other teams' unrelated load and
  configuration drift — this also keeps the blast radius of a chaos experiment contained to the one
  test in flight.
- For Kubernetes-hosted self-managed MongoDB under Chaos Mesh, scope experiments (via Chaos Mesh's
  CRD `selector`) tightly to the namespace and labels of the specific test deployment so a
  misconfigured experiment cannot select unrelated workloads in a shared cluster.[^15]

---

## Anti-Patterns

- **Running a short (minutes-long) test and calling it a soak test.** Memory leaks, connection-pool
  exhaustion, and oplog-window shrinkage are definitionally time-dependent; a test under ~12 hours
  cannot surface them regardless of load intensity.[^1][^2]
- **Injecting a fault against an idle cluster and calling it done.** A primary-kill or partition test
  with no concurrent write load skips the exact failure modes (in-flight writes, connection-pool
  saturation, thundering-herd reconnect) that matter in production.
- **Treating the first visible symptom as the root cause.** Rising query latency during an overload
  test is often a downstream effect of ticket-queue or disk-IOPS saturation elsewhere — instrument
  every candidate bottleneck, not just application-level response time.
- **Using `w:1` in a chaos-under-load test when the real application uses `w:majority` (or vice
  versa).** The write concern under test determines the actual rollback/availability exposure —
  testing with a different write concern than production measures the wrong risk.
- **Running any of this against a shared-tenant or production-adjacent cluster.** Atlas itself
  blocks Test Failover on shared/free tiers for this reason;[^12][^13] treat the same boundary as
  non-negotiable for third-party tooling.
- **Skipping the pre-flight health check.** An already-unhealthy cluster (lagging replication, low
  disk, thin oplog headroom) can be pushed into an unrecoverable state by a test that assumes a
  healthy starting point.[^12]

## Troubleshooting Quick Reference

| Symptom during a stress/soak/chaos run | Likely cause | Where to look |
|---|---|---|
| Steady upward RSS/heap trend, no plateau | Driver or app-level memory leak | Section 1 — soak metrics |
| Connection count climbs, never drains | Connections not released / `maxPoolSize` undersized for concurrency | `db.serverStatus().connections`, pool-monitoring events[^3] |
| Query latency rises but ticket `available` looks fine | Ticket **queue depth**, not `available`, is the overload signal | `queues.execution` queued count[^6] |
| "We are too stale to use `<node>` as sync source" | Oplog window collapsed under sustained write rate | Oplog GB/Hour graph vs. configured oplog size[^7] |
| Node stuck in `STARTUP2`/`RECOVERING` for extended period | Fell off the oplog — requires initial resync | `rs.status()`[^7] |
| Writes rolled back after primary rejoins post-failover | Write concern weaker than `majority` at time of step-down | Rollback data directory, write-concern config[^14] |
| Reconnect burst re-saturates cluster right after recovery | Thundering herd — no jitter/backoff on client reconnect | Driver reconnect/backoff config, ticket queue depth spike[^16] |
| Sudden throughput cliff under sustained heavy writes | WiredTiger dirty-cache trigger recruiting app threads into eviction | Cross-load `mongodb-expert/references/mongodb-wiredtiger-internals.md` |

---

## References

[^1]: [What Is Endurance Testing and Why Does It Matter for Software?](https://www.mongodb.com/resources/basics/endurance-testing) — MongoDB, load vs. stress vs. endurance/soak comparison table, duration and metric guidance. verified-as-of: 2026-07-14
[^2]: [How to Build Soak Testing](https://oneuptime.com/blog/post/2026-01-30-soak-testing/view) — soak-testing failure-rate examples (memory leak MB/hour, connection-leak exhaustion timing), environment-parity and common-mistakes guidance. verified-as-of: 2026-07-14
[^3]: [Tuning Your Connection Pool Settings](https://www.mongodb.com/docs/manual/tutorial/connection-pool-performance-tuning/) and [How to Avoid Connection Pool Mismanagement in MongoDB](https://oneuptime.com/blog/post/2026-03-31-mongodb-avoid-connection-pool-mismanagement/view) — `maxPoolSize`/`waitQueueTimeoutMS` behavior and connection-pool-exhaustion symptoms under sustained load. verified-as-of: 2026-07-14
[^4]: [WiredTiger Storage Engine](https://www.mongodb.com/docs/manual/core/wiredtiger/) — MongoDB Manual, cache sizing defaults, cache is not partitioned by database/collection/read-vs-write. verified-as-of: 2026-07-14
[^5]: [MongoDB 7.0's Dynamic WiredTiger Tickets](https://www.mydbops.com/blog/mongodb-7-wiredtiger-tickets) — dynamic ticket algorithm vs. static `wiredTigerConcurrentRead/WriteTransactions`, 128-ticket ceiling. verified-as-of: 2026-07-14
[^6]: [WiredTiger Storage Engine — Transaction (Read and Write) Concurrency](https://www.mongodb.com/docs/manual/core/wiredtiger/#transaction--read-and-write--concurrency) — `queues.execution`, low `available` does not by itself indicate overload; queued count is the overload signal. verified-as-of: 2026-07-14
[^7]: [Fix Oplog Issues — Atlas alert resolutions](https://www.mongodb.com/docs/atlas/reference/alert-resolutions/replication-oplog/) — oplog window alert conditions, common triggers, "too stale to use as sync source," STARTUP2/RECOVERING, w:majority mitigation. verified-as-of: 2026-07-14
[^8]: [Why does my MongoDB replica keep falling behind?](https://stackoverflow.com/questions/11424828/why-does-my-mongodb-replica-keep-falling-behind) — replication lag under sustained heavy workload, missing-index impact on secondary apply. verified-as-of: 2026-07-14
[^9]: [How to Use Stress Testing Software](https://www.mongodb.com/resources/basics/stress-testing) — MongoDB, stress-vs-load-vs-performance-testing distinction, incremental escalation methodology, recovery-behavior metric. verified-as-of: 2026-07-14
[^10]: [Chaos Engineering in the Wild: Findings from GitHub](https://arxiv.org/html/2505.13654v1) — Toxiproxy and Chaos Mesh usage-growth findings across public repos. verified-as-of: 2026-07-14
[^11]: [Performance tuning MongoDB with Chaos Engineering](https://www.gremlin.com/blog/performance-tuning-mongodb-with-chaos-engineering) — Gremlin, documented MongoDB attack workflow (profiler, baseline, memory attack, measured latency impact), MongoDB-relevant attack types. verified-as-of: 2026-07-14
[^12]: [Test Primary Failover — Atlas](https://www.mongodb.com/docs/atlas/tutorial/test-resilience/test-primary-failover/) — required access, prerequisites (health, lag, disk, oplog headroom), failover process, retryable writes, tier/access restrictions. verified-as-of: 2026-07-14
[^13]: [Planning for Chaos with MongoDB Atlas: Using the "Test Failover" Button](https://medium.com/mongodb/planning-for-chaos-with-mongodb-atlas-using-the-test-failover-button-be386c7af479) — MongoDB, chaos-engineering framing of Test Failover, chaos checklist (disk space, connections, IOPS, network), dedicated-cluster requirement. verified-as-of: 2026-07-14
[^14]: [How to Handle Split-Brain Scenarios in MongoDB Replica Sets](https://oneuptime.com/blog/post/2026-03-31-mongodb-split-brain-replica-sets/view) — w:majority split-brain defense mechanism, rollback behavior for weaker write concerns during partition-induced step-down. verified-as-of: 2026-07-14
[^15]: [Simulate File I/O Faults — Chaos Mesh](https://chaos-mesh.org/docs/simulate-io-chaos-on-kubernetes/) and [Chaos Mesh basic features](https://chaos-mesh.org/docs/basic-features/) — PodChaos/NetworkChaos/IOChaos/StressChaos fault types, Kubernetes CRD model. verified-as-of: 2026-07-14
[^16]: [GitHub — Shopify/toxiproxy](https://github.com/Shopify/toxiproxy) — TCP proxy for simulating network conditions, MongoDB replica-set proxying pattern for partition simulation, driver-reconnect issue context. verified-as-of: 2026-07-14
