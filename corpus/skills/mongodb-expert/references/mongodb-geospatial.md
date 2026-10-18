<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-expert` hub.** Formerly the standalone `mongodb-geospatial` skill.
> Sibling MongoDB sub-topics are now reference files under the four hubs (`mongodb-expert`,
> `mongodb-atlas-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not**
> standalone skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that
> name a bare `mongodb-*`/`atlas-*` skill; instead load that topic's `references/<name>.md`
> from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-geospatial
category: mongodb
version: "1.1.0"
updated: "2026-05-29"
description: >
  MongoDB geospatial query, index, and data-model expert.
  TRIGGER: whenever a schema includes location/coordinate fields, a query
  filters by distance or bounding region, a $geoNear aggregation stage
  needs tuning, or GeoJSON storage/indexing patterns are in scope. Also
  triggers on: "find nearest", "within radius", "points inside polygon",
  "geo index", "2dsphere", "distance query", "$geoWithin", "$near".
  SKIP: full-text search (use mongodb-atlas-search), vector similarity
  search (use mongodb-atlas-vector-search), or general aggregation
  questions unrelated to spatial filtering.
tags:
  - mongodb
  - geospatial
  - 2dsphere
  - geojson
whenToUse:
  - "Designing a schema that stores location, coordinates, or geographic boundaries"
  - "Creating 2dsphere or 2d indexes on location fields"
  - "Writing proximity queries with $near, $nearSphere, or $geoNear"
  - "Building containment queries with $geoWithin or $geoIntersects"
  - "Troubleshooting 'unable to find index for $geoNear query' errors"
  - "Converting between km/miles/radians for $centerSphere radius queries"
  - "Designing geospatial $lookup patterns or spatial joins"
  - "Auditing GeoJSON coordinate order (lng/lat vs lat/lng) bugs"
  - "Optimizing $geoNear aggregation pipeline performance"
  - "Choosing between 2dsphere (spherical) and 2d (planar) index types"
whenNotToUse:
  - "Full-text or lexical search — use mongodb-atlas-search"
  - "Semantic / vector similarity search — use mongodb-atlas-vector-search"
  - "General aggregation pipeline questions with no spatial component"
  - "GeoJSON validation tooling outside MongoDB (use a GeoJSON linter)"
related_skills:
  - mongodb-indexes-deep
  - mongodb-aggregation-pipeline
  - mongodb-atlas-search
  - mongodb-atlas-vector-search
  - mongodb-schema-design
---

# MongoDB Geospatial

## Description

Use when designing or troubleshooting MongoDB geospatial queries, indexes, or data models. Covers GeoJSON storage, 2dsphere and 2d index types, proximity and containment operators ($near, $geoWithin, $geoNear, $geoIntersects), radius calculations, $lookup pipeline joins across spatial collections, and common anti-patterns. Apply this skill whenever a schema includes location fields, a query filters by distance or bounding region, or a $geoNear aggregation stage needs tuning.

---

## 1. GeoJSON Object Types

MongoDB natively stores and queries the GeoJSON spec. Every GeoJSON field is an embedded document with a `type` string and a `coordinates` array. **Longitude always comes before latitude** — the opposite of most mapping UIs.

```js
// Point — single location
{ type: "Point", coordinates: [-73.9857, 40.7484] }   // [lng, lat]

// LineString — ordered sequence of positions
{
  type: "LineString",
  coordinates: [
    [-73.9857, 40.7484],
    [-74.0060, 40.7128]
  ]
}

// Polygon — closed ring; first and last coordinate must be equal
{
  type: "Polygon",
  coordinates: [[
    [-73.9580, 40.8003],
    [-73.9498, 40.7968],
    [-73.9737, 40.7648],
    [-73.9818, 40.7681],
    [-73.9580, 40.8003]   // closes the ring
  ]]
}

// MultiPoint
{ type: "MultiPoint", coordinates: [[-73.98, 40.75], [-74.01, 40.71]] }

// MultiLineString
{
  type: "MultiLineString",
  coordinates: [
    [[-73.98, 40.75], [-74.00, 40.72]],
    [[-73.97, 40.76], [-73.95, 40.74]]
  ]
}

// MultiPolygon
{
  type: "MultiPolygon",
  coordinates: [
    [[ [-74.0, 40.7], [-73.9, 40.7], [-73.9, 40.8], [-74.0, 40.8], [-74.0, 40.7] ]],
    [[ [-73.85, 40.65], [-73.75, 40.65], [-73.75, 40.75], [-73.85, 40.75], [-73.85, 40.65] ]]
  ]
}

// GeometryCollection — heterogeneous mix
{
  type: "GeometryCollection",
  geometries: [
    { type: "Point",      coordinates: [-73.9857, 40.7484] },
    { type: "LineString", coordinates: [[-73.98, 40.75], [-74.00, 40.72]] }
  ]
}
```

