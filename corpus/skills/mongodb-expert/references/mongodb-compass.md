<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-expert` hub.** Formerly the standalone `mongodb-compass` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-compass
title: MongoDB Compass Expert Reference
version: "1.1.0"
last-updated: "2026-05-29"
category: mongodb
description: >
  Expert reference for MongoDB Compass — the official free GUI for MongoDB.
  TRIGGER: user asks how to use, configure, or troubleshoot Compass; questions about
  schema analysis ($sample sampling, field type distributions, cardinality), aggregation
  pipeline builder (stage view, focus mode, text view, export to language), explain plan
  visualizer (COLLSCAN vs IXSCAN, SORT stage, sharded cluster plans), index management
  (create, hide, drop, TTL, wildcard, Atlas Search indexes), performance insights,
  Atlas Performance Advisor in Compass, natural language query (NLQ) / AI-powered query
  generation, data import/export via GUI, data modeling ER diagrams, Compass Isolated
  Edition for air-gapped environments, Compass plugin architecture, or production safety
  guidance (anti-patterns for using Compass against live clusters).
  SKIP: MongoDB driver API or programmatic query construction (use mongodb-developer or
  mongodb-expert), deep query profiler analysis beyond Compass's built-in advisor
  (use mongodb-query-performance), Atlas cluster config/networking/billing
  (use mongodb-atlas-expert), mongodump/mongorestore/mongoimport CLI tools
  (use mongodb-backup-restore), mongosh scripting beyond the embedded shell
  (use mongodb-expert or mongodb-mongosh).
tags:
  - mongodb
  - compass
  - gui
  - schema-analysis
  - aggregation
  - explain-plan
  - index-management
  - performance
  - nlq
  - data-modeling
keywords:
  - mongodb compass
  - compass schema analysis
  - compass aggregation builder
  - compass explain plan
  - compass nlq
  - mongodb gui
  - compass index management
  - compass performance advisor
  - compass data modeling
  - compass pipeline builder
  - compass visual explain
  - compass natural language query
  - mongodb desktop client
  - compass documents tab
  - compass embedded shell
  - compass plugins
  - compass anti-patterns
  - compass isolated edition
  - compass readonly edition
  - compass connection favorites
  - compass ER diagram
  - compass AI assistant
  - compass autoCompact
whenToUse:
  - User asks how to use, configure, or troubleshoot MongoDB Compass
  - Schema analysis: sampling, field type distributions, interactive query building
  - Aggregation pipeline builder: stage view, focus mode, export to language
  - Explain plan: COLLSCAN vs IXSCAN diagnosis, SORT stage, sharded cluster plans
  - Index management: create, hide, drop, TTL, partial, wildcard, Atlas Search indexes
  - Performance Insights or Atlas Performance Advisor recommendations in Compass
  - Natural language query (NLQ) / AI-powered query generation
  - Data import (JSON/CSV) or export via the Compass GUI
  - Data modeling ER diagrams — generating and exporting from collections
  - Compass Isolated Edition for air-gapped or security-restricted environments
  - Compass plugin architecture and extensibility questions
  - Production anti-patterns: large sample sizes, explain on unfiltered collections, JSON view replace risk
whenNotToUse:
  - MongoDB driver API or programmatic query construction — use mongodb-developer or mongodb-expert
  - Deep query optimization requiring system.profile analysis — use mongodb-query-performance
  - Atlas cluster configuration, networking, or billing — use mongodb-atlas-expert
  - mongodump / mongorestore / mongoimport / mongoexport CLI tools — use mongodb-backup-restore
  - mongosh scripting beyond what the embedded shell covers — use mongodb-expert or mongodb-mongosh
related_skills:
  - mongodb-expert
  - mongodb-atlas-expert
  - mongodb-indexes-deep
  - mongodb-query-performance
  - mongodb-aggregation-pipeline
  - mongodb-schema-design
  - mongodb-performance-troubleshooting
  - mongodb-mongosh
---

# MongoDB Compass — Expert Reference

MongoDB Compass is the official, free, source-available GUI for MongoDB. It provides visual tools for querying, aggregating, analyzing, and managing MongoDB data without requiring command-line expertise, while still exposing an embedded mongosh shell for power users. Current stable release: **1.49.8** (May 27, 2026).

## When to Use This Skill

- User asks how to use, configure, or troubleshoot MongoDB Compass
- Questions about schema analysis, explain plans, aggregation pipeline building, or index management in a GUI context
- Advising on Compass editions for restricted or air-gapped environments
- Evaluating query performance visually via explain plan trees
- Using NLQ / AI-powered query generation in Compass
- Compass plugin development or extensibility questions
- Production safety guidance: what not to do with Compass against live clusters
- Data modeling ER diagrams in Compass
- Importing or exporting data via the Compass GUI

## When NOT to Use This Skill

- Questions about the MongoDB **driver API** or programmatic query construction → use [[mongodb-expert]] or [[mongodb-developer]]
- Deep query optimization requiring profiler analysis or `system.profile` → use [[mongodb-query-performance]]
- Atlas-specific cluster configuration, networking, or billing → use [[mongodb-atlas-expert]]
- `mongodump` / `mongorestore` / `mongoimport` / `mongoexport` CLI tools (not Compass GUI) → use [[mongodb-backup-restore]]
- MongoDB shell (`mongosh`) scripting beyond what the embedded shell covers → use [[mongodb-expert]]

---

## 1. Editions and Connection Management

### 1.1 Editions

Compass ships in **two active editions** (Readonly Edition is being deprecated):

| Feature | Compass (Full) | Compass Isolated |
|---|---|---|
| CRUD operations | Yes | Yes |
| Queries and aggregations | Yes | Yes |
| Index create/delete | Yes | Yes |
| Visual explain plans | Yes | Yes |
| Schema analysis | Yes | Yes |
| Real-time server stats | Yes | Yes |
| Document validation rules | Yes | Yes |
| Kerberos / LDAP / x.509 auth | Yes | Yes |
| Embedded mongosh shell | Yes | Yes |
| AI / NLQ features | Yes | No |
| Error reporting & usage telemetry | Yes | No |
| Automatic updates | Yes | No |
| External network requests | Yes | No (MongoDB only) |

**Compass (Full)**: The standard edition with all features including AI-powered NLQ, automatic updates, and telemetry. Free and source-available.

**Compass Isolated Edition**: Designed for air-gapped or high-security environments. All network connections except the MongoDB server are blocked — no telemetry, no AI features, no auto-update checks, no additional firewall configuration required. Use when data residency or network egress policies prohibit external calls.

**Compass Readonly Edition (DEPRECATED)**: Historically limited to read operations. Will be removed in a future release. To achieve read-only behavior in the current edition:
1. Assign users the built-in `read` role at the database level in MongoDB.
2. Enable the `readOnly` option in Compass Settings.

> Warning: The `readOnly` Compass setting only hides write-operation UI elements; it does not enforce restrictions at the driver level for shell commands typed in the embedded mongosh.

### 1.2 Connection String Builder

Compass provides a visual connection form that builds connection strings without manual URI syntax knowledge:
- **General tab**: hostname, port, authentication (username/password, X.509, LDAP, Kerberos, AWS IAM, OIDC)
- **TLS/SSL tab**: CA certificate, client certificate/key, allow invalid hostnames
- **Proxy/SSH tab**: SOCKS5 proxy, SSH tunnel configuration
- **Advanced tab**: replica set name, read preference, authentication database, server selection timeout, `directConnection` flag

The built connection string is displayed and editable directly for power users who prefer URI syntax.

### 1.3 Connection Favorites and Color Coding

Save any connection as a **favorite** for quick access:
- Favorites always appear at the top of the connections sidebar.
- Each favorite can be assigned a **color label**. When connected, that color becomes the background of all tabs belonging to that connection — making it immediately clear which environment (dev/staging/prod) you are on.
- Favorites can be edited (name, color, credentials) from the connections sidebar context menu (⋯ icon).
- Favorites are stored with credentials in the OS keychain (macOS Keychain / Windows Credential Manager / GNOME Keyring on Linux).
- Import/export favorites via JSON for team sharing or backup.
- As of v1.44.5, you can edit name, color, and favorite status while actively connected.

### 1.4 Multiple Simultaneous Connections

Since Compass 1.36+, you can connect to multiple MongoDB deployments simultaneously in separate tabs, each color-coded by their favorite label.

### 1.5 Key URI Parameters (Advanced Tab)

The **Advanced tab** of the connection form exposes these commonly needed URI parameters:

| Parameter | Where to set | Purpose |
|---|---|---|
| `readPreference` | Advanced tab | primary / primaryPreferred / secondary / secondaryPreferred / nearest |
| `replicaSet` | Advanced tab | Replica set name for discovery |
| `authSource` | Advanced tab | Override authentication database |
| `tls` / `tlsAllowInvalidCertificates` | TLS/SSL tab | Enable TLS; allow self-signed certs in dev |
| `serverSelectionTimeoutMS` | Advanced tab | Increase when connecting over VPNs with latency |
| `directConnection` | Advanced tab | Connect to a single node without replica set discovery |

---

## 2. Schema Analysis

### 2.1 Overview

The **Schema tab** infers the shape of a collection by sampling documents and presenting interactive visualizations of field types, value distributions, and cardinality — without writing any code.

### 2.2 Sampling Mechanics

- Default sample size: **1,000 documents** drawn using MongoDB's `$sample` aggregation operator.
- Sampling works over the **entire collection** or a **filtered subset** when a query is entered in the query bar.
- A random, non-replacement sample is used; results approximate full-dataset analysis for most distributions.
- To increase the sample size beyond 1,000, go to **Compass Settings → General** and change the **"Sample Size"** field (default 1000). The query bar's **Options → MAX TIME MS** controls the query execution timeout (default 60,000 ms) — a separate setting that does not affect sample size.
- Compass shows a warning when the collection has > 1,000 documents, indicating results reflect only the sampled subset.

### 2.3 Field Type Distribution

For each field, Compass shows:
- **Single data type**: type name with min/max/mean statistics.
- **Multiple data types**: percentage breakdown pie/bar (e.g., 20% int32, 80% string) — useful for spotting type inconsistencies in schemaless collections.
- **Missing/undefined**: percentage of documents that do not contain the field at all — critical for identifying optional vs. required fields.
- **Nested documents and arrays**: expandable to show nested field analysis, plus min/max/average array lengths.

### 2.4 Visualization Types by Field Type

| Field Type | Visualization |
|---|---|
| String (entirely unique) | Random sample values with refresh |
| String (low cardinality) | Graded bar chart: frequency per distinct value |
| String (duplicates) | Frequency histogram |
| Integer / Float | Value histogram with bucket ranges |
| Date / ObjectId | Timeline (first–last), day-of-week distribution, time-of-day distribution |
| Boolean | True/false percentage bar |
| GeoJSON / [lng, lat] | Interactive map with point clustering; circle-draw filter tool |
| Array | Expandable nested fields; array length min/max/avg |
| Embedded document | Expandable nested field analysis |

### 2.5 Interactive Query Building from Schema

Clicking on chart values generates query filter predicates automatically:
- Click a bar in a string histogram → adds `{"field": "value"}` to the query bar.
- Click+drag over a numeric histogram range → adds `{"field": {$gte: X, $lte: Y}}`.
- Draw a circle on a geo map → adds a `$geoWithin / $geometry` polygon filter.
- Shift+click for multi-select; multiple fields combine with `$and`.

This makes schema exploration a fast path to building initial queries before moving to the Documents or Aggregations tab.

### 2.6 Use Cases

1. **Data quality assessment**: spot missing fields, unexpected type mixing, outlier values.
2. **Cardinality analysis**: determine selectivity before creating indexes.
3. **Range identification**: find min/max for numeric bounds and TTL candidates.
4. **Index candidate identification**: high-cardinality fields with frequent query patterns.
5. **Data modeling validation**: verify that actual data conforms to intended schema.
6. **Geographic data exploration**: visualize point distributions for location-based collections.

### 2.7 Schema Export

Use the **Schema Export** feature (linked from the Schema tab) to export the inferred schema as JSON for documentation, sharing with teams, or importing into other tools.

---

## 3. Aggregation Pipeline Builder

### 3.1 Overview

The **Aggregations tab** provides a visual, stage-by-stage builder for MongoDB aggregation pipelines. Each stage displays a live preview of its output from sampled data, making it easy to iterate on complex transformations.

### 3.2 Pipeline Creation Modes

**Stage View Mode** (default): Visual pipeline editor. Each stage appears as a card with:
- Stage type dropdown
- Stage configuration editor with syntax highlighting and autocomplete
- Output preview panel showing up to 10 sampled documents from the stage's output

**Stage Wizard** (within Stage View): Click the wand icon to get templates for common stages: `$group`, `$lookup`, `$match`, `$project`, `$sort`. The wizard generates boilerplate code to fill in.

**Focus Mode** (within Stage View): Edit one stage at a time with a full-height view showing Stage Input, editor, and Stage Output side by side. Ideal for complex or deeply nested stages. Keyboard shortcuts: `Cmd+Shift+A` (add stage after), `Cmd+Shift+B` (add stage before), `Cmd+Shift+9/0` (navigate between stages).

**Text View Mode**: Raw text editor accepting full pipeline JSON/EJSON syntax with real-time linting. Toggle the `</>` switch to enter this mode.

### 3.3 Stage Management

- **Add stage**: Click `+ Add Stage` at the bottom, or `+` above any existing stage card.
- **Toggle stage on/off**: Use the toggle switch on the stage card header to include/exclude a stage without deleting it — useful for A/B testing pipeline behavior.
- **Reorder stages**: Drag the stage card header to a new position.
- **Delete stage**: Click the trash icon on the stage card.
- **Resize stage editor**: Drag the stage card border to adjust width.

### 3.4 Stage Preview

- Each stage previews up to **10 randomly sampled documents** from the stage output.
- Expand all fields with "Output Options" → "Expand all fields".
- `$merge` and `$out` stages display a warning before execution since they modify collection data.

### 3.5 Atlas Search Stages

When connected to a MongoDB Atlas cluster, additional stages become available in the stage dropdown:
- `$search` — Full-text Atlas Search
- `$searchMeta` — Search metadata aggregation

### 3.6 Export Pipeline to Language

Click the **Export to Language** button to generate application-ready code in:
- JavaScript (Node.js)
- Python
- Java
- C# (.NET)
- Ruby
- Go
- Rust
- PHP

The generated code includes the driver boilerplate (collection reference, pipeline array, cursor iteration) so it can be dropped directly into an application.

### 3.7 Saved Pipelines

- **Save a pipeline**: Click the Save button to name and save the pipeline for later use.
- **Open saved pipelines**: Load previously saved pipelines from the pipeline list.
- Saved pipelines are stored locally in Compass.
- Tip: save in-progress pipelines before closing Compass; unsaved pipelines are lost on exit.

### 3.8 Running and Exporting Results

- Click **Run** (top-right) to execute the pipeline against the collection.
- Results are shown in a document view.
- Use **Export Aggregation Results** to save results as JSON or CSV.

### 3.9 Explain Plan for Pipelines

From the Aggregation Pipeline Builder, click **Explain** to view the explain plan for the pipeline, including stage-level execution statistics. See Section 4 for explain plan details.

---

## 4. Explain Plan Visualizer

### 4.1 Overview

The **Explain Plan** (accessible from both the Documents query bar and the Aggregation Pipeline Builder) visualizes how MongoDB executes a query or pipeline, helping identify performance bottlenecks.

### 4.2 View Formats

**Visual Tree View** (default): Each execution stage appears as a clickable node in a hierarchical tree. Click any node to see detailed execution statistics for that stage. This is the primary view for understanding query flow.

**Raw Output View**: The full explain document shown as formatted JSON — equivalent to running `db.collection.explain("executionStats")` in the shell. Switch between views at the top of the explain modal.

> Note: Visual Tree view is **not available** for vector search queries; use Raw Output view instead.

### 4.3 Summary Metrics

The explain plan header shows:
- **Execution time** (ms)
- **Returned documents** (nReturned)
- **Examined documents** (totalDocsExamined)
- **Examined index keys** (totalKeysExamined)

The ratio of examined documents to returned documents is the key efficiency signal. A ratio of 1:1 is ideal; 1000:1 means 1000 documents were scanned per returned document (classic full-collection scan inefficiency).

### 4.4 Stage Color Coding and Key Stage Types

| Stage | Color | Meaning |
|---|---|---|
| COLLSCAN | Red | Full collection scan — no index used. A warning sign for production queries. |
| IXSCAN | Green | Index scan — query used an index. Efficient. |
| FETCH | — | Retrieve full documents from storage after index lookup |
| SORT | Orange | In-memory sort — no sort index. May be memory-intensive on large result sets. |
| PROJECTION | — | Field projection applied |
| LIMIT / SKIP | — | Limit/skip applied |
| COUNT | — | Count operation |
| SHARD_MERGE | — | Merge results from multiple shards (sharded clusters) |
| SHARDING_FILTER | — | Filter out orphaned documents on a shard |

### 4.5 Sharded Cluster Plans

For sharded collections, the explain plan includes:
- A `SHARD_MERGE` node at the top.
- Per-shard sub-plans showing which shards were accessed and their individual execution stats.
- The "winning plan" for each shard.
- Use Raw Output to see the full `shards` array with per-shard `executionStats`.

### 4.6 How Compass Explain Differs from Shell Explain

Running `db.collection.explain("executionStats")` in the shell and clicking Explain in Compass produce equivalent data. Key differences:
- Compass runs explain at `executionStats` verbosity by default (executes the query, collects full stats).
- Compass omits `$merge` and `$out` from pipeline explains (those stages are excluded before running).
- Compass adds a `maxTimeMS` cap (configurable since v1.49.6) to prevent explain operations from running indefinitely on large collections.
- The Visual Tree is a Compass-specific rendering of the raw explain JSON; Raw Output is identical to what the shell returns.
- The shell allows `allPlansExecution` verbosity (shows rejected plan stats); this is only available via Raw Output in Compass.

### 4.7 Workflow: Explain-Driven Index Creation

1. Run explain on a slow query.
2. Identify `COLLSCAN` stage in the tree (shown in red).
3. Note the fields in the query filter and sort.
4. Switch to the **Indexes tab** (Section 5).
5. Create a compound index matching the query shape (filter fields first, sort fields after).
6. Re-run explain → verify `COLLSCAN` replaced by `IXSCAN`.
7. Check nReturned ≈ totalKeysExamined for index efficiency.

---

## 5. Index Management

### 5.1 Indexes Tab Overview

The **Indexes tab** (per collection) displays all indexes with:

| Column | Description |
|---|---|
| Name and Definition | Index name and key fields with sort order |
| Type | Regular, text, geospatial (2dsphere/2d), hashed, wildcard |
| Size | Index size in bytes on disk |
| Usage | Number of query operations that used this index since last mongod restart |
| Properties | unique, sparse, partial, TTL, hidden, collation |

> Important: Usage statistics reflect only the node Compass is currently connected to. For cluster-wide stats, run `db.collection.aggregate([{$indexStats: {}}])` or use the `$indexStats` stage on each replica set member.

### 5.2 Creating Indexes

Click **Create Index** → configure:

**Field selection**: Choose field from dropdown (autocompleted from collection schema) or type manually (including `field.$**` for wildcard sub-document indexing).

**Index type per field**:
- Ascending (1)
- Descending (-1)
- 2dsphere (geospatial)
- Text

**Compound indexes**: Click the `+` icon to add multiple fields to a single index definition.

**Index options**:
| Option | Purpose |
|---|---|
| Unique | Prevent duplicate values across documents |
| TTL | Auto-expire documents after N seconds; enter expiry in seconds |
| Partial filter expression | Index only documents matching a filter expression |
| Sparse | Exclude documents where the indexed field is missing |
| Custom collation | Language-specific string comparison rules |
| Wildcard projection | `field.$**` to index all sub-fields of an embedded document |
| Index name | Custom name (default: auto-generated from field names) |

**Atlas Search indexes**: Manageable from Compass when connected to Atlas M10+ or local deployment running MongoDB 7.0+.

**Atlas Vector Search indexes**: Create and manage vector indexes for semantic/AI search workloads from Compass.

### 5.3 Hiding and Unhiding Indexes

MongoDB supports **hidden indexes** — indexes that exist and are maintained on writes but are invisible to the query planner. This allows you to evaluate the impact of removing an index without permanently dropping it:

1. Hover over the index row → click the closed-eye icon.
2. Confirm the action.
3. Monitor query performance with the index hidden.
4. Unhide (re-open eye) if queries degrade, or drop the index if performance is unchanged.

> TTL indexes that are hidden continue to expire documents — only query planning is affected.

### 5.4 Dropping Indexes

1. Click the trash can icon for the index.
2. Enter the exact index name in the confirmation dialog.
3. Click **Drop**.

The `_id` index cannot be dropped. Never drop indexes on live production without first hiding them to test impact (see Section 12, Anti-Patterns).

### 5.5 Index Usage Statistics and Redundant Index Detection

Use the Usage column to identify:
- **Zero-usage indexes**: Never used since last restart; candidates for dropping (reduces write overhead).
- **Heavily-used indexes**: Confirm they support your most critical query patterns.
- **Redundant indexes**: If index A covers all fields of index B, index B is redundant. Compass's **Performance Insights** (Section 6) can flag "too many indexes" but does not automatically detect prefix-redundant indexes — use `$indexStats` aggregation or Atlas Performance Advisor for that.

### 5.6 Index Build Progress

For large collections, creating an index is a background operation. Compass displays index build progress in the Indexes tab. In-progress indexes appear with a progress indicator. Do not disconnect or kill the mongod process during an index build.

### 5.7 Queryable Encryption Limitation

Do not create regular indexes on encrypted fields. Use the `__safeContent__` field for Queryable Encryption equality queries. Compass enforces this restriction.

---

## 6. Performance Insights and Atlas Performance Advisor

### 6.1 Performance Insights (Built-in Compass Feature)

**Performance Insights** is an automatic Compass feature that appears when Compass detects optimization opportunities, without requiring Atlas connectivity:

| Scenario Detected | Recommendation |
|---|---|
| Query/aggregation without an index | Create an index to support the operation |
| `$lookup` stage in aggregation | Embed related data to avoid `$lookup` |
| `$text` or `$regex` query | Use Atlas Search for full-text search |
| Too many collections (>500) | Reduce collection count |
| Array fields with unbounded growth | Avoid unbounded arrays |
| Individual documents > 16MB threshold patterns | Break into separate collections |
| Too many indexes on a collection | Review and remove unused indexes |

Insights appear contextually as banners or tooltips near the relevant UI element (e.g., in the Aggregations tab when a `$lookup` stage is added). Apply insights early in development when schema changes are less disruptive.

### 6.2 Atlas Performance Advisor (Atlas-Connected Compass)

When Compass is connected to a **MongoDB Atlas** cluster, additional performance guidance is surfaced:

- **Slow Query Detection**: Atlas monitors queries exceeding 100ms (configurable) and groups them by query shape.
- **Index Recommendations**: Atlas calculates an "Impact" score for each suggested index based on: average query targeting (docs scanned per doc returned), query frequency, and execution time. High-impact indexes are listed first.
- **Index Ranking**: Each recommendation includes Average Query Targeting (AQT) — lower is better. An AQT of 1 means every scanned document was returned; AQT of 1,000 means heavy over-scanning.
- **One-Click Index Creation**: In Atlas Data Explorer (web UI), click "Create Index" from the Performance Advisor recommendation. In Compass, use the recommendation as guidance to create the index via the Indexes tab.
- **Duplicate Index Detection**: The Performance Advisor identifies prefix-redundant indexes and suggests consolidation.
- **Supported Query Types**: As of 2025, recommendations cover regex, negation operators (`$ne`, `$nin`, `$not`), `$count`, `$distinct`, and `$match`.

### 6.3 Accessing Performance Advisor

In Atlas Data Explorer (web): Database → Collection → Performance Advisor tab.

In Compass (connected to Atlas): The Performance Insights panel surfaces recommendations contextually. For the full Atlas Performance Advisor interface, use the Atlas web UI.

### 6.4 Workflow: Slow Query Remediation

1. Enable Performance Insights in Compass (automatic).
2. Run typical application queries via Compass query bar or aggregation builder.
3. Observe Performance Insights banners.
4. Switch to Indexes tab to create the recommended index.
5. Re-run the query and compare explain plan before/after.
6. For Atlas clusters: check Atlas UI Performance Advisor for cluster-wide slow query analysis across all cluster members.

---

## 7. CRUD and Documents Tab

### 7.1 Documents Tab Overview

The **Documents tab** is the primary interface for reading and modifying collection data. It includes:
- Query bar (filter, projection, sort, skip, limit, maxTimeMS, hint)
- Three document view modes
- Insert document button
- Export query results button
- Document count

### 7.2 Document View Modes

**List View** (default): Documents shown as formatted key-value pairs with expand/collapse for nested objects and arrays. The most readable view for document inspection.

**JSON View**: Documents rendered as full JSON/EJSON objects with proper MongoDB extended type encoding (ObjectId, Date, BinData, etc. shown in EJSON format). Editing in JSON view performs a `findOneAndReplace` — it replaces the entire document.

**Table View**: Documents displayed as rows with fields as columns. Useful for collections with flat, consistent schemas. As of v1.49.0, column widths are resizable. Editing in table view performs `findOneAndUpdate` — modifies only changed fields.

> Critical distinction: JSON view replace vs. List/Table view update. Editing in JSON view will **replace the document** (findOneAndReplace), which can wipe fields not shown in the editor. List and Table view editing is surgical (findOneAndUpdate).

### 7.3 In-Place Editing

Double-click any field value to enter edit mode. Changes are tracked and shown with change indicators. Click the checkmark to apply or the X to cancel. Compass generates the appropriate update operation:
- In List/Table view: `findOneAndUpdate` with `$set` for changed fields
- In JSON view: `findOneAndReplace` with the full document

### 7.4 Document Insertion

**JSON Mode**: Paste one or multiple documents as a JSON array or single object.

**Field-by-Field Editor**: Add fields interactively, choosing BSON type for each field. Supports nested documents and arrays.

### 7.5 Array and Subdocument Expansion

In List view, arrays and embedded documents are expandable inline with expand/collapse toggles. Arrays show their index and element type. ObjectIds auto-wrap when pasted (since v1.49.0).

### 7.6 Projection Support

The **Project** field in the query bar accepts MongoDB projection syntax:
- `{field: 1}` — include only specified fields
- `{field: 0}` — exclude specified fields
- Projection helps load large documents faster and reduces noise in the view

### 7.7 Multi-Select Delete

Select multiple documents using checkboxes, then click **Delete Selected**. Compass runs `deleteMany` for the selected `_id` values. Use with caution — operation is irreversible.

### 7.8 Schema Validation Rules (Validation Tab)

The **Validation tab** (a separate tab adjacent to Documents, not inline editing) manages collection-level schema validation rules:
- Supports `$jsonSchema` syntax and MQL query operator syntax
- Configure `validationLevel`: `strict` (all inserts/updates) or `moderate` (new docs only)
- Configure `validationAction`: `error` (reject) or `warn` (accept with warning)
- **Generate Rules** button: Compass analyzes existing data and generates suggested `$jsonSchema` rules
- **Preview documents** button: shows sample documents matching the current validation expression
- Validation editor provides autocomplete for fields and keywords

---

## 8. Natural Language Query (NLQ)

### 8.1 Overview

MongoDB Compass includes an **AI-powered natural language query interface** that generates MongoDB query syntax and aggregation pipelines from plain English prompts. Introduced as an experimental feature, it remains labeled experimental in official documentation; v1.49.0 added tool-calling capability and removed the preview badge from the AI Assistant, but always review generated queries before executing.

### 8.2 Enabling NLQ

NLQ is enabled via **Settings → Use Generative AI** toggle. It requires internet connectivity (not available in Compass Isolated Edition).

### 8.3 Generating Queries

1. Navigate to the Documents tab.
2. Click **Generate query** button → the Natural Language Query Bar appears.
3. Type a prompt (e.g., "Which movies were released in 2000?").
4. Press Enter → Compass generates and populates a filter query in the query bar.
5. Review the generated syntax carefully before executing.

Example prompt → generated query pairs:

| Prompt | Generated Filter |
|---|---|
| `Which movies have a "PG" rating?` | `{"rated": "PG"}` |
| `Movies with runtime greater than 90 minutes` | `{"runtime": {$gt: 90}}` |
| `Movies with David Mamet in the writers array` | `{"writers": "David Mamet"}` |

### 8.4 Generating Aggregation Pipelines via NLQ

Prompts that require aggregation (grouping, joining, multi-stage transforms) automatically redirect to the **Aggregations tab** with a generated pipeline. A pop-up notifies when aggregation stages are needed.

### 8.5 Privacy and Data Handling

**What is sent to third parties**: The text of your prompts and details about your MongoDB collection schemas (field names, types — not actual document values) are sent to **Microsoft Azure OpenAI** for processing.

**What is NOT sent**: Your actual document data is never transmitted. Data is not stored on third-party systems and is not used to train AI models. Feedback you provide is also not used for model training.

### 8.6 Supported Input Types

- Natural language descriptions
- SQL queries (pasted SQL is translated to MongoDB syntax)
- Application code snippets (query code from Node.js, Python, etc. can be pasted and interpreted)

### 8.7 Limitations and Caveats

- **Experimental accuracy**: NLQ is explicitly labeled experimental; results may be inaccurate. Always review generated queries before running, especially writes.
- **Complex queries**: Multi-stage pipelines, deeply nested conditions, or domain-specific queries may produce incorrect results.
- **MAX TIME MS**: Complex generated pipelines may require increasing `MAX TIME MS` to avoid timeouts.
- **Review before executing**: NLQ in the Documents tab generates filter queries; the risk is running a generated filter with destructive intent (e.g., "Delete Selected" after filtering). Always verify the generated query matches your intent before acting on results.
- **Schema required**: NLQ relies on field names from the inferred schema; works best when schema analysis has been run or schema is stable.

### 8.8 Compass AI Assistant (Intelligent Assistant)

Since v1.49.0, Compass includes a broader **AI Assistant** (chat interface) powered by the mongodb-chat-2 model that can:
- Answer questions about Compass features
- Suggest query optimizations
- Help debug aggregation pipelines
- Provide schema design guidance
The assistant is accessible from the Assistant panel (speech bubble icon). Tool-calling capability allows the assistant to execute Compass operations directly.

### 8.9 Comparison: Compass NLQ vs. Atlas Data Explorer NLQ

| Aspect | Compass NLQ | Atlas NLQ (Data Explorer) |
|---|---|---|
| Access | Desktop app (Compass) | Browser (Atlas web UI) |
| Connectivity | Any MongoDB (local, Atlas, any) | Atlas clusters only |
| Generates | Filter queries + aggregations | Filter queries + aggregations |
| Privacy model | Prompt + schema → Azure OpenAI | Prompt + schema → Azure OpenAI |
| AI Assistant | Compass AI Assistant (chat) | Atlas AI chat |
| Availability | Free, Compass required | Atlas subscription required |

---

## 9. Data Import and Export

### 9.1 Importing Data

Compass supports importing documents directly into a collection from the Documents tab:

- **Supported formats**: JSON and CSV
- **Access**: Documents tab → **Add Data** → **Import File**
- JSON files must contain an array of documents or newline-delimited JSON (NDJSON)
- CSV files: first row treated as field names; Compass infers BSON types but allows manual override per column
- Large imports (>10k documents): prefer `mongoimport` CLI for reliability and performance — Compass import holds the full file in memory

### 9.2 Exporting Data

Export query results or full collections:

- **Export query results**: Documents tab → run a filter → **Export Collection** → choose JSON or CSV, include/exclude fields
- **Export aggregation results**: Aggregations tab → Run pipeline → **Export** → JSON or CSV
- **Full collection export**: Documents tab with empty filter `{}` → Export Collection

> For large collections, use `mongoexport` or `mongodump` CLI tools rather than Compass — Compass export loads results into memory before writing, which can OOM on very large collections.

### 9.3 Import/Export Limitations

- No binary (BSON) import/export from the GUI — use `mongodump` / `mongorestore` for binary-format backups
- Compass CSV export flattens nested documents using dot-notation keys; arrays are serialized as strings
- No progress tracking for very large exports — Compass may appear frozen; check mongod logs to verify progress

---

## 10. Compass Plugins and Extensibility

### 10.1 Architecture: Electron + React

MongoDB Compass is an **Electron** application (cross-platform desktop via Chromium + Node.js). The UI is built with **React**, and the codebase is a multi-package monorepo at `github.com/mongodb-js/compass`.

Each major Compass feature is a separate npm package (internal plugin):
- `@mongodb-js/compass-crud` — Documents tab
- `@mongodb-js/compass-schema` — Schema tab
- `@mongodb-js/compass-indexes` — Indexes tab
- `@mongodb-js/compass-aggregations` — Aggregations tab
- `@mongodb-js/compass-query-bar` — Query bar
- `@mongodb-js/compass-schema-validation` — Validation tab
- `@mongodb-js/compass-collection` — Collection-level plugin host
- `@mongodb-js/compass-instance` — Instance-level plugin host

### 10.2 `@mongodb-js/compass-components`

The `@mongodb-js/compass-components` package is the shared UI component library for Compass. It wraps **LeafyGreen** (MongoDB's React design system) components and provides consistent UI primitives (buttons, modals, table rows, badges, toasts, etc.) used across all Compass plugins.

Using compass-components ensures visual consistency with Compass's appearance and simplifies keeping up with design system updates — a single dependency update propagates across all plugins.

### 10.3 Third-Party Plugin Development (Deprecated)

MongoDB previously supported third-party Compass plugins via a public plugin API. The workflow used `compass-plugin` as a khaos boilerplate template generating:
- A React component for UI
- Reflux stores and actions for state management
- Test setup with Enzyme
- Storybook for component prototyping

> Note: The external plugin API has been largely internalized as Compass evolved into a more monolithic Electron app. Third-party plugin development is no longer actively promoted by MongoDB. The plugin architecture exists primarily for MongoDB's own internal package decomposition.

### 10.4 Custom Themes

Compass supports light and dark mode. Custom theming beyond the built-in modes is not officially supported via a public API.

### 10.5 Compass as a Development Platform

For teams building custom MongoDB management tools, consider:
- Embedding mongosh programmatically via `@mongosh/node-mongosh-main`
- Using `@mongodb-js/mongodb-data-service` for the driver connection layer
- Forking Compass (Apache 2.0 licensed) and customizing

### 10.6 Compass Shell (mongosh)

Compass embeds **mongosh** (the modern MongoDB Shell, a JavaScript environment). Access via:
- Clicking `>_` next to the connection name in the sidebar
- Clicking `>_ Open MongoDB shell` in the top-right of any collection tab

The shell is already connected to the current deployment. Use it for operations not available in the GUI (index creation with custom options, `db.adminCommand()`, profiler control, etc.).

---

## 11. Data Modeling (ER Diagrams)

### 11.1 Overview

Since 2025, Compass includes a **Data Modeling** feature that generates entity-relationship (ER) diagrams from existing collections. This is a visual tool for understanding, documenting, and planning MongoDB schema structure.

### 11.2 Generating a Diagram

1. Open the **Data Modeling** section (top-level sidebar).
2. Select collections to include.
3. Enable **Auto-infer relationships** to have Compass analyze indexed fields containing references to other collections.
4. Compass generates an ER diagram with collection nodes and relationship arrows.

### 11.3 Diagram Features

- Collapse/expand collections in the diagram for overview and detail views
- **Diagram Overview drawer**: minimap for navigating large diagrams
- Relationship cardinality options: one-to-one, one-to-many, many-to-many
- Modify the diagram without affecting actual data — purely a planning artifact
- Add, remove, or relink collections in the diagram
- Sort persistence: diagram layout saved across sessions (since v1.49.5)

### 11.4 Export Formats

- **Image**: PNG/SVG for documentation
- **JSON**: Machine-readable model definition
- **.mdm file**: Compass-native format that can be reopened in Compass for continued editing

---

## 12. Anti-Patterns

### 12.1 Connecting to Primary in Production Without Read Preference

**Anti-pattern**: Opening Compass pointed at a production primary with default read preference (`primary`) and running schema analysis, large queries, or explain plans.

**Why it's harmful**: Schema analysis runs `$sample` aggregation on the primary; large sample sizes compete with application read workload. Full collection scans initiated by explain (especially `allPlansExecution`) can cause latency spikes.

**Fix**: In Advanced Connection Options, set `readPreference=secondaryPreferred` when connecting to production replica sets. This routes Compass queries to secondaries, protecting the primary from analysis traffic.

### 12.2 Large Sample Sizes Causing OOM

**Anti-pattern**: Increasing the schema analysis sample size to very high values (e.g., 100,000+) on a machine with limited RAM.

**Why it's harmful**: `$sample` with a large N on a big collection requires loading many documents into memory. Compass itself runs in Electron (Chromium renderer process) with memory limits. Very large samples can cause Compass to become unresponsive or crash.

**Fix**: Keep sample size at 1,000–5,000 for exploratory work. Use a query filter to narrow the analysis to a meaningful subset (e.g., recent documents, specific tenant) rather than increasing sample size globally.

### 12.3 Running Explain on Large Collections Without a Query Filter

**Anti-pattern**: Clicking **Explain** on an unfiltered query (`{}`) against a multi-million document collection.

**Why it's harmful**: Explain at `executionStats` verbosity actually executes the query. A `COLLSCAN` on a large unfiltered collection can take minutes, block the tab, and consume significant memory. On production primaries, this can cause real latency impact.

**Fix**: Always add a narrow filter before running Explain. If you need to analyze the full-collection scan behavior, use `db.collection.explain("queryPlanner")` in the shell (planning only, no execution) or add `maxTimeMS` to cap the operation.

### 12.4 Leaving Compass Connections Open (Connection Limit Impact)

**Anti-pattern**: Opening many Compass instances or connections to Atlas clusters and leaving them idle overnight or across weekends.

**Why it's harmful**: Each Compass connection counts against the Atlas cluster's connection limit. As a rough guide, M0 clusters allow ~500 connections, M10 ~1,500, M20/M30 ~3,000 — but limits vary by region and Atlas version; verify current limits in the [Atlas connection limits documentation](https://www.mongodb.com/docs/atlas/reference/faq/connection-changes/). Multiple team members with multiple Compass tabs each consuming connections can exhaust the pool.

**Fix**: Close Compass (or disconnect unused connections) when not in use. Use a single connection per cluster per user. For Atlas Free Tier development, be especially careful — 3-5 Compass connections per developer can exhaust limits.

### 12.5 Relying on Compass Usage Stats Alone for Index Decisions

**Anti-pattern**: Using only the Compass Indexes tab Usage column to decide which indexes to drop.

**Why it's harmful**: Usage counters reset on every mongod restart. If the node was recently restarted (failover, maintenance), a zero-usage count does not mean the index is never used — it means no queries have used it *since restart*. An index that's used by monthly reporting queries would show zero usage on day one after restart.

**Fix**: Use `$indexStats` aggregation stage which includes `accesses.since` (when stats were reset). Compare against known query patterns and Atlas Performance Advisor recommendations before dropping any index.

### 12.6 Editing Documents in JSON View Accidentally (findOneAndReplace)

**Anti-pattern**: Using JSON view for routine field-value edits.

**Why it's harmful**: Editing in JSON view issues a `findOneAndReplace`, replacing the entire document. If the JSON editor collapses nested fields or you accidentally remove a key, those fields are permanently deleted from the document.

**Fix**: Use **List View** or **Table View** for surgical field edits (they use `findOneAndUpdate`). Only use JSON View for whole-document replacement when that is the intentional operation.

### 12.7 Using Compass on Encrypted Fields Without Understanding Queryable Encryption Limits

**Anti-pattern**: Creating regular indexes on Queryable Encryption (QE) encrypted fields via the Compass Indexes tab.

**Why it's harmful**: Indexing encrypted field values directly leaks frequency information about the encrypted data. MongoDB's QE uses `__safeContent__` for equality query indexes.

**Fix**: Do not create indexes on QE-encrypted fields via the standard Indexes tab. Use `__safeContent__` fields or the dedicated QE index creation workflow.

---

## 13. Real-Time Performance Monitoring

### 13.1 Performance Tab

Access via: connection context menu (⋯) → **Performance**.

Displays real-time charts (powered by `mongostat` and `mongotop` data):

| Metric Panel | What it Shows |
|---|---|
| Operations | Inserts, queries, updates, deletes, commands, getmore — per second |
| Read & Write | Active reads, queued reads, active writes, queued writes |
| Network | Number of current connections |
| Memory | Resident, virtual, mapped memory |
| Hottest Collections | Collections with most operations (from `mongotop`) |
| Slowest Operations | Top slow queries from `db.currentOp()` |

### 13.2 Killing Slow Operations

Click a query in the **Slowest Operations** panel → Operation Details → **Kill Op**. Requires the `killop` privilege action for operations you don't own.

### 13.3 Pause and Resume

The **Pause** button stops display refresh without stopping data collection. Click **Play** to resume. Useful for examining a snapshot of metrics without the display jumping.

### 13.4 Limitations

- Performance data is **unavailable** for Queryable Encryption collections.
- When connected to a `mongos` (sharded cluster), performance data is limited.

---

## References

### Official Documentation
- [MongoDB Compass Overview](https://www.mongodb.com/docs/compass/) — What is Compass, key features
- [Compass Editions](https://www.mongodb.com/docs/compass/editions/) — Full vs. Isolated feature matrix
- [Schema Analysis](https://www.mongodb.com/docs/compass/schema/) — Schema tab, field types, visualizations
- [Sampling](https://www.mongodb.com/docs/compass/current/sampling/) — `$sample` mechanics, default 1,000 docs
- [Aggregation Pipeline Builder](https://www.mongodb.com/docs/compass/create-agg-pipeline/) — Stage modes, wizard, export
- [View Query Performance](https://www.mongodb.com/docs/compass/query-plan/) — Explain plan visual tree, raw output
- [Manage Indexes](https://www.mongodb.com/docs/compass/indexes/) — Create, hide, drop, TTL, wildcard
- [Performance Insights](https://www.mongodb.com/docs/compass/manage-data/performance-insights/) — Built-in optimization recommendations
- [Analyze Slow Queries (Atlas)](https://www.mongodb.com/docs/atlas/analyze-slow-queries/) — Atlas Performance Advisor
- [View Documents](https://www.mongodb.com/docs/compass/documents/view/) — List/JSON/Table view
- [Modify Documents](https://www.mongodb.com/docs/compass/documents/modify/) — findOneAndUpdate vs findOneAndReplace
- [NLQ Enable](https://www.mongodb.com/docs/compass/query-with-natural-language/enable-natural-language-querying/) — Turn on generative AI
- [NLQ Prompt Query](https://www.mongodb.com/docs/compass/query-with-natural-language/prompt-natural-language-query/) — Usage and privacy
- [NLQ Prompt Aggregation](https://www.mongodb.com/docs/compass/query-with-natural-language/prompt-natural-language-aggregation/) — Aggregation via NL
- [Set Validation Rules](https://www.mongodb.com/docs/compass/current/validation/) — $jsonSchema and MQL validation
- [Real-Time Performance](https://www.mongodb.com/docs/compass/performance/) — Performance tab metrics
- [Data Modeling - Generate Diagram](https://www.mongodb.com/docs/compass/data-modeling/generate-diagram/) — ER diagram from collections
- [Favorite Connections](https://www.mongodb.com/docs/compass/current/connect/favorite-connections/) — Color labels, import/export
- [Release Notes](https://www.mongodb.com/docs/compass/current/release-notes/) — Latest: v1.49.8 (May 27, 2026)
- [Export Pipeline Results](https://www.mongodb.com/docs/compass/agg-pipeline-builder/export-pipeline-results/) — Export aggregation output
- [Specify Read Preference](https://www.mongodb.com/docs/compass/settings/specify-read-preference-tags/) — Per-connection read preference

### Related Skills
- [[mongodb-expert]] — Core MongoDB concepts, CRUD, operators
- [[mongodb-atlas-expert]] — Atlas-specific features, clusters, Atlas Search
- [[mongodb-indexes-deep]] — Index types, strategies, compound, partial, sparse, wildcard
- [[mongodb-query-performance]] — Query optimization, profiler, explain output
- [[mongodb-aggregation-pipeline]] — Aggregation stages, operators, pipeline optimization
- [[mongodb-schema-design]] — Document model design patterns, embedding vs. referencing
- [[mongodb-performance-troubleshooting]] — Diagnosing slow queries, profiler, Atlas metrics
