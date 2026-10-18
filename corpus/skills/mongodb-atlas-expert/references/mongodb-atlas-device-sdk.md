<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-atlas-expert` hub.** Formerly the standalone `mongodb-atlas-device-sdk` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-atlas-device-sdk
title: "MongoDB Atlas Device SDK & Edge Server — Mobile and Edge Development Reference"
description: "Comprehensive reference for the Atlas Device SDK (successor to Realm SDK): SDK language matrix, Realm object model, Flexible Sync subscriptions, Atlas Edge Server deployment, migration from legacy Realm SDK, authentication providers, conflict resolution strategies, performance optimization, Flutter/Dart specifics, and offline-first architecture patterns. All features subject to the September 2024 deprecation of Atlas Device Sync — includes EOL status and recommended migration paths."
category: mongodb
version: 1
whenToUse:
  - "User asks about Realm SDK, Atlas Device SDK, or mobile database for iOS/Android/Flutter/React Native"
  - "User needs to implement offline-first mobile app architecture with MongoDB"
  - "User asks about Atlas Device Sync or Flexible Sync subscriptions"
  - "User asks about Atlas Edge Server for factory floor, retail, or embedded/industrial environments"
  - "User needs to migrate from Realm SDK to Atlas Device SDK or from Device Sync to an alternative"
  - "User asks about Realm object model: RealmObject, RealmList, RealmSet, RealmDictionary, primary keys, relationships"
  - "User asks about Flexible Sync conflict resolution, client reset, or asymmetric sync"
  - "User asks about Realm authentication: email/password, JWT, Google, Apple, Facebook"
  - "User asks about the realm Flutter/Dart package and code generation"
  - "User asks about Device SDK performance, battery optimization, or live queries"
keywords:
  - "atlas device sdk"
  - "realm sdk"
  - "realm database"
  - "atlas device sync"
  - "flexible sync"
  - "atlas edge server"
  - "realm object"
  - "offline-first mobile"
  - "realm swift kotlin flutter"
  - "mobile sync mongodb"
  - "asymmetric sync"
  - "realm migration"
  - "realm flutter dart"
---

# MongoDB Atlas Device SDK & Edge Server

> **DEPRECATION NOTICE — Critical Context for All Readers**
>
> On **September 9, 2024**, MongoDB announced the deprecation of Atlas Device Sync + Realm SDKs. The sync service (Atlas Device Sync) reached **end-of-life on September 30, 2025**. The local Realm database library continues as an open-source project, but SDK versions 20.x and later no longer support cloud synchronization. Users who need mobile-to-cloud sync must migrate to alternatives.
>
> This skill documents the final architecture of the system because: (1) existing apps built on Realm/Device Sync still run in production and require support, (2) the Realm local database (without sync) is still viable open-source, and (3) the underlying patterns inform alternative architectures. All guidance is explicitly labeled by EOL status.

---

## When NOT to Use This Skill

Do not use this skill to guide **new greenfield project decisions**. Atlas Device Sync reached end-of-life on September 30, 2025 and is permanently shut down. Use this skill for:
- Supporting existing Realm/Device Sync production apps
- Advising on the EOL migration path for a current Realm customer
- Understanding the Realm local database (still viable open-source, sync-free)

For new mobile sync architectures, redirect to alternatives: PowerSync, Couchbase Mobile, Ditto, or custom HTTP sync over Atlas.

---

## Overview

MongoDB Atlas Device SDK was the official rebrand of the Realm SDK in 2023, completing the migration of Realm (acquired by MongoDB in 2019) into the Atlas platform family. The system comprised two layers:

1. **Realm local database** — an embedded, file-backed, reactive object store. Open-source (Apache 2.0). Continues to exist as a local database library without cloud sync.
2. **Atlas Device Sync** — a managed sync service inside Atlas App Services that bridged the on-device Realm to a MongoDB Atlas cluster via a binary WebSocket protocol. **Shut down September 30, 2025.**

**Atlas Edge Server** was a companion feature in public preview (May 2024) — a MongoDB process deployable at the edge (factory, retail, aircraft) that acted as an intermediate sync tier between device SDKs and Atlas. It was also deprecated before September 30, 2024.

---

## 1. SDK Language Matrix

MongoDB maintained official SDKs for seven language/platform targets:

| Language / SDK | Repository | Primary Platforms | Local DB | Sync Support (pre-EOL) |
|---|---|---|---|---|
| Swift | realm/realm-swift | iOS 16+, macOS 13+, tvOS 16+, watchOS 9+ | Yes | Yes (Flexible Sync) |
| Kotlin | realm/realm-kotlin | Android 8+ (API 26+), Kotlin Multiplatform | Yes | Yes (Flexible Sync) |
| Java | realm/realm-java | Android 5+ (API 21+) | Yes | Yes (Partition-Based only) |
| JavaScript / Node.js | realm/realm-js | React Native 0.71+, Node.js 18+ | Yes | Yes (Flexible Sync) |
| .NET / C# | realm/realm-dotnet | Xamarin, MAUI, .NET 6+ | Yes | Yes (Flexible Sync) |
| Flutter / Dart | realm/realm-dart | Flutter 3.10.2+ (iOS, Android, Win, macOS, Linux), Dart 3.0.2+ | Yes | Yes (Flexible Sync) |
| C++ | realm/realm-cpp | Linux, macOS, Windows (embedded-target support) | Yes | Yes (Flexible Sync) |

**Package identifiers:**
- Swift: `RealmSwift` (SPM: `realm-swift`), CocoaPods pod `RealmSwift`
- Kotlin: `io.realm.kotlin` — `library-base` (local) + `library-sync` (Device Sync)
- Java: `io.realm:realm-android` — Gradle plugin `realm-android`
- JavaScript: npm `realm` (was `realm@^12`)
- .NET: NuGet `Realm` + `Realm.Fody`
- Flutter/Dart: pub.dev `realm` (v20.x current), `realm_generator`
- C++: header-only via CPM/cmake

**Version compatibility with Atlas App Services:** Device Sync required Atlas App Services (a sub-component of MongoDB Atlas, replacing the original "Realm Cloud"). App Services ran on dedicated Atlas-hosted infrastructure — the SDK connected to an App Services "application" identified by its App ID (e.g., `myapp-abcde`). The App Services endpoint was `https://realm.mongodb.com` with WebSocket sync over `wss://ws.realm.mongodb.com`.