Insert a document with a GeoJSON Point field:

```js
db.places.insertOne({
  name: "Empire State Building",
  location: { type: "Point", coordinates: [-73.9857, 40.7484] },
  category: "landmark"
});
```

---

## 2. 2dsphere Indexes

A **2dsphere** index supports queries on GeoJSON geometry computed over a sphere modelled on WGS84 (the same datum used by GPS). Version 3 has been the default since MongoDB 3.2; MongoDB 8.3+ defaults to version 4. It handles Points, LineStrings, and Polygons stored as GeoJSON and supports all geospatial query operators.

```js
// Basic 2dsphere index on a GeoJSON field
db.places.createIndex({ location: "2dsphere" });

// Compound index — location plus a scalar field
db.places.createIndex({ location: "2dsphere", category: 1 });

// Check the index was created correctly
db.places.getIndexes();
// → { "key": { "location": "2dsphere" }, "name": "location_2dsphere", "2dsphereIndexVersion": 3 }

// Specify index version explicitly (rarely needed)
db.places.createIndex({ location: "2dsphere" }, { "2dsphereIndexVersion": 3 });
```

Key properties:
- Handles wraparound at the anti-meridian (180° longitude) correctly.
- Required by `$geoNear`, `$near`, `$nearSphere`, `$geoWithin` with `$centerSphere`.
- 2dsphere indexes are **always sparse** (MongoDB ignores the `sparse` option). A document missing the geo field — or where it is `null` or an empty array — is not indexed, whether the index is standalone or compound. In a compound 2dsphere index, only the geo field determines whether a document is indexed.

---

## 3. 2d Indexes

A **2d** index uses planar (flat-earth) geometry. It is a legacy index type intended for coordinate pairs stored as `[lng, lat]` arrays (not GeoJSON documents). Use it only when the coordinate space is genuinely flat (e.g., game maps, CAD drawings, grid systems) and spherical correction is not needed.

```js
// Legacy coordinate pair stored as an array
db.legacy.insertOne({ name: "HQ", loc: [-73.98, 40.75] });

// Create a 2d index
db.legacy.createIndex({ loc: "2d" });

// Optional: define the bounding box and granularity
db.legacy.createIndex({ loc: "2d" }, { min: -180, max: 180, bits: 26 });

// $near on a 2d index — returns sorted by distance, Euclidean
db.legacy.find({ loc: { $near: [-73.98, 40.75], $maxDistance: 0.5 } });
```

Limitations vs. 2dsphere:
- No polygon-edge wraparound.
- Distance unit is degrees, not metres.
- Does not support GeoJSON input documents.
- Cannot use `$geoNear` aggregation with `spherical: true`.

---

## 4. $geoNear Aggregation Stage

`$geoNear` must be the **first stage** of an aggregation pipeline. It returns documents sorted by computed distance from a reference point and appends the distance value to each document under `distanceField`. A geospatial index is required; if multiple exist, specify `key`.

```js
db.places.aggregate([
  {
    $geoNear: {
      near: { type: "Point", coordinates: [-73.9857, 40.7484] },
      distanceField: "dist.calculated",   // field added to output docs
      maxDistance: 2000,                  // metres (spherical: true)
      minDistance: 100,
      query: { category: "restaurant" },  // pre-filter before distance
      spherical: true,                    // required for 2dsphere index
      key: "location"                     // required when > 1 geo index exists
    }
  },
  { $limit: 10 },
  { $project: { name: 1, "dist.calculated": 1, _id: 0 } }
]);
```

