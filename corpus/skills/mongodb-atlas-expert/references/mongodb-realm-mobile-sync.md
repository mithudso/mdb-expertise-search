<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-atlas-expert` hub.** Formerly the standalone `mongodb-realm-mobile-sync` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-realm-mobile-sync
category: mongodb
version: "1.1.0"
updated: "2026-05-29"
tags: [mongodb, realm, atlas, device-sync, mobile, ios, android, flexible-sync, kotlin, swift, flutter, react-native, offline-first]
description: >
  Expert reference for MongoDB Realm and Atlas Device Sync — HISTORICAL context
  for existing deployments. Atlas Device Sync reached end-of-life September 30, 2025.
  TRIGGER: questions about existing Realm SDK deployments, Flexible Sync vs
  Partition-Based Sync, offline-first mobile architecture, CRDT conflict resolution,
  client reset strategies, Realm object model (Swift/Kotlin/Flutter/React Native),
  or migrating away from Realm Sync. Also triggers on: "Realm SDK", "Atlas Device
  Sync", "offline-first mobile", "Flexible Sync", "client reset", "sync permissions".
  SKIP: new mobile app development (Device Sync is EOL — recommend alternatives),
  Atlas App Services triggers/functions (use mongodb-atlas-app-services), general
  Atlas cluster configuration (use mongodb-atlas-expert), MongoDB Atlas Device SDK
  questions that are purely about the local Realm database without sync (use
  mongodb-atlas-device-sdk).
whenToUse:
  - "Supporting an existing app that uses Atlas Device Sync before its migration deadline"
  - "Debugging Realm Flexible Sync subscription errors or client reset failures"
  - "Migrating from Partition-Based Sync to Flexible Sync"
  - "Understanding Realm CRDT conflict resolution for offline-first scenarios"
  - "Configuring Realm permissions (roles, apply_when, field-level filtering)"
  - "Choosing a client reset strategy (recoverOrDiscardUnsyncedChanges, discardUnsyncedChanges, manual)"
  - "Diagnosing sync-not-starting issues (expired JWT, App Services paused, WebSocket firewall)"
  - "Compacting Realm files or managing MVCC file growth"
  - "Planning migration from Atlas Device Sync to an alternative sync solution"
whenNotToUse:
  - "Building a new mobile app — Atlas Device Sync is EOL; use a different sync solution"
  - "Atlas App Services Triggers and Functions — use mongodb-atlas-app-services"
  - "General Atlas cluster management — use mongodb-atlas-expert"
  - "Local Realm database usage without sync — use mongodb-atlas-device-sdk"
related_skills:
  - mongodb-atlas-app-services
  - mongodb-atlas-device-sdk
  - mongodb-atlas-expert
  - mongodb-migration-patterns
---

# MongoDB Realm & Atlas Device Sync

Expert knowledge covering the Realm mobile database SDK, Atlas Device Sync, and offline-first mobile architecture patterns across all supported platforms.

> **EOL NOTICE:** Atlas Device Sync and all Device SDKs reached end-of-life on **September 30, 2025** and are no longer supported by MongoDB. Use this skill only when supporting existing deployments during migration. For new mobile apps, choose an alternative sync solution (see Section 12).

---

## 1. Atlas Device Sync Overview

Atlas Device Sync (formerly "Realm Sync") was MongoDB's managed service for bidirectional, real-time synchronization between the on-device Realm database and a MongoDB Atlas cluster. The sync engine ran inside Atlas App Services (formerly Realm Cloud).

**Core model:**
- Each mobile device ran an embedded Realm database (a persistent, file-backed, reactive object store).
- Changes made locally were queued in a change log (the Realm "history").
- On connectivity, the SDK streamed those changes to the Atlas App Services sync server via a WebSocket (the "Sync Protocol").
- The server merged changes into Atlas and fanned the delta out to all other subscribed clients.

**What Realm Sync was NOT:**
- Not a REST API sync layer — it used its own binary protocol, not HTTP polling.
- Not MongoDB Change Streams directly — Atlas App Services bridged between the wire protocol and Atlas internally.
- Did not sync entire collections — only documents matching active query subscriptions were materialized on device.

**Service endpoint:** `realm://<app-id>.mongodb.net` (the `realm://` URI scheme was the SDK-facing address; the transport was a WebSocket over TLS on port 443). The SDK managed reconnection, exponential backoff, and session resumption automatically.

---

## 2. Realm SDK Languages and Platforms

