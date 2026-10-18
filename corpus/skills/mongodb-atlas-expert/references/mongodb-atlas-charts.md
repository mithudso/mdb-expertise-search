<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-atlas-expert` hub.** Formerly the standalone `mongodb-atlas-charts` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-atlas-charts
description: >
  MongoDB Atlas Charts reference — chart types, data sources, aggregation pipelines in Charts,
  dashboard layout and filters, embedded charts (unauthenticated and JWT-authenticated SDK),
  the Charts JavaScript SDK, Charts REST API, access control, cost model, and anti-patterns.
  TRIGGER: Atlas Charts; building dashboards in Atlas; embedding charts in a web app; Charts SDK
  (@mongodb-js/charts-embed-dom); JWT filter security for embedded charts; Charts REST API;
  chart types (bar, line, scatter, geo, heatmap, KPI, table, gauge, candlestick); Atlas Charts
  data source setup; dashboard filters; chart alerts; Charts cost and render billing; "how do I
  embed a MongoDB chart"; "Charts authentication"; "multi-tenant chart embed security";
  "drilldown charts"; federated data sources in Charts; Charts access control roles.
  SKIP: Atlas Data Federation itself (not Charts) — use mongodb-atlas-data-federation; SQL/BI
  tools over MongoDB — use mongodb-bi-connector; Grafana or monitoring dashboards — use
  mongodb-monitoring-observability; real-time streaming data visualization — Charts is not
  designed for sub-100ms refresh, recommend a different tool.
category: mongodb
tags: [mongodb, atlas, charts, BI, embedded, dashboards, sdk, jwt, visualization, rest-api]
last_verified: 2026-05-28
version: "1.1.0"
updated: "2026-05-29"
whenNotToUse:
  - Atlas Data Federation queries without Charts — use mongodb-atlas-data-federation
  - SQL/BI tool bridge (Tableau, PowerBI) — use mongodb-bi-connector
  - Grafana/Prometheus monitoring dashboards — use mongodb-monitoring-observability
  - Sub-100ms live refresh / ticker display — Charts is not designed for this use case
related_skills:
  - mongodb-atlas-expert
  - mongodb-atlas-data-federation
  - mongodb-bi-connector
  - mongodb-monitoring-observability
  - mongodb-aggregation-pipeline
---

# MongoDB Atlas Charts

## 1. Atlas Charts Overview

Atlas Charts is MongoDB's built-in business intelligence and data visualization layer, native to the Atlas platform. It requires no separate cluster, no ETL pipeline, and no additional data warehouse — it queries your Atlas collections directly.

### Key characteristics

- **Native to Atlas**: Charts is a managed service within the Atlas UI. You do not provision a separate compute resource; MongoDB runs the rendering layer on your behalf.
- **No driver required**: Charts speaks to your cluster over the same Atlas data-access path used by Data API and Data Federation. You point it at a cluster, choose a collection, and start building.
- **Real-time queries**: Each chart load triggers a live aggregation query against your cluster. Results are not pre-computed unless you enable the optional caching layer.
- **No separate cluster**: Charts does not clone your data. It reads from the cluster you designate as a data source.

For the full pricing and cost breakdown, see [Section 11 — Cost Model](#11-cost-model).

### When not to use Atlas Charts

| Requirement | Better fit |
|---|---|
| Sub-100ms live refresh (ticker, ops metrics) | Grafana + Atlas monitoring panels |
| Row-level security enforced at query time (Atlas RBAC collection rules) | Application-layer query API (GraphQL/REST) that enforces authorization before querying Atlas |
| Complex cross-cluster joins in real time | Atlas Data Federation + dedicated BI tool |
| Streaming / CDC visualization | Atlas Charts is not designed for event-stream display |

---

## 2. Chart Types

Atlas Charts supports a broad set of visualization primitives. Choose the chart type based on the shape of your query output and the story you want to tell.

| Chart type | Best for |
|---|---|
| **Bar / Column** | Comparing discrete categories; grouped or stacked variants for multi-series |
| **Line** | Trends over time; supports multiple series and smooth vs stepped interpolation |
| **Area** | Cumulative or stacked trends; good for part-to-whole over time |
| **Donut / Pie** | Part-to-whole ratios for a small number of categories (≤7 segments) |
| **Scatter** | Correlation between two numeric fields; bubble variant adds a third dimension via point size |
| **Geo / Map** | Plotting GeoJSON Point data, coordinates, or country/region codes on a world map |
| **Heatmap** | Two-dimensional frequency matrix; useful for time-of-day vs day-of-week patterns |
| **KPI / Number** | Single aggregated metric with optional comparison to prior period |
| **Table** | Tabular output with sorting, pagination, conditional formatting |
| **Word Cloud** | Frequency of string values; a quick NLP-adjacent visualization |
| **Gauge** | Progress toward a target; single numeric value on a min-to-max arc |
| **Candlestick** | OHLC financial data |

### Chart builder UI

Each chart has four zones:
1. **Fields panel** (left) — all fields detected in a sample of your collection's documents.
2. **Encoding channels** (center-left) — drag fields into X-axis, Y-axis, Color, Size, etc.
3. **Canvas** (center-right) — live preview, re-rendered on every change.
4. **Query / Filter bar** (top) — optional MQL filter applied before aggregation.

---

## 3. Data Sources

A data source connects Charts to a MongoDB namespace (database + collection) or a higher-level abstraction.

### Direct cluster access

1. In the Charts section of your Atlas project, click **Add Data Source**.
2. Select the cluster, database, and collection.
3. Charts auto-samples up to 1,000 documents to infer field names and types. This sampling is for field discovery only — actual chart queries run against all documents matching your filter.
4. The data source becomes available to all dashboards in the project.

You can add multiple collections as separate data sources and join them inside a chart using `$lookup` in a custom aggregation pipeline.

### Federated data sources (Atlas Data Federation)

Atlas Data Federation can expose:
- **S3 buckets** (JSON, CSV, Parquet, Avro) as queryable collections.
- **Atlas clusters** from other projects or regions.
- **Azure Blob / GCS** (via partner federation connectors).
- **BigQuery** tables via the Atlas BigQuery Connector (adds a federated namespace).

Field discovery for federated sources uses the same 1,000-document sample process as direct cluster sources, but sampling from S3-backed namespaces is slower.

To use federated sources in Charts:
1. Configure a Federated Database Instance in your Atlas project.
2. Add it as a data source in Charts exactly as you would a regular cluster.
3. Charts issues MQL against the federated endpoint; Data Federation translates to S3 Select / BigQuery SQL at the storage layer.

**Caveats**: Federated queries are slower than direct cluster queries. Avoid live-dashboard use cases that require sub-second render times over S3-backed federated sources.

---

## 4. Aggregation Pipeline in Charts

### Query bar

The query bar at the top of the chart builder accepts an MQL filter document (e.g., `{ "status": "open", "priority": { "$gte": 3 } }`). This is applied as a `$match` stage before any aggregation. It is equivalent to the first stage in a pipeline.

### Encoding-driven aggregation

When you drag fields into encoding channels, Charts automatically constructs an aggregation pipeline:
- **Grouping** fields produce a `$group` stage.
- **Metric** fields produce accumulator expressions (`$sum`, `$avg`, `$min`, `$max`, `$count`).
- **Sort** and **limit** controls add `$sort` and `$limit` stages.
- **Date binning** (hour, day, week, month, quarter, year) adds a `$dateToString` or `$dateTrunc` stage.
- **Array unwind** support adds `$unwind` when a field is an array.

### Custom aggregation pipelines

For complex transformations (multi-stage lookups, `$facet`, `$bucket`, `$graphLookup`), switch to **Custom** mode in the chart builder. You write a full pipeline JSON array. The pipeline must emit documents where each top-level field maps to an encoding channel name you define.

```json
[
  { "$match": { "createdAt": { "$gte": { "$date": "2025-01-01T00:00:00Z" } } } },
  { "$group": {
      "_id": { "month": { "$month": "$createdAt" }, "status": "$status" },
      "count": { "$sum": 1 },
      "avgResolutionDays": { "$avg": "$resolutionDays" }
  }},
  { "$sort": { "_id.month": 1 } }
]
```

Custom pipelines bypass the encoding-driven builder — you must manually map output fields to chart encoding channels.

### Calculated fields

Charts supports a limited set of computed fields via the **Add Field** button in the Fields panel (bottom-left of the chart builder):
- **Formula fields**: simple arithmetic between numeric fields.
- **Conditional fields**: if-then-else bucketing.
- **Date part extraction**: year, month, day from a date field.

For complex transformations not expressible in the UI, use a custom pipeline instead.

---

## 5. Dashboards

### Layout

A dashboard is a canvas of charts arranged in a responsive grid. Charts can be resized and repositioned via drag-and-drop. Grid cells snap to a column layout (default 12 columns wide).

### Dashboard-level data sources

A dashboard can be associated with one or more data sources. Charts within the dashboard can each use a different data source, or share one. Dashboard-level data source assignment simplifies onboarding — new charts default to the dashboard's primary source.

### Filters

Dashboard-level filters apply a common MQL condition across all charts on the dashboard that share the same collection as the filtered field. Configure them in **Dashboard > Filter** settings:
1. Choose the field (must exist in the data source collection).
2. Choose the control type: dropdown, date range picker, text input.
3. When a user selects a value, all charts on the dashboard whose data source collection contains the filtered field are re-queried. Charts that use a different collection are unaffected.

Dashboard filters are additive with chart-level query bar filters.

### Chart alerts

Charts supports alert rules that notify when an aggregated metric crosses a threshold. To configure:
1. Open the chart → **…** menu → **Create Alert**.
2. Set the metric field, operator (`>`, `<`, `=`), and threshold value.
3. Configure the notification channel (email or webhook).
4. Alerts evaluate on each scheduled refresh interval (minimum 5 minutes on paid tiers; check Atlas pricing for free-tier limits).

### Sharing dashboards

- **Within Atlas project**: Share with other Atlas users at Viewer or Author permission level.
- **Embed**: Generate an embed code (iframe or SDK) from the dashboard embed settings.
- **PDF / PNG export**: Each chart has an individual download button; dashboards can be exported as PDF snapshots via the UI.
- **Export dashboard JSON**: Use **Dashboard > Export** to download a JSON definition for backup or migration to another Atlas project.

---

## 6. Embedded Charts

Charts can be embedded in external web applications in two modes.

### Unauthenticated (public) embedding

- Generates a public embed URL (iframe `src`).
- No user authentication required — anyone with the URL can see the chart.
- Suitable for public-facing dashboards where the underlying data is non-sensitive.
- You can still apply a **base filter** in the embed settings (locked server-side) to restrict which documents are visible.

**Quick iframe embed snippet:**

```html
<iframe
  src="https://charts.mongodb.com/charts-myproject-abc123/embed/charts?id=<chartId>&maxDataAge=3600&theme=light"
  style="border: none; width: 640px; height: 480px;">