`distanceMultiplier` converts metres to another unit:

```js
{
  $geoNear: {
    near: { type: "Point", coordinates: [-73.9857, 40.7484] },
    distanceField: "distKm",
    distanceMultiplier: 0.001,   // metres → kilometres
    spherical: true
  }
}
```

`includeLocs` records the matched location field alongside distance:

```js
{ $geoNear: { ..., includeLocs: "matchedLocation", spherical: true } }
```

---

## 5. $geoWithin

`$geoWithin` finds documents whose geometry is **entirely contained within** a specified shape. It does not sort results and does not require a geospatial index (though an index improves performance significantly on large collections).

```js
// Within a GeoJSON Polygon
db.places.find({
  location: {
    $geoWithin: {
      $geometry: {
        type: "Polygon",
        coordinates: [[
          [-74.0, 40.7], [-73.9, 40.7],
          [-73.9, 40.8], [-74.0, 40.8],
          [-74.0, 40.7]
        ]]
      }
    }
  }
});

// $centerSphere — circle on a sphere; radius in radians
// radians = distanceKm / 6378.1
const radiusKm = 5;
db.places.find({
  location: {
    $geoWithin: {
      $centerSphere: [ [-73.9857, 40.7484], radiusKm / 6378.1 ]
    }
  }
});

// $box — planar rectangle (2d index only)
db.legacy.find({ loc: { $geoWithin: { $box: [[-74.1, 40.6], [-73.8, 40.9]] } } });

// $polygon — planar polygon (2d index only)
db.legacy.find({ loc: { $geoWithin: { $polygon: [[-74, 40.7], [-73.9, 40.7], [-73.95, 40.85]] } } });
```

---

## 6. $geoIntersects

`$geoIntersects` finds documents whose GeoJSON geometry **intersects** — shares any point with — the query geometry. Useful for routes, delivery zones, and region overlap checks. Requires a 2dsphere index for good performance.

```js
// Find all routes that pass through a query polygon
db.routes.find({
  path: {
    $geoIntersects: {
      $geometry: {
        type: "Polygon",
        coordinates: [[
          [-74.02, 40.69], [-73.97, 40.69],
          [-73.97, 40.74], [-74.02, 40.74],
          [-74.02, 40.69]
        ]]
      }
    }
  }
});

// Find zones that contain a specific point (point in polygon)
db.zones.find({
  boundary: {
    $geoIntersects: {
      $geometry: { type: "Point", coordinates: [-73.9857, 40.7484] }
    }
  }
});

// Works with LineString query geometry too
db.regions.find({
  area: {
    $geoIntersects: {
      $geometry: {
        type: "LineString",
        coordinates: [[-74.0, 40.7], [-73.9, 40.8]]
      }
    }
  }
});
```

---

## 7. $near and $nearSphere

`$near` and `$nearSphere` are **query operators** (not aggregation stages). Both sort results by distance and **require a geospatial index**. They cannot be used inside `$or` or `$and` alongside other `$near`/`$nearSphere` expressions.

```js
// $near with GeoJSON (requires 2dsphere index, metres)
db.places.find({
  location: {
    $near: {
      $geometry: { type: "Point", coordinates: [-73.9857, 40.7484] },
      $maxDistance: 1500,   // metres
      $minDistance: 100     // metres
    }
  }
});

// $nearSphere with GeoJSON (spherical interpretation, metres)
db.places.find({
  location: {
    $nearSphere: {
      $geometry: { type: "Point", coordinates: [-73.9857, 40.7484] },
      $maxDistance: 2000
    }
  }
});

// $near with legacy coordinate pair (2d index, degrees)
db.legacy.find({
  loc: { $near: [-73.98, 40.75], $maxDistance: 0.5 }
});

// Combine with additional filter fields
db.places.find({
  category: "coffee",
  location: {
    $near: {
      $geometry: { type: "Point", coordinates: [-73.9857, 40.7484] },
      $maxDistance: 800
    }
  }
});
```

**$near vs. $geoNear:** Use `$near` for a simple `.find()` that returns sorted documents. Use `$geoNear` when you need the distance value in the result, further pipeline stages, or more control (distanceMultiplier, query pre-filter, key selection).

