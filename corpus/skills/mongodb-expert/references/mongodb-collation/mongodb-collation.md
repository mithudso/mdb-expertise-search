<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-expert` hub.** Formerly the standalone `mongodb-collation` skill.
> Sibling topics in this family are now reference files under the hubs (`mongodb-expert`) — **not** standalone
> skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that name a bare sibling
> skill; load that topic's `references/<name>.md` from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-collation
description: >-
  MongoDB collation expert: locale-aware string comparison and ordering, and
  case-insensitive queries/indexes. Covers the collation document (locale,
  strength, caseLevel, caseFirst, numericOrdering, alternate, maxVariable,
  backwards) and the simple binary default.
  TRIGGER: case-insensitive or accent-insensitive search/sort; locale-aware
  ordering; the collation document fields and ICU strength levels (1-5);
  numericOrdering for numeric strings ("10" vs "2"); setting collation at
  collection vs index vs query/cursor level and the inheritance rules; building
  a case-insensitive index (strength 1 or 2) and why a query must repeat the
  same collation to use it; collation on views; text/2d indexes needing
  locale:"simple".
  SKIP: Atlas Search analyzers/tokenizers/BM25 relevance (Lucene full-text) ->
  mongodb-atlas-expert; general index design, aggregation stage semantics, and
  BSON string type details -> mongodb-expert.
version: 1.1.1
updated: 2026-07-17
model: claude-sonnet-5
effort: medium
category: mongodb
whenToUse:
  - "how do I make a MongoDB query or index case-insensitive?"
  - "why isn't my case-insensitive index being used?"
  - "how do I sort strings by locale, or make search accent-insensitive?"
  - "why does '10' sort before '2' in my results, and how do I fix it?"
  - "what collation should I set on this collection, index, or query?"
  - "does collation apply to a view, and can I override it per query?"
whenNotToUse:
  - Atlas Search analyzers, tokenizers, or BM25 relevance scoring (Lucene full-text) — use mongodb-atlas-expert
  - General index-type design, aggregation stage semantics, or BSON string-type internals — use mongodb-expert
keywords:
  - collation
  - case-insensitive index
  - locale
  - strength
  - caseLevel
  - numericOrdering
  - simple binary comparison
  - accent-insensitive
  - icu comparison levels
  - collation inheritance
tags:
  - mongodb
  - collation
  - indexes
  - queries
  - i18n
  - text-search
---

# MongoDB Collation

> Scope: **collation** (locale-aware comparison/ordering) and case-insensitive
> queries/indexes. For Lucene-based full-text search (analyzers, stemming,
> synonyms, BM25) see `mongodb-atlas-expert` (`mongodb-atlas-expert/references/mongodb-atlas-search.md`);
> for the general index-type catalog see `mongodb-expert`
> (`mongodb-expert/references/mongodb-indexes-deep.md`).
>
> `verified-as-of: 2026-07-15`, confirmed against the MongoDB Manual (current
> and v8.2); collation defaults are stable but re-verify locale specifics.

## Overview

**Collation** lets MongoDB compare and order strings by language-specific rules
(case, diacritics, punctuation, numeric ordering) instead of raw byte order. The
default collation is **`locale: "simple"`** (binary comparison), so out of the
box `"Betsy"` and `"betsy"` are different values and sort by code point.
[^collation][^locales]

## The collation document

```javascript
{
  locale: <string>,          // REQUIRED (e.g. "en_US"); "simple" = binary
  caseLevel: <boolean>,      // default false
  caseFirst: <string>,       // "upper" | "lower" | "off"
  strength: <int>,           // ICU comparison level 1-5, default 3
  numericOrdering: <boolean>,// default false
  alternate: <string>,       // "non-ignorable" | "shifted"
  maxVariable: <string>,     // "punct" | "space"
  backwards: <boolean>
}
```

`locale` is the only required field; everything else is optional and may have
locale-specific defaults. Defaults consistent across locales: `caseLevel:false`,
`strength:3`, `numericOrdering:false`, `maxVariable:punct`. [^collation][^cursor][^locales]

### Key fields

- **`strength`** (ICU comparison level) is the one you tune most:
  - **1**, base characters only; ignores case **and** diacritics.
  - **2**, base + diacritics; still case-insensitive.
  - **3** (default), case-sensitive, diacritic-sensitive.
  - 4 / 5, punctuation / tie-breaking distinctions.
  A `strength` of **1 or 2 = case-insensitive**. [^caseinsensitive][^cursor]
- **`caseLevel`**, when true with `strength:1`, compares base characters **and**
  case; with `strength:2`, base + diacritics + case. [^collation][^cursor]
- **`numericOrdering`**, `true` compares numeric strings as numbers (`"10" > "2"`);
  `false` (default) compares them as strings (`"10" < "2"`). [^cursor]

## Where collation is set, and inheritance

Collation can be specified at three levels; the interaction is the main source of
surprises:

1. **Collection default** (at `createCollection`): once set, **all indexes and
   all queries inherit it** unless they explicitly specify a different collation.
   [^caseinsensitive]
2. **Index**: an index can carry its own collation (e.g. a case-insensitive
   index). [^caseinsensitive]
3. **Query / sort** (`.collation()` on the cursor / aggregation): overrides per
   operation. [^cursor]

**Critical rule for index use:** to use a collated index for string comparisons,
the operation's **effective collation** — explicit on the query, or inherited
from the collection default when the query specifies none — **must match**
the index's collation. A query with a different explicit collation cannot use
that index for string comparisons; on a collection with **no default
collation**, an unspecified query collation falls back to `"simple"` and also
cannot use a non-simple collated index. [^collation][^caseinsensitive]

## Case-insensitive indexes

Case insensitivity is *derived from collation*. Create a case-insensitive index
by giving it a collation with `strength: 1` or `2`:

```javascript
db.names.createIndex(
  { first_name: 1 },
  { collation: { locale: "en", strength: 2 } }
)
```

- On a collection with **no default collation**, you must repeat the **same
  collation at query level** for the query to use the index. [^caseinsensitive]
- On a collection **with** a default collation, queries inherit it and use the
  index automatically; you can still force a case-sensitive search by passing a
  different collation (e.g. `strength:3`) on the query. [^caseinsensitive]

## Collation on views

- A view's default collation does **not** inherit the underlying collection's —
  it defaults to `"simple"` unless set at view creation.
- String comparisons on a view use the view's default collation, and you
  **cannot override** it per operation.
- A view created from another view must match the source view's collation, and
  `$lookup`/`$graphLookup` across views require the views to share a collation.
  [^collation]

## Anti-patterns / gotchas

- **Index defined with a collation, query without it (or with a different one)**
  → the index is silently not used for string comparisons; you get a slow scan or
  case-sensitive results. Always match the collation. [^collation][^caseinsensitive]
- **Expecting the collection default to reach a view** → it does not; set the
  view's collation explicitly. [^collation]
- **`text` or `2d` index on a collection with a non-simple default collation** →
  you must explicitly pass `{ collation: { locale: "simple" } }` when creating
  that index, because those index types only support simple binary comparison.
  [^collation]
- **Sorting version-like or numeric strings** and getting `"10"` before `"2"` →
  set `numericOrdering: true`. [^cursor]

## Troubleshooting

- **Case-insensitive query returns case-sensitive results** → no collation on the
  query, or it differs from the index/collection collation. Add
  `.collation({ locale: ..., strength: 2 })`. [^caseinsensitive]
- **Query ignores my case-insensitive index** → operation collation does not
  match the index collation. [^caseinsensitive]
- **`$lookup` between views errors on collation** → the joined views must share a
  collation. [^collation]
- **Need the full optimize-and-verify loop on a specific collated query** (explain-verified
  rewrite + index recommendation) → mongodb-expert (references/deep-mongodb-mql-query-optimizer.md) (/dmqo).

## References

[^collation]: MongoDB Manual: Collation (collation document, strength/caseLevel, index-must-match-collation rule, views, simple-only index types). https://www.mongodb.com/docs/manual/reference/collation/
[^caseinsensitive]: MongoDB Manual: Case-Insensitive Indexes (strength 1/2, collection-default inheritance, query must repeat collation). https://www.mongodb.com/docs/manual/core/index-case-insensitive/
[^locales]: MongoDB Manual: Collation Locales and Default Parameters (simple default, cross-locale defaults). https://www.mongodb.com/docs/manual/reference/collation-locales-defaults/
[^cursor]: MongoDB Manual: cursor.collation() (per-query collation, strength/caseLevel/numericOrdering semantics, worked examples). https://www.mongodb.com/docs/manual/reference/method/cursor.collation/

## Digest

Cheap digest: `mongodb-collation.llms/llms-small.txt` (≤2k tokens). Citable claims with locators: `mongodb-collation.llms/llms-facts.txt`. Produced by skill-to-llms-txt digest mode; the SKILL.md body above stays the full reference.