MongoDB maintained official Realm SDKs for six primary language/platform targets:

### Swift (iOS / macOS / tvOS / watchOS)
```swift
import RealmSwift

// Open a local Realm
let localConfig = Realm.Configuration(schemaVersion: 3)
let localRealm = try! Realm(configuration: localConfig)

// Open with Device Sync
let app = App(id: "your-app-id")
let user = try await app.login(credentials: .anonymous)
var syncConfig = user.flexibleSyncConfiguration()
let realm = try await Realm(configuration: syncConfig, downloadBeforeOpen: .always)
```
Swift Realm objects use `@Persisted` property wrappers (since SDK 10.x).

### Kotlin (Android / Kotlin Multiplatform)
```kotlin
val config = SyncConfiguration.Builder(user, setOf(Task::class))
    .initialSubscriptions { realm ->
        add(realm.query<Task>("owner == $0", user.id))
    }
    .build()
val realm = Realm.open(config)
```
Kotlin SDK uses coroutines natively; flows via `asFlow()` are the reactive primitive.

### Flutter (iOS + Android via Dart)
```dart
final config = Configuration.flexibleSync(user, [Task.schema]);
final realm = await Realm.open(config);

// Add a subscription
await realm.subscriptions.update((mutableSubscriptions) {
  mutableSubscriptions.add(realm.all<Task>());
});
```
The Flutter SDK uses Dart's `Stream<RealmResultsChanges>` for live queries.

### React Native (iOS + Android via JavaScript/TypeScript)
```typescript
import Realm, { App, Credentials } from 'realm';

const app = new App({ id: 'your-app-id' });
const user = await app.logIn(Credentials.anonymous());

const realm = await Realm.open({
  schema: [TaskSchema],
  sync: {
    user,
    flexible: true,
    initialSubscriptions: {
      update(subs, realm) {
        subs.add(realm.objects('Task'));
      },
    },
  },
});
```

### .NET (Xamarin, MAUI, Unity, Blazor)
```csharp
var config = new FlexibleSyncConfiguration(user);
var realm = await Realm.GetInstanceAsync(config);

await realm.Subscriptions.UpdateAsync(subscriptions => {
    subscriptions.Add(realm.All<Task>().Where(t => t.OwnerId == user.Id));
});
```

### JavaScript / Node.js (Browser not supported; Node only)
The JavaScript SDK targeted Node.js and Electron. Browsers could not use Realm directly — use the MongoDB Data API or Atlas GraphQL instead for browser clients (both are also now removed; see Section 12).

---

## 3. Flexible Sync — Current Model

Flexible Sync was the **recommended** sync mode as of Atlas App Services 2022+ (replaced Partition-Based Sync).

### How It Works
Clients declared **subscriptions** — named queries written in the Realm Query Language (RQL), a subset of MQL — that defined the set of documents synced to their local Realm. Not all MQL operators were supported; complex aggregation operators and `$where` were unavailable. The sync server evaluated these queries server-side and streamed only matching documents to the device.

```swift
// Swift: adding subscriptions
let subscriptions = realm.subscriptions
try await subscriptions.update {
    subscriptions.append(
        QuerySubscription<Task>(name: "my-tasks") {
            $0.owner == user.id && $0.isComplete == false
        }
    )
}
```

### Key properties of Flexible Sync:
- **Multiple subscriptions** per realm, each independently named and queryable.
- **Dynamic** — subscriptions could be added, removed, or updated at runtime without reopening the Realm.
- **Field filtering** — the sync server applied the RQL predicate; only fields present in the document (not the client schema) were evaluated.
- **Required queryable fields** — fields used in subscription queries MUST be listed as queryable in the App Services UI or CLI config. Indexing them on Atlas is strongly recommended.

### Queryable Fields Configuration (App Services)
```json
{
  "flexible_sync": {
    "state": "enabled",
    "database_name": "my-db",
    "queryable_fields_names": ["owner_id", "priority", "status"]
  }
}
```

### Subscription Lifecycle States
| State | Meaning |
|---|---|
| `Pending` | Query sent to server, waiting for acknowledgement |
| `Complete` | Server has sent all matching documents |
| `Invalidated` | Query is no longer valid (e.g. schema mismatch) |
| `Error` | Unrecoverable subscription error |

---

## 4. Partition-Based Sync (Legacy)

Partition-Based Sync (PBS) was the original model. Every document had a `_partitionKey` field; a client opened a Realm scoped to one partition value (e.g. `user.id` or `project-42`). The entire partition was synced as a unit.