---

## 2. Realm Object Model

### 2.1 Defining Objects

Each language has its own class definition pattern. The underlying storage is always a B-tree file on disk (the `.realm` file).

**Swift (`@Persisted` wrapper, SDK 10+):**
```swift
import RealmSwift

class Task: Object {
    @Persisted(primaryKey: true) var _id: ObjectId = ObjectId.generate()
    @Persisted var title: String = ""
    @Persisted var completed: Bool = false
    @Persisted var dueDate: Date?
    @Persisted var tags: List<String>
    @Persisted var subtasks: List<Subtask>
    @Persisted var assignee: User?      // to-one relationship (optional link)
}

class Subtask: EmbeddedObject {         // EmbeddedObject: lifecycle tied to parent
    @Persisted var name: String = ""
    @Persisted var done: Bool = false
}
```

**Kotlin (`RealmObject` interface):**
```kotlin
import io.realm.kotlin.types.RealmObject
import io.realm.kotlin.types.ObjectId
import io.realm.kotlin.ext.realmListOf

class Task : RealmObject {
    @PrimaryKey
    var _id: ObjectId = ObjectId.create()
    var title: String = ""
    var completed: Boolean = false
    var dueDate: RealmInstant? = null
    var tags: RealmList<String> = realmListOf()
    var subtasks: RealmList<Subtask> = realmListOf()
}

class Subtask : EmbeddedRealmObject {   // EmbeddedRealmObject in Kotlin SDK
    var name: String = ""
    var done: Boolean = false
}
```

**JavaScript / React Native:**
```javascript
const TaskSchema = {
  name: 'Task',
  primaryKey: '_id',
  properties: {
    _id:        'objectId',
    title:      'string',
    completed:  {type: 'bool', default: false},
    dueDate:    'date?',
    tags:       'string[]',           // shorthand for list<string>
    subtasks:   'Subtask[]',
    assignee:   'User?',
  },
};
```

**Flutter/Dart (code-gen annotation):**
```dart
import 'package:realm/realm.dart';
part 'task.realm.dart';             // generated file

@RealmModel()
class _Task {
  @PrimaryKey()
  late ObjectId id;

  late String title;
  bool completed = false;
  DateTime? dueDate;
  List<String> tags = [];           // RealmList<String> in generated class
}
```
Generate: `dart run realm generate` (Flutter) or `dart run realm_dart generate` (Dart standalone).

### 2.2 Supported Property Types

| Realm Type | Swift | Kotlin | JavaScript | Notes |
|---|---|---|---|---|
| Boolean | `Bool` | `Boolean` | `bool` | |
| Integer (32-bit) | `Int` | `Int` | `int` | |
| Integer (64-bit) | `Int64` | `Long` | `int` (JS uses 64-bit) | |
| Float / Double | `Float`, `Double` | `Float`, `Double` | `float`, `double` | |
| String | `String` | `String` | `string` | |
| Date | `Date` | `RealmInstant` | `date` | |
| Data / Binary | `Data` | `ByteArray` | `data` | |
| ObjectId | `ObjectId` | `ObjectId` | `objectId` | BSON ObjectId |
| UUID | `UUID` | `RealmUUID` | `uuid` | |
| Decimal128 | `Decimal128` | `BsonDecimal128` (via BSON) | `decimal128` | |
| Mixed / Any | `AnyRealmValue` | `RealmAny` | `mixed` | Any of the above |
| List | `List<T>` | `RealmList<T>` | `T[]` / `list<T>` | Ordered, duplicates allowed |
| Set | `MutableSet<T>` | `RealmSet<T>` | `set<T>` | Unordered, unique elements |
| Dictionary | `Map<String, T>` | `RealmDictionary<T>` | `dictionary<T>` | String keys only |

### 2.3 Primary Keys

- Annotated with `@PrimaryKey` (Kotlin) / `primaryKey: true` in `@Persisted` (Swift) / `primaryKey` field in schema (JS) / `@PrimaryKey()` (Dart).
- Supported types: `String`, `ObjectId`, `UUID`, integer types.
- For Device Sync, the primary key field **must** be named `_id` to align with the MongoDB document `_id` field.
- Primary keys are immutable once the object is written to a synced realm.

### 2.4 Relationships

| Relationship Type | Mechanism | Notes |
|---|---|---|
| To-one (optional link) | Nullable object property | `var assignee: User?` |
| To-one (required) | Non-null object property | Must not be null after migration |
| To-many | `RealmList<T>` / `List<T>` | Ordered; allows duplicates |
| Unique collection | `RealmSet<T>` / `MutableSet<T>` | Elements must be unique |
| Key-value map | `RealmDictionary<T>` / `Map<String, T>` | String keys only |
| Backlink / Inverse | `@Backlinks` (Swift) / `linkingObjects()` (Kotlin) | Computed; not stored on disk |
| Embedded | `EmbeddedObject` / `EmbeddedRealmObject` | Lifecycle bound to parent; no independent `_id` |

**Backlinks example (Swift):**
```swift
class User: Object {
    @Persisted(primaryKey: true) var _id: ObjectId
    @Persisted var name: String = ""
    @Persisted(originProperty: "assignee") var assignedTasks: LinkingObjects<Task>
}
```

### 2.5 Schema Versioning and Migration

Realm tracks a `schemaVersion` integer in the Realm configuration. Whenever the schema changes (field added, renamed, type changed), the version must be incremented and a migration block provided.

**Swift migration example:**
```swift
let config = Realm.Configuration(
    schemaVersion: 4,
    migrationBlock: { migration, oldSchemaVersion in
        if oldSchemaVersion < 3 {
            // Rename field
            migration.renameProperty(onType: "Task", from: "name", to: "title")
        }
        if oldSchemaVersion < 4 {
            // Populate new field from existing data
            migration.enumerateObjects(ofType: "Task") { old, new in
                new!["completed"] = false
            }
        }
    }
)
```

