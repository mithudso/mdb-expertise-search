---
name: mongodb-atlas-managed-upgrades
category: mongodb
version: "1.0.0"
updated: "2026-07-14"
description: >
  Atlas-managed MongoDB major-version upgrade mechanics and gotchas — auto-upgrade
  vs pinned-major-version cadence, maintenance windows/sequence/protected hours,
  End-of-Life forced upgrades, the 2-major-version FCV upgrade ceiling, and the
  Atlas-specific 7.0->8.0 bump risks: write-blocking on 8.0+ dedicated clusters,
  the new defaultMaxTimeMS cluster parameter surfacing as app-visible query
  timeouts, Atlas Search/Vector Search index auto-rebuild disk-space alerts,
  Search Node version compatibility, App Services/Triggers end-of-life
  overlapping upgrade timing, and known SERVER-ticket regressions
  (SERVER-99290 time-series FCV blocker).
  TRIGGER: "does Atlas auto-upgrade my cluster"; "can I opt out of automatic
  version upgrades"; Atlas maintenance window/sequence/protected hours; Atlas
  major-version-change limitations (2-version FCV ceiling); Atlas 7.0->8.0
  upgrade risk; write-blocking after upgrading to 8.0; Atlas Search index
  rebuild disk space alert; App Services/Triggers deprecation colliding with an
  upgrade; Atlas vs self-managed upgrade risk-profile comparison.
  SKIP: the self-managed FCV/rolling-upgrade/sharded-cluster procedure, driver
  compatibility matrix, PSA-stepdown/oplog-window/index-build failure modes —
  use mongodb-operations-expert (references/mongodb-upgrade-paths.md); live
  diagnosis of a slow query or high CPU during/after an upgrade — use
  atlas-diagnostics-expert; Atlas Search/Vector Search index *design* and query
  syntax — use references/mongodb-atlas-search.md and
  references/mongodb-atlas-vector-search.md.
tags:
  - mongodb
  - atlas
  - upgrade
  - auto-upgrade
  - maintenance-window
  - fcv
  - atlas-search
  - vector-search
  - app-services
whenToUse:
  - "Explaining how and when Atlas auto-upgrades a cluster's major version"
  - "Advising a customer on maintenance windows, sequence waves, or protected hours before a version bump"
  - "Diagnosing why a customer can't upgrade straight from 7.0 to a version beyond 8.0"
  - "Assessing write-blocking risk right after an Atlas 8.0 upgrade"
  - "Explaining an app-visible query-timeout regression that started after an Atlas 8.0 upgrade"
  - "Advising on Atlas Search/Vector Search index rebuild disk-space alerts during a version bump"
  - "Untangling App Services/Triggers deprecation timing from a MongoDB version upgrade"
  - "Comparing Atlas-managed upgrade risk to the self-managed FCV/rolling procedure"
whenNotToUse:
  - "Self-managed FCV pin/unpin lifecycle, rolling replica-set or sharded-cluster upgrade order, driver compatibility matrix — use mongodb-operations-expert references/mongodb-upgrade-paths.md"
  - "Live diagnosis of a specific slow query, high CPU, or cache-pressure symptom — use atlas-diagnostics-expert"
  - "Atlas Search or Vector Search index design, analyzers, or query syntax — use references/mongodb-atlas-search.md / references/mongodb-atlas-vector-search.md"
  - "Atlas Search Nodes provisioning/sizing (non-upgrade) — use references/mongodb-atlas-search-nodes.md"
related_skills:
  - mongodb-atlas-expert
  - mongodb-operations-expert
  - atlas-diagnostics-expert
  - mongodb-atlas-app-services
  - mongodb-atlas-search-nodes
---