**Why it was deprecated:**
- Could not mix documents from different partitions in one Realm.
- Required all documents to carry a partition key, complicating schema design.
- Could not filter within a partition; granularity was coarse.

**Migration to Flexible Sync:**
1. In App Services, navigate to the Sync configuration and select "Migrate to Flexible Sync."
2. The wizard creates an initial subscription equivalent to the old partition queries.
3. Remove `_partitionKey` from app code after migration; replace with subscription queries.
4. Old SDKs (< 10.22 for Swift, < 1.6 for Kotlin) must be upgraded before migration.

---

## 5. Conflict Resolution

Realm uses a **custom CRDT (Conflict-free Replicated Data Type)** engine that provides field-level merge semantics rather than whole-document last-writer-wins. This is distinct from Operational Transformation (OT).

### Default Resolution Rules

| Operation type | Resolution |
|---|---|
| Field set | Last-write-wins per field (by logical clock, not wall clock) |
| List append | All appends preserved; ordering by lamport timestamp |
| List delete | Delete wins over concurrent insert at the same index |
| Object creation | Both survive if IDs differ; merge if same primary key |
| Object deletion | Delete wins over concurrent update to the same object |

### Custom Resolution Patterns

The SDK did not expose a "conflict hook" — resolution was automatic. However, custom semantics could be achieved with data model choices:

**Counter pattern (CRDT-safe increment):**
```swift
// Do NOT do this — not CRDT-safe:
task.counter += 1

// DO this — use a Realm Counter type (Swift SDK 10.46+):
try realm.write {
    task.counter.increment(by: 1)
}
```

**Append-only log pattern:** Model state changes as list entries rather than mutable fields. Replay the log client-side to derive current state.

**Timestamp arbitration:** Store a `lastModifiedAt` Date field alongside a `lastModifiedBy` string. After sync, resolve conflicts in UI layer by presenting the most-recent-winner.

---

## 6. Realm Object Model

### Schema Definition

All Realm objects extended a base class/interface. Required: a primary key (must be `_id` for synced Realms to align with MongoDB `_id`).

**Swift:**
```swift
class Task: Object {
    @Persisted(primaryKey: true) var _id: ObjectId
    @Persisted var name: String = ""
    @Persisted var owner: String = ""
    @Persisted var isComplete: Bool = false
    @Persisted var tags: List<String>
    @Persisted var subtasks: List<Subtask>
    @Persisted var metadata: TaskMetadata?  // embedded object — use a concrete EmbeddedObject subclass
}
```

**Kotlin:**
```kotlin
class Task : RealmObject {
    @PrimaryKey
    var _id: ObjectId = ObjectId()
    var name: String = ""
    var owner: String = ""
    var isComplete: Boolean = false
    var tags: RealmList<String> = realmListOf()
    var subtasks: RealmList<Subtask> = realmListOf()
}
```

### Embedded Objects
Embedded objects are owned by exactly one parent and have no independent lifecycle. They map to BSON subdocuments in Atlas.

```swift
class Subtask: EmbeddedObject {
    @Persisted var title: String = ""
    @Persisted var done: Bool = false
}
```

Embedded objects cannot be synced independently — they sync as part of their parent document.

### Links (References)
Links are to-one or to-many forward relationships to top-level Realm objects (stored as `ObjectId` references in Atlas). `LinkingObjects` is the backlink type — it tracks which objects point to the current object.

```swift
// Forward link and backlink on a task variant
class TaskWithRelations: Object {
    @Persisted var assignee: User?                                              // forward to-one link
    @Persisted(originProperty: "tasks") var project: LinkingObjects<Project>   // backlink
}
```

Unlike embedded objects, linked objects were synced independently — the link target must also be in a matching subscription for both ends to materialize on device.

### Supported Field Types
- Primitive: `String`, `Int`, `Double`, `Float`, `Bool`, `Date`, `Data`, `ObjectId`, `UUID`, `Decimal128`
- Collections: `List<T>`, `Map<String, T>`, `MutableSet<T>`
- Special: `Counter` (CRDT-safe), `AnyRealmValue` (mixed type)
- Nullable: all types support optional/nullable variants

---

## 7. Sync Configuration

### Initial Sync
On first open, the SDK downloaded all documents matching current subscriptions before resolving the open call (when `downloadBeforeOpen: .always` / `waitForInitialRemoteData`). For large datasets this could block app startup.