**Migration strategies:**
- **Incremental migration block** — recommended for production; preserves data.
- `deleteRealmIfMigrationNeeded` — use only in development; deletes all local data on schema mismatch.
- **Additive-only schema changes** (add fields) — do not require a migration block in most SDKs; the new field defaults to its zero value.

---

## 3. Atlas Device Sync (Flexible Sync)

> **Status: EOL September 30, 2025.** Document for legacy support.

### 3.1 Architecture

Atlas Device Sync ran as a component inside Atlas App Services. The SDK maintained a persistent WebSocket connection to the App Services sync endpoint. Changes were streamed bidirectionally using a binary protocol (Operational Transformation-based). The sync server translated between the Realm wire format and native MongoDB BSON documents stored in Atlas.

```
Device (Realm DB)  ←──WebSocket (TLS 443)──→  Atlas App Services Sync Server  ←──→  MongoDB Atlas Cluster
       ↕                                                  ↕
   Local writes                              Conflict resolution + fan-out
   Change log                                to other subscribed clients
```

### 3.2 Flexible Sync vs Partition-Based Sync

| Feature | Flexible Sync | Partition-Based Sync |
|---|---|---|
| Data selection | Query-based subscriptions (RQL) | Partition key value match |
| Granularity | Document-level, based on queryable fields | Collection-wide, per partition |
| Cross-partition queries | Supported | Not supported |
| Complexity | Higher (subscription management) | Lower (single key) |
| Status | Recommended (was) | Legacy — Kotlin/Java never fully supported |

### 3.3 Flexible Sync Subscriptions

Subscriptions are named query sets stored in a `SubscriptionSet`. They define which documents from each object type are synced to the device.

**Opening a synced Realm (Swift):**
```swift
let app = App(id: "your-app-id")
let user = try await app.login(credentials: .emailPassword(
    email: "user@example.com",
    password: "s3cr3t"
))

var config = user.flexibleSyncConfiguration()
config.objectTypes = [Task.self, User.self]
let realm = try await Realm(configuration: config)
```

**Adding subscriptions (Swift):**
```swift
let subs = realm.subscriptions
try await subs.update {
    // Add or update named subscriptions
    if let existing = subs.first(named: "my-tasks") {
        existing.updateQuery(toType: Task.self) { $0.assigneeId == user.id }
    } else {
        subs.append(
            QuerySubscription<Task>(name: "my-tasks") { $0.assigneeId == user.id }
        )
    }
    // Subscribe to a related type
    subs.append(QuerySubscription<User>(name: "all-users"))
}
// After update() completes, matching documents are on-device
```

**Kotlin subscription with `.subscribe()` (SDK 1.10+):**
```kotlin
// New shorthand — creates subscription automatically in background
val tasks = realm.query<Task>("assigneeId == $0", user.id)
    .subscribe(name = "my-tasks", updateExisting = true)
// Returns Flow<RealmResults<Task>> or blocks depending on mode

// Manual subscription management (explicit SubscriptionSet API)
realm.subscriptions.update {
    add(realm.query<Task>("assigneeId == $0", user.id), name = "my-tasks")
}
```

**JavaScript subscription:**
```javascript
await realm.subscriptions.update(mutableSubs => {
    mutableSubs.add(
        realm.objects('Task').filtered('assigneeId == $0', user.id),
        { name: 'my-tasks' }
    );
});
```

### 3.4 Queryable Fields

Not all fields can be used in subscription queries. Fields must be declared as **queryable fields** in the App Services UI or via the App Services CLI. Only top-level primitive fields, lists, and sets are eligible. Embedded object fields are not directly queryable.

### 3.5 Initial Subscriptions

Initial subscriptions are evaluated at Realm open time, before `downloadBeforeOpen` completes. They allow pre-populating local data without a separate subscription update call.

**Swift:**
```swift
var config = user.flexibleSyncConfiguration(
    initialSubscriptions: { subs in
        subs.append(QuerySubscription<Task>(name: "all-mine") {
            $0.assigneeId == user.id
        })
    },
    rerunOnOpen: false    // set true to re-evaluate on every app open
)
```

### 3.6 Sync Session Management

```swift
// Pause / resume sync
let session = realm.syncSession!
session.suspend()
session.resume()

// Observe connection state
let token = session.observe(\SyncSession.connectionState) { session, change in
    switch session.connectionState {
    case .disconnected:  print("Offline")
    case .connecting:    print("Connecting…")
    case .connected:     print("Live")
    @unknown default:    break
    }
}
token.invalidate() // stop observing
```

**Kotlin (connection state flow):**
```kotlin
realm.syncSession.connectionStateAsFlow().collect { change ->
    when (change.newState) {
        ConnectionState.DISCONNECTED -> { /* offline */ }
        ConnectionState.CONNECTING   -> { /* reconnecting */ }
        ConnectionState.CONNECTED    -> { /* live */ }
    }
}
```

### 3.7 Offline-First Behavior

When the device is offline:
1. All local reads and writes succeed immediately against the Realm file.
2. Writes are appended to an internal change log (the "upload queue").
3. On reconnection, the SDK replays the upload queue to the sync server.
4. Server changes downloaded since last sync are replayed locally (download queue).
5. Conflicts between the two queues are resolved by the sync engine before being applied.

The sync session automatically manages reconnection with exponential backoff.

### 3.8 Asymmetric Sync (Data Ingest)

Asymmetric sync (also called "Data Ingest") is a write-only mode for high-volume, insert-only workloads such as IoT telemetry, event logging, or sensor readings. Objects are synced to Atlas but never queried back to the device, and they are automatically deleted from the local Realm after sync.

**Use cases:** GPS tracking, temperature sensors, clickstream data, audit events.

**Kotlin asymmetric object:**
```kotlin
class SensorReading : AsymmetricRealmObject {
    @PrimaryKey
    var _id: ObjectId = ObjectId.create()
    var deviceId: String = ""
    var temperature: Double = 0.0
    var timestamp: RealmInstant = RealmInstant.from(System.currentTimeMillis() / 1000, 0)
}

// Insert (no return value — object deleted after sync)
realm.write {
    insert(SensorReading().apply {
        deviceId = "sensor-001"
        temperature = 23.4
    })
}
```