---

## 8. Radius Queries

Converting a real-world radius to the unit each operator expects:

| Operator / context | Unit | Conversion from km |
|---|---|---|
| `$near` / `$nearSphere` GeoJSON | metres | `km * 1000` |
| `$geoNear` `maxDistance` (spherical) | metres | `km * 1000` |
| `$centerSphere` radians | radians | `km / 6378.1` (Earth radius km) |
| `$centerSphere` miles | radians | `miles / 3963.2` (Earth radius mi) |
| `$near` legacy 2d | degrees | `km / 111.2` (approx) |

```js
// 5 km radius — $geoWithin $centerSphere (radians)
const radiusKm = 5;
db.places.find({
  location: {
    $geoWithin: {
      $centerSphere: [ [-73.9857, 40.7484], radiusKm / 6378.1 ]
    }
  }
});

// 10 miles radius — $geoWithin $centerSphere
const radiusMi = 10;
db.places.find({
  location: {
    $geoWithin: {
      $centerSphere: [ [-73.9857, 40.7484], radiusMi / 3963.2 ]
    }
  }
});

// 2 km radius — $near (metres)
db.places.find({
  location: {
    $near: {
      $geometry: { type: "Point", coordinates: [-73.9857, 40.7484] },
      $maxDistance: 2000
    }
  }
});

// Helper function for application code
function kmToRadians(km) { return km / 6378.1; }
function milesToRadians(mi) { return mi / 3963.2; }
```

---

## 9. Geospatial $lookup Patterns

Geospatial query operators (`$geoIntersects`, `$geoWithin`, `$near`) are **query operators, not aggregation expression operators** — they cannot be used inside `$expr`. Inside a `$lookup` pipeline stage, place them directly inside `$match` against a field in the **joined** collection. The outer document's location must be supplied via `$geoNear` output or by denormalizing the coordinate.

```js
// Pattern A: two-stage pipeline — $geoNear first, then $lookup on a scalar key
// (most scalable; spatial work happens in the first stage against the driving collection)
db.orders.aggregate([
  {
    $geoNear: {
      near: { type: "Point", coordinates: [-73.9857, 40.7484] },
      distanceField: "dist",
      spherical: true,
      maxDistance: 5000
    }
  },
  {
    $lookup: {
      from: "zones",
      localField: "zoneId",    // scalar ID pre-assigned at write time
      foreignField: "_id",
      as: "zone"
    }
  }
]);

// Pattern B: $lookup with a pipeline — geo filter inside $match on the joined collection
// Works when the joined collection (zones) has a 2dsphere index on `boundary`
// and each order document carries a static query polygon (e.g. a stored bounding box)
db.orders.aggregate([
  {
    $lookup: {
      from: "zones",
      pipeline: [
        {
          $match: {
            boundary: {
              $geoIntersects: {
                $geometry: { type: "Point", coordinates: [-73.9857, 40.7484] }
              }
            }
          }
        }
      ],
      as: "matchedZones"
    }
  }
]);
// Limitation: the coordinates above are a literal — to pass a per-document point
// into a $lookup pipeline, use the denormalize pattern below instead.

// Recommended pattern: denormalize zone ID at write time
// Step 1 — resolve the zone when creating the order
async function findZoneForPoint(db, point) {
  return db.collection("zones").findOne({
    boundary: { $geoIntersects: { $geometry: point } }
  });
}

// Step 2 — store zoneId on the order document
await db.collection("orders").insertOne({
  _id: orderId,
  location: { type: "Point", coordinates: [lng, lat] },
  zoneId: zone._id    // denormalized scalar — cheap to $lookup later
});

// Step 3 — simple $lookup on zoneId at query time (no per-row geo scan)
db.orders.aggregate([
  { $lookup: { from: "zones", localField: "zoneId", foreignField: "_id", as: "zone" } }
]);
```