**Pattern: download in background, open immediately from local Realm:**
```swift
// Open with cached data immediately, sync in background
var syncConfig = user.flexibleSyncConfiguration()
syncConfig.objectTypes = [Task.self]
// Do NOT set downloadBeforeOpen — local Realm opens instantly
let realm = try! Realm(configuration: syncConfig)
// UI renders, sync catches up silently
```

### Incremental Sync
After initial sync, the SDK only transferred deltas. The sync server tracked a client's "progress token" and replayed only new operations since the last session.

### Network Resilience
- The SDK maintained an in-memory change queue and persisted it to the Realm file.
- On disconnect, all writes continued locally. On reconnect, the queue was replayed.
- Manual conflict resolution was not required for the standard object model.
- `syncSession.pause()` / `syncSession.resume()` allowed explicit offline mode toggling.

### Sync Session Monitoring
```swift
let token = realm.syncSession?.observe(\.state, options: .initial) { session, change in
    switch session.state {
    case .active: print("syncing")
    case .inactive: print("paused")
    case .invalid: print("session ended")
    }
}
```

### Compaction
Realm files grew via MVCC (multi-version concurrency control). Compact on open when the file was large and mostly reclaimable:
```swift
syncConfig.shouldCompactOnLaunch = { totalBytes, usedBytes in
    // Compact if file > 50 MB and less than 50% of bytes are live data
    totalBytes > 50 * 1_048_576 && Double(usedBytes) / Double(totalBytes) < 0.5
}
```

---

## 8. Permissions Model

### Role-Based Access Control (App Services UI)
Permissions were defined in App Services as JSON rules applied per collection. They controlled which users could read or write which documents.

```json
{
  "roles": [
    {
      "name": "owner",
      "apply_when": { "owner_id": "%%user.id" },
      "document_filters": {
        "read": true,
        "write": true
      }
    },
    {
      "name": "reader",
      "apply_when": {},
      "document_filters": {
        "read": { "isPublic": true },
        "write": false
      }
    }
  ]
}
```

### Document-Level Permissions
The `apply_when` condition on a role used `%%user.id`, `%%user.data.*`, and comparison operators. A role was active if its `apply_when` evaluated to true for the current user.

### Field-Level Filtering
Roles could restrict specific fields from being read or written:
```json
{
  "fields": {
    "salary": { "read": false, "write": false },
    "name":   { "read": true,  "write": { "owner_id": "%%user.id" } }
  }
}
```

### Sync vs. Non-Sync Permissions
Sync permissions were evaluated at the sync protocol layer — documents that failed read permissions were simply not synced to the client. Write attempts that failed permissions were rejected by the server and rolled back on the client.

### Default Roles
Lock down the default role to `{ read: false, write: false }` and grant explicit named roles. This is the secure-by-default pattern.

---

## 9. Offline-First Patterns

### Local Persistence by Default
All Realm writes were immediately durable on device (journaled to the `.realm` file). The app never needed to wait for network confirmation.

### Optimistic UI
```swift
// Write immediately, sync in background
try realm.write {
    realm.add(newTask)
}
// UI updates reactively via live query — no callback needed
```

Live queries (`Results<T>`) automatically updated when the underlying data changed, whether from local writes or incoming sync. Bind directly to `Results` in the UI layer.

### Sync Trigger Events
```swift
// React to sync completing for a subscription
await realm.subscriptions.update { subs in
    subs.add(realm.objects(Task.self))
}
// .update suspends until server confirms subscription is Complete
```

### Handling Sync Errors in UI
```swift
let errorHandlingConfig = user.flexibleSyncConfiguration { session, error in
    // Called on unrecoverable sync errors
    if let syncError = error as? SyncError {
        switch syncError.code {
        case .clientResetRequired:
            // Must discard local Realm and re-download
            handleClientReset()
        default:
            print("Sync error: \(error)")
        }
    }
}
```

### Client Reset Strategy
A client reset was required when the server's history was truncated beyond the client's last known position (e.g., after disabling/re-enabling sync in App Services, or after exceeding the configurable history window — 60 days by default).

| Strategy | Behavior |
|---|---|
| `recoverOrDiscardUnsyncedChanges` | Attempt to recover; discard if not possible (recommended) |
| `recoverUnsyncedChanges` | Recover only; error if not possible |
| `discardUnsyncedChanges` | Always discard local unsynced data |
| `manual` | App code handles the reset (advanced) |

---

## 10. App Services Context