**Swift asymmetric object:**
```swift
class SensorReading: AsymmetricObject {
    @Persisted(primaryKey: true) var _id: ObjectId = ObjectId.generate()
    @Persisted var deviceId: String = ""
    @Persisted var temperature: Double = 0.0
    @Persisted var timestamp: Date = Date()
}

try realm.write {
    realm.create(SensorReading.self, value: [
        "_id": ObjectId.generate(),
        "deviceId": "sensor-001",
        "temperature": 23.4,
    ])
}
```

Constraints: Asymmetric objects cannot be queried, updated, or deleted via the Realm API. They cannot link to non-asymmetric objects. No conflict resolution needed — inserts are always applied.

---

## 4. Atlas Edge Server

> **Status: Deprecated before September 30, 2024.**

### 4.1 What Edge Server Was

Atlas Edge Server was a MongoDB process (a full `mongod` instance plus a sync server sidecar) designed to run on-premises or at geographically remote locations. It acted as a middle tier between Device SDK clients and a central MongoDB Atlas cluster.

**Typical deployment sites:**
- Factory floors (intermittent WAN connectivity, latency-sensitive PLC integration)
- Retail store back-offices (point-of-sale resilience during internet outages)
- Aircraft / maritime vessels (intermittent satellite connectivity)
- Hospital wards (local compliance requirements, network segmentation)

**Architecture:**
```
[Device SDK clients]  ←── Device Sync ──→  [Edge Server (mongod + sync)]  ←── Atlas Device Sync ──→  [MongoDB Atlas]
                              ↑                        ↑
                      WebSocket (TLS)           WAN / satellite link
                      (LAN or local WiFi)       (intermittent OK)
```

### 4.2 Edge Server vs Direct Atlas Sync

| Factor | Direct Atlas Sync | Via Edge Server |
|---|---|---|
| Connectivity requirement | WAN to Atlas (always) | LAN to Edge only (WAN optional) |
| Latency | Depends on Atlas region | Sub-millisecond local LAN |
| WAN failure impact | Apps go offline | Apps continue via Edge |
| Bandwidth | All changes go to Atlas | Only aggregated deltas cross WAN |
| Scale | Per-Atlas-connection limit | Many local devices, few WAN sessions |
| Use case | Consumer mobile | Industrial / embedded / remote edge |

### 4.3 Deployment Model

**Docker Compose (development):**
```yaml
services:
  edge-server:
    image: mongodb/mongodb-atlas-edge-server:latest
    environment:
      APPSERVICES_APP_ID: your-app-id
      REGISTRATION_TOKEN: your-token
    ports:
      - "27021:27021"   # Device Sync port (SDK clients connect here)
      - "27020:27020"   # Admin API port
```

**Kubernetes via `edgectl` and the Edge Kubernetes Operator:**
```bash
# Install edgectl
curl https://services.cloud.mongodb.com/edge/install.sh | bash -s

# Initialize configuration (requires App ID and registration token from UI)
edgectl init --platform kubernetes --app-id <APP-ID>

# Apply the generated manifest
kubectl apply -f edge-server.yaml
```

The Kubernetes Operator manages two pods: the Edge Server pod and a backing MongoDB pod (managed by the MongoDB Community Operator).

### 4.4 Device SDK Connection to Edge Server

Clients configured to use Edge Server point their App Services base URL to the Edge Server's local address instead of the Atlas endpoint:

```swift
// Swift — point SDK at Edge Server
let app = App(id: "your-app-id",
              configuration: AppConfiguration(baseURL: "http://192.168.1.10:27021"))
```

```kotlin
// Kotlin
val app = App.create(
    AppConfiguration.Builder("your-app-id")
        .baseUrl("http://192.168.1.10:27021")
        .build()
)
```

### 4.5 Edge Server Admin API

Edge Server exposed a REST Admin API on port `27020`:
- `GET /api/edge/v1.0/info` — Edge Server status and version
- `POST /api/edge/v1.0/auth` — authenticate with token
- `GET /api/edge/v1.0/connection` — upstream Atlas connection state
- `POST /api/edge/v1.0/pause` / `POST /api/edge/v1.0/resume` — control upstream sync

The `edgectl` CLI wrapped these endpoints for local management.

---

## 5. Realm → Atlas Device SDK Migration

> This section covers two distinct migration paths:
> (A) Upgrading legacy Realm SDK code to Atlas Device SDK API conventions (still relevant for local DB use).
> (B) Migrating off Atlas Device Sync to an alternative backend (required by September 2025 EOL).

### 5.1 Path A: Legacy Realm API → Atlas Device SDK API

Major API changes introduced with the Atlas Device SDK rebranding (2022–2023):

| Area | Old Realm SDK | Atlas Device SDK |
|---|---|---|
| Swift property declaration | `@objc dynamic var title: String = ""` | `@Persisted var title: String = ""` |
| Swift object definition | `class Task: Object { }` | Same, but `@Persisted` wrappers required for sync |
| Swift concurrency | Callback-based | `async/await` throughout (RealmSwift 10.x, requires Xcode 13+) |
| Kotlin object definition | `open class Task : RealmObject() { }` | `class Task : RealmObject { }` (no `open`, no constructor call) |
| Kotlin sync config | `SyncConfiguration.defaultConfig(user, partitionValue)` | `SyncConfiguration.Builder(user, schema).build()` for Flexible Sync |
| Partition-Based Sync | `partitionValue: "user=\(user.id)"` | Replace with Flexible Sync subscriptions |
| JS schema format | `{ properties: { id: 'objectId' } }` | Same format; `@realm/react` library recommended |
| .NET migration | `RealmObject` subclass | Same; `[PrimaryKey]` on `_id` field |