Performance considerations for geospatial $lookup:
- `$geoIntersects` / `$geoWithin` inside a `$lookup` pipeline runs once per driving document; ensure a 2dsphere index on the joined collection's geometry field.
- Add a `$match` with a bounding-box `$geoWithin` before `$lookup` to narrow candidates when the joined collection is large.
- Denormalizing the zone or region ID at write time (Recommended pattern above) eliminates the per-row geo scan entirely and scales best.
- For hot-path proximity queries at scale, consider Atlas Search `$search` with a `geoWithin` or `geoShape` filter, which uses a dedicated search index and avoids aggregation pipeline overhead.

---

## 10. Anti-Patterns

```js
// BAD — coordinate order wrong (lat, lng instead of lng, lat)
{ type: "Point", coordinates: [40.7484, -73.9857] }   // silently stores wrong location

// GOOD
{ type: "Point", coordinates: [-73.9857, 40.7484] }   // lng, lat

// BAD — querying without a 2dsphere index
// $near will throw: "unable to find index for $geoNear query"
db.places.find({ location: { $near: { $geometry: { type: "Point", coordinates: [-73.98, 40.75] } } } });
// Always create the index first:
db.places.createIndex({ location: "2dsphere" });

// BAD — polygon spanning more than 180 degrees of longitude
// MongoDB interprets the smaller interior; polygons > 180° may be treated as their complement
{
  type: "Polygon",
  coordinates: [[
    [-170, -80], [170, -80], [170, 80], [-170, 80], [-170, -80]  // spans 340°, ambiguous
  ]]
}
// GOOD — split into two polygons or use multipolygon; keep each ring < 180°

// BAD — $geoNear not as first aggregation stage
db.places.aggregate([
  { $match: { category: "cafe" } },   // pre-filter before $geoNear — causes error
  { $geoNear: { near: { ... }, distanceField: "d", spherical: true } }
]);
// GOOD — $geoNear must be stage 0; use query: {} inside $geoNear for pre-filtering:
db.places.aggregate([
  { $geoNear: { near: { ... }, distanceField: "d", spherical: true, query: { category: "cafe" } } }
]);

// BAD — mixing 2d index with GeoJSON queries
db.places.createIndex({ loc: "2d" });
db.places.find({ loc: { $near: { $geometry: { type: "Point", coordinates: [-73.98, 40.75] } } } });
// 2d index does not support GeoJSON $geometry form; use 2dsphere

// BAD — omitting spherical: true on a 2dsphere index with $geoNear
db.places.aggregate([
  { $geoNear: { near: { type: "Point", coordinates: [-73.98, 40.75] }, distanceField: "d" } }
  // missing spherical: true — uses planar distance, wrong results over large distances
]);
// GOOD
{ $geoNear: { ..., spherical: true } }
```

### Anti-Patterns Summary Table

| Anti-pattern | Symptom | Fix |
|---|---|---|
| Lat/lng coordinate order | Queries return wrong or empty results | Always use `[longitude, latitude]` |
| No 2dsphere index | `$near` / `$geoNear` throw error | `createIndex({ field: "2dsphere" })` |
| Polygon ring > 180° | Wrong containment, complement selected | Split into MultiPolygon or smaller rings |
| `$geoNear` not first stage | Aggregation error | Move `$geoNear` to stage index 0 |
| GeoJSON `$geometry` on 2d index | Index not used or query error | Use 2dsphere index for GeoJSON queries |
| Missing `spherical: true` | Planar distance used, wrong results at scale | Always set `spherical: true` with 2dsphere |
| `$near` inside `$or` / `$and` | Query planner error | Restructure; use `$geoNear` in pipeline instead |
| `$centerSphere` radius in km not radians | Radius far too large or small | Divide km by 6378.1 to get radians |

---

## References

1. MongoDB Geospatial Queries overview: https://www.mongodb.com/docs/manual/geospatial-queries/
2. Geospatial query operator reference: https://www.mongodb.com/docs/manual/reference/operator/query-geospatial/
3. 2dsphere index documentation: https://www.mongodb.com/docs/manual/core/2dsphere/
4. $geoNear aggregation stage: https://www.mongodb.com/docs/manual/reference/operator/aggregation/geoNear/
5. GeoJSON objects reference: https://www.mongodb.com/docs/manual/reference/geojson/
6. Geospatial tutorial (find restaurants): https://www.mongodb.com/docs/manual/tutorial/geospatial-tutorial/
