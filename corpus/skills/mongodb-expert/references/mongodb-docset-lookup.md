<!-- hub-reference-banner -->
> **Reference file — part of the `mongodb-expert` hub.** Formerly the standalone `mongodb-docset-lookup` skill.
> Sibling topics in this family are now reference files under the hubs (`mongodb-expert`, `atlas-diagnostics-expert`, `mongodb-operations-expert`) — **not** standalone
> skills. Ignore any "use the X skill" / `related_skills` / SKIP pointers below that name a bare sibling
> skill; load that topic's `references/<name>.md` from the owning hub (see the hub's "Cross-hub map").

---

---
name: mongodb-docset-lookup
category: mongodb
version: "1.1.1"
updated: "2026-06-10"
description: >-
  Offline MongoDB Manual lookup via the local Dash docset. TRIGGER: exact Manual syntax/semantics
  for an operator, command, mongosh method, or server option; verify a MongoDB claim against
  authoritative Manual text; docs lookup when offline or docs.mongodb.com is unreachable; find the
  precise manual page/URL for a topic; ground generated MongoDB advice in real Manual text. SKIP:
  distilled conceptual guidance → mongodb-expert / mongodb-atlas-expert /
  mongodb-operations-expert / atlas-diagnostics-expert; KB troubleshooting articles → mongodb-kb;
  Atlas platform docs (not mirrored — server manual only) → mongodb-atlas-expert; need
  current-version freshness while online → live docs.mongodb.com; docset format/creation/Dash MCP
  setup → dash-docsets. Corpus: version-pinned mirror of
  www.mongodb.com/docs/manual (master docs, mirrored 2026-05-16; 3,555 pages); SQLite searchIndex
  of 6,159 entries: Operators (304), Commands (178), Methods (2,099), Options (827), Guides (585),
  Sections (2,121).
origin: local
tags:
  - mongodb
  - documentation
  - offline
  - lookup
  - dash-docset
  - reference
keywords:
  - offline mongodb docs
  - mongodb manual lookup
  - dash docset
  - exact operator syntax
  - mongodb command reference
  - mongosh method reference
  - server parameter reference
  - verify mongodb claim
  - docs.mongodb.com unreachable
  - manual page path
  - version-pinned documentation
  - searchIndex sqlite
whenToUse:
  - Looking up the exact, authoritative Manual text for an operator, command, method, or option
  - Verifying a MongoDB technical claim against the real Manual page (offline fact-check)
  - Finding docs when offline or when docs.mongodb.com is unreachable
whenNotToUse:
  - Distilled conceptual guidance or design advice — use mongodb-expert (or mongodb-atlas-expert / mongodb-operations-expert / atlas-diagnostics-expert for their domains)
  - KB / troubleshooting article lookup — use mongodb-kb
  - Atlas platform documentation (the mirror covers the server Manual only) — use mongodb-atlas-expert
  - Version-sensitive answers where the latest docs matter and you are online — use live docs.mongodb.com
related_skills:
  - mongodb-expert
  - mongodb-atlas-expert
  - mongodb-operations-expert
  - atlas-diagnostics-expert
  - misc-catch-all
---

# MongoDB Manual Offline Lookup (Dash docset)

A local, version-pinned mirror of the **MongoDB Manual** lives on this machine as a Dash docset.
This skill documents how to query it directly (no Dash app, no network) to retrieve the exact
Manual page for any operator, command, mongosh method, server option, or guide.

**Snapshot pin:** mirrored from `www.mongodb.com/docs/manual/` (the `master`/current docs version)
by HTTrack on **2026-05-16**. Always include this snapshot date when reporting extracted Manual
text so readers can judge currency.

**Output contract:** after running the three-step workflow or `mdb_docs`, return the relevant
extracted text to the user, quoting the specific section(s) that answer the question (not the
full page), plus the live URL (prepend `https://` to the cleaned path) for reference.

## Docset anatomy

Base path (note the space in `Application Support` — always quote):

```
DOCSET="$HOME/Library/Application Support/Dash/DocSets/MongoDB/MongoDB.docset"
```

| File | What it is |
| --- | --- |
| `Contents/Info.plist` | Metadata; `dashIndexFilePath` = manual landing page |
| `Contents/Resources/docSet.dsidx` | SQLite lookup index: `searchIndex(id, name, type, path)` — 6,159 entries |
| `Contents/Resources/tarix.tgz` | ALL page HTML inside one 257 MB tar.gz (no extracted `Documents/` on disk) |
| `Contents/Resources/tarixIndex.db` / `optimizedIndex.dsidx` | Dash-internal random-access/search indexes — ignore |

## Lookup workflow (all commands verified against this docset)

### 1. Find the page in the search index

```bash
sqlite3 -separator ' | ' "$DOCSET/Contents/Resources/docSet.dsidx" \
  "SELECT name, type, path FROM searchIndex WHERE name LIKE '%setWindowFields%' LIMIT 8;"
```