**Swift: `@objc dynamic` → `@Persisted` migration:**
```swift
// Before (legacy)
class Task: Object {
    @objc dynamic var _id: ObjectId = ObjectId.generate()
    @objc dynamic var title: String = ""
    override static func primaryKey() -> String? { return "_id" }
}

// After (Atlas Device SDK)
class Task: Object {
    @Persisted(primaryKey: true) var _id: ObjectId = ObjectId.generate()
    @Persisted var title: String = ""
}
```

**Kotlin: Partition-Based → Flexible Sync:**
```kotlin
// Before (Partition-Based)
val config = SyncConfiguration.defaultConfig(user, "user=${user.id}")

// After (Flexible Sync)
val config = SyncConfiguration.Builder(user, schema = setOf(Task::class))
    .initialSubscriptions { realm ->
        add(realm.query<Task>("ownerId == $0", user.id), name = "user-tasks")
    }
    .build()
```

### 5.2 Path B: Migrating Off Atlas Device Sync (EOL Path)

As of September 30, 2025, Atlas Device Sync is shut down. Options for apps that required sync:

| Alternative | Approach | Notes |
|---|---|---|
| **Realm local DB only** | Remove sync; keep Realm as local SQLite-like store | Versions 20.x+ are sync-free; viable if offline-only |
| **Custom HTTP sync** | Build your own REST/WebSocket sync layer over Atlas | Full control; significant engineering investment |
| **Couchbase Mobile** | Couchbase Lite + Sync Gateway + Couchbase Capella | Closest architectural equivalent; offers migration tooling |
| **PowerSync** | Postgres/MongoDB backend + PowerSync sync layer | Supports MongoDB Atlas as upstream |
| **Ditto** | P2P sync mesh without central server requirement | Strong for local-first, low-connectivity environments |
| **WatermelonDB** | Local SQLite + custom sync adapter | JavaScript/React Native focus |
| **Core Data + CloudKit** | Apple-platform only | Native iOS/macOS; no cross-platform |

**Extension requests:** Customers with active Atlas contracts who needed more time could open a MongoDB Support case and request a 3–6 month extension.

### 5.3 Migration Timeline Reference

| Date | Event |
|---|---|
| 2019 | MongoDB acquires Realm |
| 2022 | Partition-Based Sync → Flexible Sync migration path released |
| February 2023 | Realm SDK renamed to Atlas Device SDK |
| May 2, 2024 | Atlas Edge Server enters public preview |
| September 9, 2024 | Deprecation of Atlas Device Sync + Realm SDKs announced |
| Pre-September 30, 2024 | Atlas Edge Server deprecated |
| September 30, 2025 | Atlas Device Sync end-of-life; sync service shut down |
| Post-September 2025 | Realm local DB continues as open-source (no cloud sync) |

---

## 6. Authentication Providers

Authentication was handled by Atlas App Services (also EOL for most features after September 2025). The SDK's `App` object managed auth state; credentials were passed to `app.login()`.

### 6.1 Supported Providers

| Provider | Credential Type | Notes |
|---|---|---|
| Anonymous | `Credentials.anonymous()` | Temporary; no account recovery |
| Email/Password | `Credentials.emailPassword(email, password)` | Requires email confirmation flow |
| API Key | `Credentials.userAPIKey(key)` | Server-side or client-side API key |
| Custom JWT | `Credentials.jwt(token)` | Any JWT from an external IdP |
| Google OAuth 2.0 | `Credentials.google(authCode:)` / `.google(idToken:)` | Requires Google Sign-In SDK |
| Apple Sign-In | `Credentials.apple(idToken:)` | Requires Sign in with Apple |
| Facebook | `Credentials.facebook(accessToken:)` | Requires Facebook SDK |
| Custom Function | `Credentials.function(payload:)` | Call an App Services function to validate |

### 6.2 Login Examples

**Swift — Email/Password:**
```swift
let app = App(id: "your-app-id")
let user = try await app.login(
    credentials: .emailPassword(email: "user@example.com", password: "s3cr3t")
)
```

**Swift — Anonymous (quick start):**
```swift
let user = try await app.login(credentials: .anonymous)
```

**Kotlin — Google Sign-In:**
```kotlin
// After obtaining Google auth code via GoogleSignIn SDK
val credentials = Credentials.google(serverAuthCode, GoogleAuthType.AUTH_CODE)
val user = app.login(credentials)
```

**JavaScript — Custom JWT:**
```javascript
const credentials = Realm.Credentials.jwt(myJwtToken);
const user = await app.logIn(credentials);
```

### 6.3 Token Management

- **Access tokens** expire after **30 minutes**. The SDK automatically refreshes access tokens using the refresh token — no application code needed.
- **Refresh tokens** do not auto-renew. Their expiry is configurable in App Services (default: 60 days). When the refresh token expires, the user is logged out and must re-authenticate.
- Access tokens are stored in browser `localStorage` / `sessionStorage` (Realm Web SDK) or the secure device keystore (mobile SDKs).
- The SDK exposes `user.accessToken` and `user.refreshToken` for custom JWT scenarios.

### 6.4 Linking Multiple Identities

A single App Services user account can link multiple auth identities (e.g., anonymous + email):

```swift
// Swift — link anonymous user to email/password
let emailCredentials = Credentials.emailPassword(email: "user@example.com", password: "pw")
try await anonymousUser.linkUser(credentials: emailCredentials)
// Same user._id preserved; data associated with anon account is retained
```

### 6.5 Email/Password Registration Flow

```swift
// 1. Register (sends confirmation email if configured)
try await app.emailPasswordAuth.registerUser(email: "user@example.com", password: "s3cr3t")

// 2. Confirm email (token from confirmation URL or email)
try await app.emailPasswordAuth.confirmUser(token: token, tokenId: tokenId)

// 3. Login
let user = try await app.login(credentials: .emailPassword(email: "user@example.com", password: "s3cr3t"))

// 4. Password reset
try await app.emailPasswordAuth.sendResetPasswordEmail(email: "user@example.com")
```

---

## 7. Conflict Resolution

### 7.1 Operational Transformation

Atlas Device Sync used an **Operational Transformation (OT)** algorithm for conflict resolution, not CRDTs. Each change in the Realm database was recorded as an atomic operation (insert, update, delete) with a logical timestamp. When multiple clients modified the same data while offline, the sync server merged their operation logs using OT.