</iframe>
```

### Authenticated SDK embedding

- Uses the Atlas Charts JavaScript SDK (`@mongodb-js/charts-embed-dom`).
- Requires your backend to issue a signed JWT or use one of the supported auth providers (Atlas App Services users, custom JWT).
- The chart is rendered inside a sandboxed `<iframe>` managed by the SDK.
- Supports passing **user-scoped filter objects** from your application to restrict the data each user sees.

### JWT-based filter security

> **Security — read before implementing multi-tenant embeds.**
>
> Never pass filter values directly from untrusted client input. A client that can modify the filter object in browser DevTools could access another tenant's data. Always sign tenant-scoped filters in a backend-issued JWT.

When passing filters from the embedding application to a chart, use a **signed JWT** issued by your backend. The JWT payload can include a `mongodbFilter` claim:

```javascript
// Backend (Node.js example) — sign on your server, never in browser code
import jwt from 'jsonwebtoken';

const token = jwt.sign(
  {
    sub: 'user-123',
    mongodbFilter: { tenantId: 'acme' },
  },
  process.env.CHARTS_EMBEDDING_SIGNING_KEY,
  { expiresIn: '30m' } // produces a valid absolute exp claim
);
```

The JWT must be signed with the **Embedding Signing Key** configured in Charts project settings. Charts verifies the signature server-side before applying the filter.

---

## 7. Embedding SDK

The JavaScript embedding SDK (`@mongodb-js/charts-embed-dom`) provides programmatic control over embedded charts.

### Installation

```bash
npm install @mongodb-js/charts-embed-dom
```

### Basic usage

```javascript
import ChartsEmbedSDK from '@mongodb-js/charts-embed-dom';