MongoDB App Services (formerly MongoDB Realm Cloud) hosted Device Sync, along with:

- **Realm Functions** — serverless JavaScript (Node 18+) triggered by sync events, HTTP endpoints, or schedules.
- **Realm Triggers** — database triggers (on Atlas change streams), auth triggers, scheduled triggers.
- **GraphQL API** — auto-generated from Atlas schema (now removed, Sept 30, 2025).
- **Data API** — REST-over-HTTPS for non-Realm clients (now removed, Sept 30, 2025).

### Status as of 2025
MongoDB shut down the hosted App Services platform on **September 30, 2025**. Sync itself, Triggers, and auth providers were removed along with the Data API and GraphQL.

See `mongodb-atlas-app-services` skill for the full EOL migration table covering all deprecated App Services features and recommended replacements.

---

## 11. Common Pitfalls

### Schema Mismatch
If the client schema and Atlas collection schema diverged, sync errored with `ErrorSchemaMismatch`. Causes:
- Adding a required (non-optional) field to the client schema before migrating existing Atlas documents.
- Using a field name that conflicted with a system field (e.g., `id` vs `_id`).
- **Fix:** Always add fields as optional/nullable first; backfill Atlas documents; then make non-optional if needed.

### Large Initial Sync
If subscriptions were too broad (e.g., `realm.all<Document>()`), the initial download could be hundreds of MB.
- **Fix:** Use narrow subscriptions; paginate with time-bounded queries; prefer background sync with cached local Realm.

### Missing Indexes on Queryable Fields
Queryable fields used in subscriptions were evaluated server-side against Atlas. Without indexes, subscription evaluation scanned the full collection.
- **Fix:** For every field in `queryable_fields_names`, create a MongoDB index on the Atlas collection.
```javascript
db.tasks.createIndex({ owner_id: 1, priority: -1 });
```

### Writes Outside a Transaction
All Realm mutations must occur within a write transaction.
```swift
// Wrong — crashes
task.name = "Updated"

// Correct
try realm.write { task.name = "Updated" }
```

### Storing Non-Persisted State in Realm Objects
Computed or transient properties must be marked `@Persisted(ignored: true)` (Swift) or `@Ignore` (Kotlin) or they will be included in the schema and synced.

### Realm File Path Conflicts
In multi-user apps, each user must open a separate Realm file (typically keyed by `user.id`). Sharing a Realm file between users can cause sync session conflicts and data leakage.
```swift
var syncConfig = user.flexibleSyncConfiguration()
// The default path already includes user.id — don't override it with a shared path
```

### Thread Safety
Realm objects are **thread-confined** in Swift and Kotlin. Do not pass `Object` instances across threads. Use the primary key to re-fetch on the target thread, or use `ThreadSafeReference`.
```swift
let ref = ThreadSafeReference(to: task)
DispatchQueue.global().async {
    let realm = try! Realm()
    let task = realm.resolve(ref)!
    // safe to use task here
}
```

### Subscription Naming Collisions
If two subscriptions share the same name, the second `add()` call replaces the first. Use distinct names or omit the name (unnamed subscriptions replace the previous unnamed subscription of the same query type).

### Sync Not Starting After Configuration
Common causes:
- App Services Sync was paused in the Atlas UI (check "Pause Sync" toggle).
- The device clock was skewed > 5 minutes (JWT validation fails silently).
- The user's auth token was expired and `refreshToken` had not been called.
- Firewall blocking WebSocket on port 443 (the sync protocol requires WebSocket upgrade on HTTPS).

---

## 12. Migration Options (EOL — September 30, 2025)

Since Atlas Device Sync is end-of-life, new projects must use alternative sync solutions:

| Option | Best fit |
|---|---|
| Custom sync layer via MongoDB drivers + WebSocket/SSE | Teams that want full control and are already using MongoDB Atlas |
| Couchbase Lite + Couchbase Sync Gateway | Enterprises needing a hosted mobile sync platform |
| PouchDB + CouchDB | JavaScript/web-centric offline-first apps |
| Realm database standalone (local only, no sync) | Apps that don't need cloud sync — local persistence only |
| PowerSync | Open-source Postgres/MongoDB → SQLite sync; active development post-Realm EOL |

See `mongodb-atlas-app-services` for the full EOL migration table covering all deprecated App Services features with recommended replacements. The `mongodb-atlas-app-services` skill also covers the App Services authentication providers and Rules/Permissions engine relevant to the Flexible Sync permissions model documented here.