**Default behavior (Last-Write-Wins for scalars):**
- For simple scalar fields (`String`, `Int`, `Bool`, etc.): the most recent write (by server timestamp) wins.
- For list operations: OT applies more intelligent strategies that attempt to preserve the intent of both writes (e.g., both an insert and a delete can coexist without one losing the other's intent).

### 7.2 Custom Conflict Resolution

Realm did not support user-defined conflict resolvers at the field level for normal objects. The sync engine's OT resolution was fixed. The supported approaches to influence conflict behavior:

1. **Asymmetric sync** — no conflict possible (write-only).
2. **Embedded objects** — changes to embedded objects are treated atomically with their parent.
3. **Server-side Atlas Functions** — post-sync triggers on Atlas could detect and reconcile conflicts in the Atlas collection after sync, but this was reactive, not preventive.
4. **Schema design** — appending to lists (rather than updating indexes) avoids field-level conflicts.

### 7.3 Client Reset Strategies

A **client reset** is triggered when the sync server cannot reconcile the client's change log with the server state (e.g., the client has been offline for longer than the server's history retention window, or the App Services app was reset). Four strategies:

| Strategy | Behavior | Data Loss Risk |
|---|---|---|
| `recoverUnsyncedChanges` (default) | SDK attempts to re-apply unsynced local changes after downloading fresh server state | Low — local changes replayed if possible |
| `recoverOrDiscardUnsyncedChanges` | Recovery attempted; falls back to discard if recovery fails | Medium — changes discarded on fallback |
| `discardUnsyncedChanges` | Local Realm replaced with server state; all unsynced changes lost | High — unsynced data permanently lost |
| `manual` | Application code handles the reset; SDK provides old and new Realm file paths | None (app controls outcome) |

**Swift client reset handler:**
```swift
var config = user.flexibleSyncConfiguration(
    clientResetMode: .recoverOrDiscardUnsyncedChanges(
        beforeReset: { realm in
            // Save local state before reset (optional backup)
        },
        afterReset: { before, after in
            // `before` is frozen snapshot of pre-reset Realm
            // `after` is the recovered Realm
            // Merge any critical data here
        }
    )
)
```

**Kotlin client reset:**
```kotlin
val config = SyncConfiguration.Builder(user, schema)
    .syncClientResetStrategy(object : RecoverOrDiscardUnsyncedChangesStrategy {
        override fun onBeforeReset(realm: TypedRealm) { /* backup */ }
        override fun onAfterRecovery(before: TypedRealm, after: MutableRealm) { }
        override fun onAfterDiscard(before: TypedRealm, after: MutableRealm) { }
        override fun onError(session: SyncSession, exception: ClientResetRequiredException) { }
    })
    .build()
```

### 7.4 Conflict Design Patterns

- **Prefer appending to lists** over updating indexed positions — list inserts from two clients both survive; two updates to the same index produce a winner/loser.
- **Use `@MapTo` for field renaming** (Java SDK / legacy Kotlin SDK only) — annotate fields with the canonical Atlas field name when local and Atlas names differ; avoids silent field mismatch bugs on conflict. In modern Kotlin SDK use the `@PersistedName` annotation instead.
- **Prefer embedded objects for sub-documents** — the parent-child ownership model means the entire embedded subtree is treated as one atomic update, preventing interleaved partial updates.
- **High-frequency telemetry → asymmetric sync** — removes conflict surface entirely.

---

## 8. Performance and Battery Optimization

### 8.1 Memory Model: Lazy Loading

Realm objects are **live objects** — they hold a reference into the memory-mapped Realm file, not a deserialized copy. Property access reads directly from the file via zero-copy pointer arithmetic. This means:

- Object creation (query result) is O(1) regardless of object size.
- Only accessed properties cause actual memory pages to be read.
- Result sets (`RealmResults`) are lazily populated — iterating 10,000 results loads only the accessed pages.

**Implication:** Avoid materializing large result sets into Swift `Array` / Kotlin `List` / JS plain arrays unless needed for serialization. Keep Realm results as `Results<T>` / `RealmResults<T>` for UI binding.

### 8.2 Transactions

Realm batches writes in transactions. Each `realm.write {}` is a single ACID transaction with a single disk flush. Write cost is dominated by the commit, not the operations within the transaction.

**Performance rule:** Batch related writes into a single transaction.

```swift
// Slow: 1000 separate flushes
for item in items { try realm.write { realm.add(item) } }

// Fast: 1 flush
try realm.write {
    for item in items { realm.add(item) }
}
```

**Kotlin async write:**
```kotlin
// Blocking write on calling thread (use background dispatcher)
realm.write {
    for (item in items) { copyToRealm(item) }
}
// Or: realm.writeBlocking { ... }  for non-suspending contexts
```

### 8.3 Thread Model

Realm instances are **not thread-safe** — each thread that accesses Realm must open its own Realm instance (Realm caches and reuses instances per-thread automatically when opened with the same configuration).

**Cross-thread patterns:**
- **Frozen objects** — call `.freeze()` on a `RealmObject` or `RealmResults` to get an immutable snapshot that can be passed across threads. Frozen objects do not auto-update.
- **Thread-safe references (TSR)** — pass a `ThreadSafeReference` across threads, then resolve it on the target thread's Realm instance.
- **Realm configurations** — always safe to pass across threads; open a new Realm from the config on each background thread.

```swift
// Swift: freeze for background processing
let frozenResults = realm.objects(Task.self).freeze()
DispatchQueue.global().async {
    for task in frozenResults {           // Safe — frozen
        print(task.title)                 // No auto-update
    }
}

// Swift: ThreadSafeReference for mutations from background thread
let ref = ThreadSafeReference(to: task)
DispatchQueue.global().async {
    let realm = try! Realm()              // New Realm instance on this thread
    guard let task = realm.resolve(ref) else { return }
    try! realm.write { task.completed = true }
}
```

### 8.4 Sync Session Optimization