<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-atlas-expert` hub.** For the
> self-managed FCV/rolling-upgrade procedure this file deliberately does not
> repeat, see `mongodb-operations-expert/references/mongodb-upgrade-paths.md`.

# Atlas-Managed MongoDB Upgrades (7.0 → 8.0 and beyond)

This reference covers the **Atlas-platform angle** of a major-version upgrade:
how Atlas decides *when* a cluster moves to a new major version, what a
customer can and cannot control, and the Atlas-specific gotchas that show up
in a 7.0 → 8.0 bump that have **no self-managed equivalent** (write-blocking,
`defaultMaxTimeMS`, Search index auto-rebuild, Search Node compatibility,
App Services end-of-life timing). It intentionally does **not** repeat FCV
mechanics, rolling-upgrade order, or the driver-compatibility matrix — those
live in `mongodb-operations-expert/references/mongodb-upgrade-paths.md` and
apply identically underneath Atlas.

## 1. How Atlas triggers a major-version upgrade

Atlas gives **Dedicated (M10+)** clusters two release-cadence models; **Free**
and **Flex** clusters get neither choice — Atlas silently keeps them on the
current major version (MongoDB 8.0 as of this writing) and auto-upgrades them
on its own schedule.[^1]

| Cadence | What it means | Who can pick it |
| --- | --- | --- |
| **Major Version** (pinned) | Cluster stays on the selected major version (e.g., `7.0`) indefinitely; only patch releases apply automatically. Customer explicitly triggers the next major-version bump. | M10+ only |
| **Latest Version With Auto Upgrades** | Atlas advances the cluster through **major and minor** versions automatically as they roll out, on Atlas's own timetable. Once opted in, the customer cannot select a specific major/minor/patch — only a return window right after a new major GAs lets them switch back to pinned. | M10+ only |
| *(no choice)* | Free and Flex clusters always track "the current major version" and Atlas auto-upgrades them; there is no per-cluster opt-out. | M0 / Flex |

Two forcing functions push even a **pinned** M10+ cluster onto a new major
version without a customer-initiated click:

1. **End of Life (EOL).** Atlas emails project owners **at least six months**
   before a MongoDB major version reaches EOL. If the customer has not
   upgraded (or received an approved extension) by the cut-off date, **Atlas
   upgrades the cluster to the next major version automatically** — this is
   an Atlas-initiated upgrade, not customer-initiated, and it is the single
   most common way a 7.0 cluster ends up on 8.0 without an explicit change
   ticket.[^1]
2. **Live Migration / Mongosync restriction.** Live Migration and Mongosync do
   not support clusters on **Latest Version With Auto Upgrades** (minor
   versions) — only a major-version-pinned cluster, or a self-guided
   migration tool, works there.[^1] This affects migration planning timing,
   not the upgrade trigger itself, but TAMs should flag it before recommending
   auto-upgrade to a customer who still has cluster-to-cluster migrations
   planned.

## 2. Maintenance windows, protected hours, and sequence waves

Once Atlas decides a cluster needs maintenance (a version bump, an OS patch,
or a routine update), the **when** is governed by per-project settings —
available only for **Dedicated (M10+)** clusters; Free/Flex maintenance
timing is entirely Atlas-controlled and not configurable.[^2]

- **Maintenance Window** — the day/hour Atlas starts weekly maintenance that
  requires a replica-set election.
- **Protected Hours** — up to an 18-hour daily window where Atlas defers
  *standard* updates (not maintenance requiring a restart); does not block
  **urgent** maintenance (e.g., zero-day security patches), which Atlas
  applies regardless of window or protected hours.[^2]
- **Maintenance Sequence** (private preview) — assigns projects to waves
  (Wave 1 → Last Wave) so an organization can stagger rollout across
  dev/staging/production, with **at least a 48-hour gap** between waves.[^2]
- **Auto-defer** — enabling "automatically defer maintenance for one week"
  effectively halves maintenance frequency to every two weeks; **mutually
  exclusive with Maintenance Sequence** on the same organization.[^2]
- **Manual defer** — a customer can defer a single scheduled maintenance
  event **up to twice**; Atlas gives 48–72 hours' advance notice via a UI
  banner and email to Project Owners before required maintenance.[^2]
- **Trigger immediately** — `atlas maintenanceWindows update --startASAP` (CLI)
  or `"startASAP": true` (Admin API `PATCH .../maintenanceWindow`) starts
  scheduled maintenance on demand rather than waiting for the window.[^2]

**What customers cannot control:** the maintenance window/sequence apparatus
governs *when* Atlas performs work Atlas has already decided to do (patch
upgrades, OS updates, EOL-forced major bumps) — it does not let a customer
prevent an EOL-forced major-version upgrade altogether, only shift its timing
within the deferral limits above. There is **no setting that disables
automatic version updates outright**; MongoDB support has stated directly
that fully disabling them is not offered because they are considered core to
keeping deployments on a secure, stable release.[^3]

## 3. The 2-major-version FCV upgrade ceiling

Atlas enforces a hard limit independent of the self-managed sequential-hop
rule: **you cannot select a target version more than 2 major versions above
the cluster's pinned Feature Compatibility Version (FCV)** — the gate,
separate from the binary version, that controls which on-disk and protocol
features are active (full FCV lifecycle mechanics:
`mongodb-operations-expert/references/mongodb-upgrade-paths.md` §2).
If a cluster's FCV is pinned at `6.0`, the Atlas UI only allows upgrading to
`7.0` — not `8.0` or later — until the FCV itself advances.[^4] This is easy to miss when a customer pinned FCV during a prior
upgrade's burn-in window and then tries to jump straight to the newest major
version months later; the fix is to unpin/advance FCV first, then re-attempt
the version-change dialog.

Other Atlas-specific limitations on the version-change action itself:[^4]

- One major version at a time — same "no skipping" rule as self-managed.
- No downgrade after a major-version upgrade unless FCV was pinned
  beforehand (this mirrors, and is the Atlas enforcement point for, the
  self-managed FCV pin/downgrade-window behavior already documented in
  `mongodb-operations-expert/references/mongodb-upgrade-paths.md`).
- Live Migration requires source and destination FCVs to match major
  versions — another reason a customer mid-migration should not casually
  advance FCV on either side.
- The Atlas-recommended workflow is staging-cluster-first: clone production
  data into a staging cluster, upgrade the staging cluster, run application
  and **failover** tests against it, upgrade drivers, *then* upgrade
  production — with a High-Priority support ticket path if the staging
  upgrade surfaces version-specific issues.[^4]

## 4. Atlas-specific 7.0 → 8.0 gotchas

These are platform behaviors that do not exist for a self-managed 7.0 → 8.0
upgrade and have generated real customer confusion.

### 4.1 Write-blocking on dedicated 8.0+ clusters

Starting with **MongoDB 8.0 on dedicated (M10+) Atlas clusters only**, Atlas
introduces primary-node **write-blocking** as part of Intelligent Workload
Management: if the primary's free disk space drops below a size-dependent
threshold (600 MB free on <20 GB disks; 4% free on <1.25 TB disks; 50 GB free
on ≥1.25 TB disks), Atlas **blocks writes to the primary** — reads continue —
until free space recovers 50% above the blocking threshold.[^5] This did not
exist pre-8.0. A cluster that upgrades to 8.0 while already running close to
its storage ceiling can start seeing `MongoServerError: User writes blocked,
reason: DiskUseThresholdExceeded` immediately post-upgrade with **no schema or
query change** — the fix is enabling storage auto-scaling or increasing disk
size *before* the upgrade, not after the alert fires (once blocked, Atlas also
refuses index/collection drops that would otherwise free space).[^5] Free and
Flex clusters are exempt from write-blocking entirely.[^5]

### 4.2 `defaultMaxTimeMS` — a new source of app-visible query timeouts

MongoDB 8.0 introduces the `defaultMaxTimeMS` cluster parameter, settable via
`db.adminCommand({ setClusterParameter: { defaultMaxTimeMS: { readOperations:
<ms> } } })`, applying a global timeout to `find`, `count`, `distinct`,
`dbHash`, and non-`$merge`/`$out` `aggregate` operations unless an operation
specifies its own `maxTimeMS()`.[^6] The parameter **defaults to `0` (no
timeout)** at the driver/cluster-parameter level — so a bare 8.0 upgrade does
not itself introduce query timeouts. The Atlas-specific gotcha is at the
**tooling layer**: the Atlas Data Explorer query view applies its **own**
default `MAX TIME MS` of 60 seconds, independent of and pre-dating the
`defaultMaxTimeMS` cluster parameter.[^12] Separately, if a TAM or customer
explicitly configures `defaultMaxTimeMS` during an 8.0 upgrade rollout — a
step some upgrade runbooks now recommend for query-governance reasons — any
existing long-running analytics or reporting query that previously ran to
completion can start failing with `MaxTimeMSExpired` the moment the parameter
is set, unless that query already specifies its own longer `maxTimeMS()`.[^6]
Treat `defaultMaxTimeMS` as an **opt-in governance feature to configure
deliberately after the upgrade**, not a build-in behavior change from the
upgrade itself — but audit long-running analytics-node and reporting queries
before anyone on the account turns it on.

### 4.3 Atlas Search / Vector Search across the version bump

- **Search index auto-rebuild disk pressure.** When Atlas upgrades a Search
  or Vector Search index to enable new features (which can accompany a
  server major-version bump), it builds the **new** index version alongside
  the **existing** one and only deletes the old copy once the rebuild
  completes — meaning the cluster must have disk headroom for **both**
  copies simultaneously. Insufficient free space triggers the documented
  alert *"Insufficient disk space to support rebuilding search indexes"*.[^7]
  For a 7.0 → 8.0 upgrade on a cluster already tight on storage, this
  compounds with the write-blocking risk in §4.1 — budget disk headroom for
  both mechanisms before upgrading, not just one.
- **Vector Search minimum-version floor.** `$vectorSearch` requires MongoDB
  **6.0.11 or 7.0.2+** for ANN search, and **6.0.16 / 7.0.10 / 7.3.2+** for
  exact nearest-neighbor (ENN) search.[^8] A cluster already on a
  Vector-Search-eligible 7.0.x patch keeps working through the 8.0 bump; the
  floor only matters for customers upgrading from pre-7.0.2 patches directly
  or evaluating Vector Search readiness before committing to the version
  plan.
- **Search Nodes** are provisioned independently of database compute and
  have their own upgrade cadence; treat Search Node version compatibility
  during a database major-version bump as a question for
  `references/mongodb-atlas-search-nodes.md` rather than assuming Search
  Node and `mongod`/`mongos` versions always move in lockstep.

### 4.4 App Services / Triggers — a parallel deprecation, not an upgrade dependency

**Atlas App Services has reached end-of-life and is no longer actively
supported.**[^9] This is frequently confused with the 7.0 → 8.0 server
upgrade because both land on a customer's roadmap around the same time, but
they are **independent timelines** — App Services deprecation is a platform
sunset, not a version-compatibility gate:

- **Database Triggers are explicitly *not* deprecated** and remain available
  directly in the Atlas UI (moved out of the legacy App Services docs into
  mainline Atlas docs) — a customer using Database Triggers does not need to
  migrate off them because of a server version bump.[^9]
- **Deprecated alongside App Services:** Data API and HTTPS Endpoints, Device
  Sync, Device SDKs, App Services authentication/user management
  (Authentication Triggers stop firing once the SDKs are removed), and the
  App Services wire protocol.[^9] Functions remain available **only in the
  context of Triggers** — any Function invoked directly through a Device SDK
  needs a different integration path.
- **TAM guidance:** when a customer raises "will my Triggers break on 8.0",
  the accurate answer is that Database Triggers are unaffected by the server
  version bump; the real, unrelated action item is whether they depend on
  any of the deprecated App Services surfaces above, on a timeline set by
  MongoDB's App Services sunset — not by their upgrade schedule.

### 4.5 Known regression: time-series FCV blocker (SERVER-99290)

**SERVER-99290** documents invalid time-series buckets collections that can
**prevent completion of the FCV 8.0 upgrade** — a customer with malformed
historical time-series bucket data can have the binary upgrade succeed but
the `setFeatureCompatibilityVersion: "8.0"` step fail.[^10] This is a
data-integrity precondition, not an Atlas-vs-self-managed distinction, but it
surfaces identically on Atlas: if a staging-cluster FCV advance fails
unexpectedly during an 8.0 rollout, check for time-series collections created
before the bug fix landed before assuming the failure is capacity- or
network-related.

Separately, MongoDB 8.0 before **8.0.5** has a known high-CPU regression under
TLS with a specific `openssl` package version on the host OS.[^11] On
self-managed deployments this requires the operator to track OS package
versions manually; **on Atlas, MongoDB controls and patches the underlying
host OS**, so this specific class of OS-package-interaction regression is one
Atlas customers structurally do not have to track themselves — call this out
explicitly when a customer asks "how do you know your infra doesn't hit
this" as a genuine Atlas risk-reduction point, not a talking point.

## 5. Risk-profile comparison: Atlas-managed vs self-managed

| Dimension | Self-managed | Atlas-managed |
| --- | --- | --- |
| Who decides *when* the major-version bump happens | Always the operator, on their own schedule | Operator (major-version cadence), **or Atlas** (EOL forced upgrade, or opted into Latest-Version-With-Auto-Upgrades) |
| Rolling-upgrade execution (secondaries → primary, sharded-cluster order) | Manual, operator-run runbook | Fully automated by Atlas; operator cannot skip or reorder steps |
| FCV pin/unpin | Operator discipline only, no enforced limit | Same mechanics, but bounded to a **4-week pin window** with **auto-unpin at next maintenance**[^4] — the Atlas "Point of No Return" is time-boxed, not just decision-boxed |
| Host OS patching (kernel/openssl-class regressions) | Operator's responsibility | MongoDB's responsibility — structurally removes a class of self-managed-only failure modes (§4.5) |
| Disk-pressure failure modes during upgrade | Cold WiredTiger cache after rolling upgrade (see mongodb-upgrade-paths.md §8) | Adds **write-blocking** (§4.1) and **Search index dual-copy rebuild** (§4.3) as Atlas-only disk-pressure mechanisms layered on top of the same cache-warming behavior |
| Forced-upgrade exposure | None — the operator always initiates | **EOL forced upgrade** after 6-month notice is a real, Atlas-initiated path customers must plan around even on a "pinned" cadence |
| Ecosystem surfaces that can be mistaken for version-upgrade risk | N/A | App Services/Triggers deprecation (§4.4) — a parallel platform sunset, not a version gate |

**Net TAM guidance:** Atlas removes most of the *mechanical* upgrade risk
(rolling order, host-OS patching, cache pre-warming automation) but adds a
distinct set of **platform-governance risks** — forced EOL upgrades on a
timeline the customer doesn't fully control, and new 8.0-era safety
mechanisms (write-blocking, Search index rebuild disk pressure) that convert
a marginal-storage cluster's *slow-and-known* self-managed disk problem into
a *sudden write outage* if headroom isn't checked before the version bump.
The self-managed procedure in `mongodb-upgrade-paths.md` remains the correct
reference for FCV semantics and driver compatibility — this file is the
Atlas-only risk layer on top of it.

---

## Quick reference

| Question | Answer |
| --- | --- |
| Can a customer fully disable Atlas auto-upgrades? | No — MongoDB Support has stated this is not offered[^3] |
| What forces an upgrade even on a pinned major version? | EOL cutoff (6-month notice, then Atlas auto-upgrades)[^1] |
| Max FCV-to-target-version gap Atlas allows | 2 major versions above pinned FCV[^4] |
| New Atlas-only 8.0 disk-pressure mechanism | Write-blocking on dedicated M10+ primaries[^5] |
| New 8.0 query-timeout knob | `defaultMaxTimeMS` cluster parameter (default off)[^6] |
| Search index rebuild alert to watch for | "Insufficient disk space to support rebuilding search indexes"[^7] |
| Vector Search version floor | 6.0.11 / 7.0.2+ (ANN), 6.0.16 / 7.0.10 / 7.3.2+ (ENN)[^8] |
| Are Database Triggers affected by the 8.0 bump? | No — Triggers are not deprecated; App Services EOL is unrelated[^9] |
| Known FCV-8.0-blocking regression | SERVER-99290 (invalid time-series buckets)[^10] |
| Who patches the host OS on Atlas? | MongoDB — removes self-managed-only OS-package regressions[^11] |

---

## References

[^1]: [MongoDB Versions in Atlas — MongoDB Docs](https://www.mongodb.com/docs/atlas/atlas-versions/)
[^2]: [Configure Maintenance Windows, Sequence, and Protected Hours — Atlas Docs](https://www.mongodb.com/docs/atlas/tutorial/cluster-maintenance-window/)
[^3]: [Is there an option to disable automatic version updates? — MongoDB Community Forums](https://www.mongodb.com/community/forums/t/is-there-an-option-to-disable-automatic-version-updates/183992)
[^4]: [Upgrade Major MongoDB Version for a Cluster — Atlas Docs](https://www.mongodb.com/docs/atlas/tutorial/major-version-change/)
[^5]: [Write-Blocking — Atlas Docs](https://www.mongodb.com/docs/atlas/cluster-blocking-writes/)
[^6]: [defaultMaxTimeMS — MongoDB Manual](https://www.mongodb.com/docs/manual/reference/cluster-parameters/defaultmaxtimems/)
[^7]: [Fix MongoDB Search Issues (alert resolutions) — Atlas Docs](https://www.mongodb.com/docs/atlas/reference/alert-resolutions/atlas-search-alerts/)
[^8]: [MongoDB Vector Search Overview — MongoDB Docs](https://www.mongodb.com/docs/atlas/atlas-vector-search/vector-search-overview/)
[^9]: [Service Deprecations — Atlas App Services Docs](https://www.mongodb.com/docs/atlas/app-services/deprecation/)
[^10]: [SERVER-99290 "Invalid timeseries buckets collections prevent completion of FCV 8.0 upgrade" — listed in Release Notes for MongoDB 8.0 (8.0.5 fixed-issues section)](https://www.mongodb.com/docs/manual/release-notes/8.0/)
[^11]: [Release Notes for MongoDB 8.0 — MongoDB Docs](https://www.mongodb.com/docs/manual/release-notes/8.0/)
[^12]: [Adjust Maximum Time for Query Operations — Atlas Docs](https://www.mongodb.com/docs/atlas/atlas-ui/query/maxtimems/)

**verified-as-of: 2026-07-14**