const sdk = new ChartsEmbedSDK({
  baseUrl: 'https://charts.mongodb.com/charts-myproject-abc123',
});

const chart = sdk.createChart({
  chartId: 'a1b2c3d4-...',
  height: '400px',
  theme: 'dark',
  autoRefresh: true,
  maxDataAge: 60, // seconds; enables client-side cache
  filter: { status: 'open' }, // client-visible filter (not security-sensitive)
});

await chart.render(document.getElementById('chart-container'));
```

### Authenticated embedding with JWT

```javascript
const chart = sdk.createChart({
  chartId: 'a1b2c3d4-...',
  getUserToken: async () => {
    // Call your backend to get a signed JWT (never generate it here)
    const res = await fetch('/api/charts-token');
    const { token } = await res.json();
    return token;
  },
});
```

### Theming

The SDK exposes a `theme` property (`'light'` | `'dark'`) and a `customTheme` object for color overrides. Custom theme keys include `background`, `title.color`, `axisLabel.color`, `marks.color`, and others documented in the SDK README.

### Drilldowns and events

Charts embedded via the SDK emit events you can subscribe to:
- `click` — fired when a user clicks a data mark; payload includes the underlying document fields for that mark.
- `filter` — fired when a dashboard filter control changes value.

```javascript
chart.addEventListener('click', (payload) => {
  // payload.target contains the clicked mark's data
  console.log(payload.target);
  // Navigate or filter another component based on the clicked value
  drillDown(payload.target.x);
});
```

This is the foundation for building drilldown navigation — a click on a bar chart can navigate the user to a filtered detail view in your application.

### Refresh control

```javascript
// Programmatic refresh
await chart.refresh();