- **Pause sync when not needed** (`session.suspend()` / `session.resume()`) — e.g., pause during large local batch operations to prevent flooding the upload queue.
- **Fine-grained subscriptions** — subscribe only to documents the user will actually view. Avoid `objects('Task')` with no predicate on large collections.
- **`downloadBeforeOpen: .never`** — open realm immediately from local cache; accept stale data on first open.
- **Compact on launch** — configure `shouldCompactOnLaunch` to reduce file size on startup (Swift), or `compactOnLaunch()` (Kotlin).

```swift
// Swift: compact only if file > 50MB and <20% used
var config = user.flexibleSyncConfiguration()
config.shouldCompactOnLaunch = { totalBytes, usedBytes in
    let fiftyMB = 50 * 1024 * 1024
    return (totalBytes > fiftyMB) && (Double(usedBytes) / Double(totalBytes)) < 0.2
}
```

### 8.5 Battery Impact

- Realm's zero-copy read model means **no CPU serialization overhead** on reads — favorable for battery.
- Atlas Device Sync maintained a persistent **WebSocket** — one open TLS connection, which is battery-friendlier than HTTP polling.
- The SDK used **exponential backoff** on reconnect — no tight retry loops draining battery during outages.
- **Background sync** (iOS Background App Refresh / Android WorkManager) — trigger `session.resume()` in a background task to sync while app is backgrounded; call `session.suspend()` when done to allow the connection to close.

---

## 9. Data Access Patterns

### 9.1 Live Queries

Realm queries return **live result sets** that auto-update when the underlying data changes. Registering a change listener (notification token) delivers fine-grained change information (insertions, deletions, modifications).

**Swift live query:**
```swift
var token: NotificationToken?

func observeTasks(in realm: Realm) {
    let tasks = realm.objects(Task.self).filter("completed == false").sorted(byKeyPath: "dueDate")
    
    token = tasks.observe { changes in
        switch changes {
        case .initial(let results):
            print("Initial: \(results.count) tasks")
        case .update(let results, let deletions, let insertions, let modifications):
            tableView.performBatchUpdates({
                tableView.deleteRows(at: deletions.map { IndexPath(row: $0, section: 0) }, with: .automatic)
                tableView.insertRows(at: insertions.map { IndexPath(row: $0, section: 0) }, with: .automatic)
                tableView.reloadRows(at: modifications.map { IndexPath(row: $0, section: 0) }, with: .automatic)
            })
        case .error(let error):
            print("Error: \(error)")
        }
    }
}

deinit { token?.invalidate() }
```

**Kotlin live query with Flow:**
```kotlin
realm.query<Task>("completed == false")
    .sort("dueDate", Sort.ASCENDING)
    .asFlow()
    .collect { changes: ResultsChange<Task> ->
        when (changes) {
            is InitialResults -> adapter.submitList(changes.list)
            is UpdatedResults -> adapter.submitList(changes.list) // DiffUtil handles delta
        }
    }
```

### 9.2 Realm as Local Cache + Atlas as Source of Truth

The canonical offline-first pattern:

1. **Read from local Realm** — always fast, always available.
2. **Write to local Realm** — immediately visible to the UI via live queries.
3. **Sync propagates to Atlas** — async, transparent to the user.
4. **Atlas-side operations** (aggregations, analytics) run on Atlas directly; push results back as Atlas Triggers or Data API calls.

```
UI Layer
  │  ↕ live queries / observe
  │
Realm (local cache)  ←── sync ──→  Atlas (source of truth)
                                       │
                                   Analytics / Aggregation
                                   Atlas Charts
                                   Atlas Search
```

### 9.3 Offline-First Read Pattern

```swift
// Open realm immediately from local cache; no wait for download
var config = user.flexibleSyncConfiguration()
// NOTE: try! used here for brevity — use try/catch in production
let realm = try! await Realm(configuration: config, downloadBeforeOpen: .never)

// Data is available immediately from prior sync
let tasks = realm.objects(Task.self)
// Sync resumes in background; live queries update the UI as new data arrives
```

### 9.4 Pagination with Realm

```swift
// Swift: lazy section — only pages loaded by the scroll view are in memory
let allTasks = realm.objects(Task.self).sorted(byKeyPath: "createdAt", ascending: false)
// Bind directly to UITableView or SwiftUI List — Realm manages lazy loading
```

### 9.5 `@ObservedResults` / `@ObservedRealmObject` (SwiftUI)

The `@ObservedResults` property wrapper integrates live Realm queries with SwiftUI's state system:

```swift
struct TaskListView: View {
    @ObservedResults(Task.self, filter: NSPredicate(format: "completed == false")) var tasks

    var body: some View {
        List {
            ForEach(tasks) { task in
                Text(task.title)
            }
            .onDelete { indexSet in $tasks.remove(atOffsets: indexSet) }
        }
    }
}
```

Changes to the Realm collection automatically trigger SwiftUI view updates with no manual `objectWillChange` calls needed.

### 9.6 `@realm/react` (React Native)

```javascript
import { RealmProvider, useQuery, useRealm, useObject } from '@realm/react';

// Wrap app
<RealmProvider schema={[TaskSchema]} sync={syncConfig}>
    <TaskList />
</RealmProvider>

// In component
function TaskList() {
    const tasks = useQuery(Task, (collection) =>
        collection.filtered('completed == false').sorted('dueDate')
    );
    return <FlatList data={tasks} renderItem={/* ... */} />;
}
```

---

## 10. Flutter/Dart SDK

### 10.1 Setup and Code Generation

**pubspec.yaml:**
```yaml
dependencies:
  realm: ^20.0.0

dev_dependencies:
  realm_generator: ^20.0.0
  build_runner: ^2.4.0
```

**Dart SDK minimum: 3.0.2; Flutter minimum: 3.10.2**

**Model definition (underscore prefix = template class):**
```dart
// task.dart
import 'package:realm/realm.dart';
part 'task.realm.dart';   // generated; commit this file

@RealmModel()
class _Task {
  @PrimaryKey()
  late ObjectId id;

  late String title;
  bool completed = false;
  DateTime? dueDate;
  
  // List property
  List<String> tags = [];
  
  // Backlink (from Subtask.owner)
  @Backlink(#owner)
  late Iterable<_Subtask> subtasks;
}

@RealmModel()
class _Subtask {
  @PrimaryKey()
  late ObjectId id;
  late String name;
  bool done = false;
  late _Task owner;   // to-one relationship
}
```