Exact-name match when you know it (quote `$`-names in single quotes so the shell doesn't expand):

```bash
sqlite3 "$DOCSET/Contents/Resources/docSet.dsidx" \
  "SELECT path FROM searchIndex WHERE name = '\$setWindowFields' AND type = 'Operator' LIMIT 1;"
```

Filter by `type` when names collide across types (e.g., `find` is both a privilege-action
Option and a command/method).

### 2. Clean the returned path

Capture the path from step 1 into `$RAW`, then strip two layers of Dash metadata:
`<dash_entry_*>` prefixes (on Guide/Section rows) and `#//apple_ref/...` anchors (on most rows).

```bash
RAW=$(sqlite3 "$DOCSET/Contents/Resources/docSet.dsidx" \
  "SELECT path FROM searchIndex WHERE name = '\$setWindowFields' AND type = 'Operator' LIMIT 1;")
CLEAN=$(printf '%s' "$RAW" | sed 's/<[^>]*>//g' | cut -d'#' -f1)
# → www.mongodb.com/docs/manual/reference/operator/aggregation/setWindowFields/index.html
```

The clean path doubles as the **live URL**: prepend `https://` for a shareable
docs.mongodb.com link (subject to the snapshot-vs-live caveat below).

### 3. Extract the page from the tar and convert to text

The HTML is inside `tarix.tgz` under the prefix `MongoDB.docset/Contents/Resources/Documents/`.
A sequential stream-extract takes ~1 s:

```bash
tar -xzOf "$DOCSET/Contents/Resources/tarix.tgz" \
  "MongoDB.docset/Contents/Resources/Documents/$CLEAN" 2>/dev/null \
  | textutil -stdin -format html -convert txt -stdout
```

`textutil` ships with macOS. The output is clean, readable Manual text (the pages are static
HTML; the mirror was taken with JavaScript disabled, so reference content is complete).

### One-call helper (for a shell session)

```bash
mdb_docs() {  # usage: mdb_docs '$merge'   (single-quote $-names)
  local DOCSET="$HOME/Library/Application Support/Dash/DocSets/MongoDB/MongoDB.docset"
  local raw clean
  raw=$(sqlite3 "$DOCSET/Contents/Resources/docSet.dsidx" \
    "SELECT path FROM searchIndex WHERE name = '$1' ORDER BY type LIMIT 1;")
  if [ -z "$raw" ]; then echo "no exact match for '$1' — retry with LIKE" >&2; return 1; fi
  clean=$(printf '%s' "$raw" | sed 's/<[^>]*>//g' | cut -d'#' -f1)
  tar -xzOf "$DOCSET/Contents/Resources/tarix.tgz" \
    "MongoDB.docset/Contents/Resources/Documents/$clean" 2>/dev/null \
    | textutil -stdin -format html -convert txt -stdout
}
```

## Entry types in the index

| type | count | what it covers |
| --- | --- | --- |
| Section | 2,121 | Named page sections (anchors within pages) |
| Method | 2,099 | mongosh `db.*`/`rs.*`/`sh.*` methods, GridFS fields |
| Option | 827 | Server parameters, command options, privilege actions |
| Guide | 585 | Tutorials and admin guides |
| Operator | 304 | Query + aggregation operators (`$match`, `$merge`, …) |
| Command | 178 | Database commands and binaries (`mongod`, `serverStatus`, …) |
| Type / Variable | 24 / 21 | Extended-JSON types, replica-set member states |

## Caveats

- **Snapshot, not live.** Content is frozen at 2026-05-16 (`master`). For brand-new features or
  changed defaults, cross-check live docs when online — and cite the snapshot date offline.
- **Server Manual only.** No `/docs/atlas`, drivers, or Compass docs in this mirror. Atlas
  questions route to `mongodb-atlas-expert`; KB articles to `mongodb-kb`.
- **Read-only artifact.** Never modify, move, or delete anything under the docset — Dash manages
  it. Re-downloading the docset in Dash refreshes the snapshot (counts and dates here will drift;
  re-derive with `SELECT type, COUNT(*) FROM searchIndex GROUP BY type`).
- **One file per ~1 s.** Stream-extraction scans the 257 MB archive sequentially. Fine for a
  handful of lookups; do not loop it over hundreds of pages — query the index first and extract
  only what you need.
- **SQL quoting.** Index names contain `$` and spaces but no single quotes; pass user input
  through parameterized callers or sanity-check it before string-building SQL.

## How this relates to the other MongoDB skills

| Channel | Corpus | Use for |
| --- | --- | --- |
| `mongodb-expert` + sibling hubs | Distilled expertise (73 reference files) | Design guidance, trade-offs, patterns |
| `mongodb-kb` | ~2,717 internal KB articles | Troubleshooting, error codes, escalation |
| **this skill** | 3,555-page Manual mirror (offline) | Exact authoritative Manual text, offline/citation-grade lookup |
| live docs.mongodb.com | Current docs | Latest-version behavior when online |