// Disable auto-refresh for a chart that should only load once
const chart = sdk.createChart({ chartId: '...', autoRefresh: false });
```

---

## 8. Charts API (REST)

Atlas Charts exposes a REST API for programmatic management of charts and dashboards. The base URL follows the Atlas Admin API pattern:

```
https://cloud.mongodb.com/api/atlas/v1.0/groups/{groupId}/charts/
```

> **Note**: The Atlas Admin API has a v2 path (`/api/atlas/v2`) for newer resources. Charts management endpoints were originally in v1.0 and continue to work there; consult the current Atlas API changelog if you need v2 equivalents.

### Authentication

Charts API uses Atlas programmatic API keys (public key + private key) with Digest authentication, the same as the Atlas Admin API.

### Common operations

| Operation | Method | Path |
|---|---|---|
| List dashboards | GET | `/groups/{gId}/charts/dashboards` |
| Get dashboard | GET | `/groups/{gId}/charts/dashboards/{dashId}` |
| Create dashboard | POST | `/groups/{gId}/charts/dashboards` |
| Delete dashboard | DELETE | `/groups/{gId}/charts/dashboards/{dashId}` |
| List charts in dashboard | GET | `/groups/{gId}/charts/dashboards/{dashId}/charts` |
| Get chart definition | GET | `/groups/{gId}/charts/charts/{chartId}` |
| Update chart | PATCH | `/groups/{gId}/charts/charts/{chartId}` |

### Use cases

- **CI/CD**: Version-control chart definitions as JSON and apply them via API on deploy.
- **Tenant provisioning**: When onboarding a new customer, clone a template dashboard and remap its data source to the tenant's collection via API.
- **Bulk updates**: Update chart colors or titles across many dashboards via script rather than clicking through the UI.

---

## 9. Access Control

### Role hierarchy

| Role | Scope | Capabilities |
|---|---|---|
| **Viewer** | Dashboard | Can view dashboards and interact with filters; cannot edit charts |
| **Author** | Dashboard or project | Can create and edit charts and dashboards |
| **Admin** | Project | Can manage data sources, embedding keys, and user permissions |

Atlas project Owners automatically receive Charts Admin.

### Dashboard sharing

1. Open the dashboard → **Share** button.
2. Add Atlas users or teams by email/team name.
3. Assign Viewer or Author per grantee.
4. Optionally generate an **embed link** with or without authentication.

### Project-level vs org-level access

- Data source access is project-scoped: a Charts data source in Project A is not visible from Project B.
- Org-level Atlas users with Org Owner role can access Charts in any project under the org.
- Charts does not have an org-level "Charts Admin" role separate from Atlas org roles.

### IP allowlist

Charts respects the Atlas cluster network access controls. If your cluster has an IP allowlist, ensure that the Charts rendering layer's egress IPs are included. MongoDB publishes these IPs in the Atlas documentation for each region.

---

## 10. Anti-Patterns

### Unfiltered large collection queries

A chart with no query bar filter and no encoding-level `$match` will scan the full collection on every render. For collections with tens of millions of documents, this causes:
- High latency (seconds to tens of seconds per chart load).
- Read IOPS spikes that can affect application query performance on shared tiers.

**Fix**: Always add a query bar filter that limits the scan to the time window or subset relevant to the chart. For time-series data, filter to the last N days by default.

### No caching for embedded charts

Public embedded charts loaded on a high-traffic marketing page will fire a live Atlas query on every page view. At scale this becomes both expensive and slow.

**Fix**: Use the SDK's `maxDataAge` property to enable client-side result caching (per-browser tab). For server-side caching, consider a lightweight proxy that caches the Charts embed token and sets a TTL matching your data freshness requirements.

### Missing filter security on multi-tenant embeds

Passing tenant filter values as plain URL parameters or unverified query strings allows malicious users to modify the filter in browser devtools and access other tenants' data.

**Fix**: Always issue tenant-scoped filters inside a backend-signed JWT. Never trust client-supplied filter values for security-sensitive data.

### Using Charts as a real-time operational dashboard

Charts is optimized for analytical queries over moderate data volumes. It is not designed for sub-100ms refresh loops or ticker-style live data.

**Fix**: For real-time operational metrics (ops/sec, latency percentiles), use a time-series purpose-built tool (Grafana + MongoDB Atlas metrics, or Atlas monitoring panels) rather than Charts.

### Too many data sources per dashboard

Dashboards with charts spanning many different collections issue independent queries for each chart on render. A 20-chart dashboard hitting 15 different collections can produce 20 concurrent Atlas queries.

**Fix**: Consolidate related metrics into pre-aggregated summary collections using Atlas Triggers or scheduled aggregations. Point Charts at the summary collection instead of the raw operational collection.

### Exposing raw collection schema through unauthenticated embeds

An unauthenticated public embed with no base filter exposes whatever fields the chart encodes. If a chart's tooltip or table mode displays sensitive fields, any visitor can see them.

**Fix**: Always configure a restrictive base filter in embed settings, and limit encoded fields to the minimum necessary for the visualization.

---

## 11. Cost Model

### Free tier

Every Atlas project (including M0 free-tier clusters) gets Atlas Charts at no additional charge for use within the Atlas UI. The free tier includes:
- **Unlimited dashboards** for Atlas-authenticated users viewing charts inside the Atlas UI.
- A monthly embedded render quota (consult the current Atlas pricing page; historically 1,000 renders/month).
- Both unauthenticated and authenticated embed types consume the render quota.

### Paid embedded renders

Once the free monthly render quota is exhausted, each embedded chart render is billed at a per-render rate. A "render" is counted each time an embedded chart loads data in a browser (not each time the hosting page loads — only when the chart iframe fetches new data).

The `maxDataAge` SDK option directly reduces your bill by serving cached results within the TTL window instead of issuing new render calls.

### No separate Charts cluster cost

You pay only for your Atlas cluster (compute + storage) and any embedded renders above the free tier. Charts itself has no cluster, no dedicated compute charge, and no separate storage fee.

### Federated source cost

Queries routed through Atlas Data Federation may incur Data Federation processing fees (billed per GB of data processed). Factor this in when using Charts over S3-backed federated sources at scale.

---

## 12. Quick Reference

### SDK initialization checklist

1. Install `@mongodb-js/charts-embed-dom`.
2. Configure the embedding signing key in Atlas Charts project settings.
3. Build a backend endpoint that issues short-lived signed JWTs (using a proper JWT library with `expiresIn`) with `mongodbFilter` claims scoped to the authenticated user.
4. Use `getUserToken` in the SDK to call that endpoint; never generate or hard-code the signing key in client-side code.
5. Set `maxDataAge` to a value appropriate for your data freshness requirements to control both latency and cost.
6. Subscribe to `click` events for drilldown navigation.
7. Test with a non-admin Atlas user to verify that permission boundaries are respected.

### Unauthenticated iframe embed checklist

1. In Charts UI, open the chart → **Embed** → set **Authentication: Unauthenticated**.
2. Configure a **base filter** to restrict visible documents (e.g., `{ "public": true }`).
3. Copy the iframe snippet; set `maxDataAge` query param to reduce render billing.
4. Test the embed URL in an incognito window (no Atlas session) to confirm it loads.

### Charts API quick-start

1. Create a programmatic API key in Atlas with Project Data Access Read/Write or Owner role.
2. `GET /api/atlas/v1.0/groups/{groupId}/charts/dashboards` to list dashboards.
3. `GET /api/atlas/v1.0/groups/{groupId}/charts/charts/{chartId}` to export a chart definition as JSON.
4. Store definitions in version control; `PATCH` to update on deploy.