**Generate the RealmObject classes:**
```bash
# One-time generation
dart run realm generate

# Watch mode during development
dart run realm generate --watch
```

The generator produces `task.realm.dart` containing the concrete `Task` and `Subtask` classes. Commit the generated files.

### 10.2 Opening a Local Realm

```dart
// Basic open (no migration needed)
final config = Configuration.local([Task.schema, Subtask.schema], schemaVersion: 1);
final realm = Realm(config);
```

```dart
// With a migration block (schema version incremented — separate from the basic open above)
final configV2 = Configuration.local(
  [Task.schema],
  schemaVersion: 2,
  migrationCallback: (migration, oldSchemaVersion) {
    if (oldSchemaVersion < 2) {
      migration.renameProperty('Task', 'name', 'title');
    }
  },
);
final realm = Realm(configV2); // separate Realm instance from the basic example above
```

### 10.3 Write Operations

```dart
// Insert
final task = Task(ObjectId(), 'Buy groceries');
realm.write(() => realm.add(task));

// Update (must be inside write transaction)
realm.write(() => task.completed = true);

// Delete
realm.write(() => realm.delete(task));

// Batch insert
realm.write(() {
  for (final item in items) { realm.add(item); }
});
```

### 10.4 Queries

```dart
// All incomplete tasks sorted by dueDate
final tasks = realm.all<Task>()
    .query('completed == false SORT(dueDate ASC)');

// With parameters
final userTasks = realm.all<Task>()
    .query(r'ownerId == $0', [userId]);
```

Realm Query Language (RQL) is the same across all SDKs — NSPredicate-compatible syntax.

### 10.5 Live Queries and Streams

```dart
// Stream of changes (RealmResultsChanges)
final subscription = realm.all<Task>()
    .query('completed == false')
    .changes
    .listen((changes) {
      print('Inserted: ${changes.inserted}');
      print('Modified: ${changes.modified}');
      print('Deleted:  ${changes.deleted}');
    });

// Cancel when done
await subscription.cancel();
```

### 10.6 Flexible Sync (Flutter)

> **EOL Note:** Device Sync shut down September 30, 2025. Code below is for reference.

```dart
final app = App(AppConfiguration('your-app-id'));
final user = await app.logIn(Credentials.anonymous());

final config = Configuration.flexibleSync(
  user,
  [Task.schema],
);
final realm = await Realm.open(config);

// Add a subscription
await realm.subscriptions.update((mutableSubscriptions) {
  mutableSubscriptions.add(
    realm.all<Task>().query(r'ownerId == $0', [user.id]),
    name: 'user-tasks',
  );
});

// Wait for initial download
await realm.subscriptions.waitForSynchronization();
```

### 10.7 Platform-Specific Notes

- **iOS (Flutter):** Requires CocoaPods v1.11+ and `pod install` after adding the realm package. LLDB debugging may require the `realm-swift` dSYM.
- **Android:** The Realm AAR is included automatically; no manual NDK configuration needed for `realm` pub package v10+.
- **Windows/macOS/Linux:** The `realm_dart` native library ships pre-compiled binaries for x64; ARM64 macOS (Apple Silicon) supported from realm v10+.
- **Dart isolates:** Realm instances are single-isolate by default. To use Realm from a background isolate, open a new Realm instance (from the same configuration) in that isolate.

---

## References and See Also

### Official Documentation (pre-deprecation)
- [Atlas Device SDK Docs](https://www.mongodb.com/docs/atlas/device-sdks/) — top-level docs page
- [Atlas Device Sync — App Services](https://www.mongodb.com/docs/atlas/app-services/sync/) — sync configuration
- [Client Resets — App Services](https://www.mongodb.com/docs/atlas/app-services/sync/error-handling/client-resets/) — reset strategies
- [Asymmetric Sync (.NET)](https://www.mongodb.com/docs/realm/sdk/dotnet/fundamentals/asymmetric-sync/) — data ingest reference
- [Authentication Providers — App Services](https://www.mongodb.com/docs/atlas/app-services/authentication/) — all auth provider docs
- [Custom JWT Auth](https://www.mongodb.com/docs/atlas/app-services/authentication/custom-jwt/) — JWT configuration
- [realm pub.dev package](https://pub.dev/packages/realm) — Flutter/Dart package (v20.x current)
- [realm-dart GitHub](https://github.com/realm/realm-dart) — Flutter/Dart source
- [realm-kotlin GitHub](https://github.com/realm/realm-kotlin) — Kotlin SDK source
- [Edge Kubernetes Operator](https://github.com/mongodb/edge-kubernetes-operator) — Edge Server Kubernetes deployment

### Deprecation Notices
- [Atlas Device Sync End-of-Life Forum Post](https://www.mongodb.com/community/forums/t/atlas-device-sync-end-of-life-and-deprecation/296687) — official MongoDB announcement
- [Device Sync Deprecation (realm-js)](https://github.com/realm/realm-js/discussions/6884) — JS SDK discussion thread
- [realm-swift deprecation discussion](https://github.com/realm/realm-swift/discussions/8680) — Swift SDK community thread

### Migration Resources
- [PowerSync Atlas Device Sync Migration Guide](https://docs.powersync.com/migration-guides/atlas-device-sync) — PowerSync alternative
- [Couchbase Mobile Alternative](https://www.couchbase.com/blog/couchbase-mobile-alternative-to-mongodb-sync/) — Couchbase migration guide

### See Also (Related Skills)
- [[mongodb-realm-mobile-sync]] — Legacy Realm & Atlas Device Sync patterns, Partition-Based Sync, CRDT details, production pitfalls
- [[mongodb-atlas-app-services]] — App Services platform: auth, rules, triggers, schema — including post-EOL status of each component
- [[mongodb-atlas-triggers-functions]] — Atlas Triggers and Functions that remain active post-September 2025
