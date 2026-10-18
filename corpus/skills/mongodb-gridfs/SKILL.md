---
name: mongodb-gridfs
description: >-
  MongoDB GridFS expert: the specification for storing files larger than the
  16 MB BSON document limit by splitting them into chunks across two
  collections (files + chunks) in a bucket.
  TRIGGER: storing/streaming files bigger than 16 MB in MongoDB; the GridFS
  chunk model (default 255 KiB chunks, fs.files + fs.chunks, files_id+n unique
  index); GridFS vs a single BinData document (<16 MB) vs external object
  storage (S3); when GridFS fits (geo-distributed replica-set file sync,
  range/streaming reads) and when it does not (whole-file atomic updates);
  driver GridFS bucket upload/download APIs; custom bucket name and chunkSizeBytes.
  SKIP: files under 16 MB as BinData, mongofiles CLI mechanics, driver setup, and
  schema design -> mongodb-expert; Atlas cold-tier archival -> mongodb-atlas-expert.
version: 1.1.0
updated: 2026-07-17
model: claude-sonnet-5
effort: medium
category: mongodb
whenToUse: >-
  Use when deciding whether to store large files in MongoDB and how: choosing
  GridFS vs an inline BinData document vs external object storage, understanding
  the chunk/bucket model and its indexes, or diagnosing GridFS read/write
  behavior and its atomic-update limitation.
keywords:
  - gridfs
  - large file storage
  - fs.files
  - fs.chunks
  - chunk size
  - 16mb bson limit
  - bindata vs gridfs
  - mongofiles
  - file streaming mongodb
  - gridfs bucket
tags:
  - mongodb
  - gridfs
  - file-storage
  - bson
  - data-modeling
---

# MongoDB GridFS

> Scope: the **GridFS large-file storage specification**. For files under 16 MB
> stored directly as a `BinData` field, the `mongofiles` CLI, driver setup, and
> schema/embedding design, see `mongodb-expert` (`references/mongodb-bson-types.md`,
> `references/mongodb-database-tools.md`, `references/mongodb-developer.md`,
> `references/mongodb-schema-design.md` respectively); for Atlas cold-tier
> archival see `mongodb-atlas-expert` (`references/mongodb-atlas-online-archive.md`).
>
> `verified-as-of: 2026-07-15`, confirmed against the MongoDB Manual and driver
> docs (current + v8.0).

## Overview

**GridFS** is a specification for storing and retrieving files that exceed the
**16 MB BSON document size limit**. Instead of one document, GridFS splits a file
into **chunks** and stores them across **two collections** in a *bucket* (default
name `fs`): [^gridfs]

- **`fs.chunks`**, the binary file chunks; each document is one chunk.
- **`fs.files`**, one document of file metadata per stored file.

## Core concepts

- **Default chunk size is 255 KiB.** GridFS divides the file into 255 KiB chunks;
  only the last chunk is smaller. Configurable per bucket via `chunkSizeBytes`.
  [^gridfs]
- **Indexing:** GridFS relies on a **unique compound index** on `fs.chunks`
  over `{ files_id: 1, n: 1 }` (the file id and the chunk sequence number), plus
  an index on `fs.files`. Spec-conformant drivers **create these automatically**.
  [^gridfs]
- **Bucket naming:** the default bucket is `fs`; you can create additional named
  buckets (e.g. `photos.files` / `photos.chunks`). [^gridfs]
- **Access is via driver GridFS bucket APIs** (open upload/download streams) or
  the `mongofiles` CLI, see `mongodb-expert` (`references/mongodb-database-tools.md`). [^gridfs][^java-driver]

## When to use GridFS (decision guide)

| Situation | Use |
|---|---|
| File **> 16 MB** | **GridFS** [^gridfs] |
| All files **< 16 MB** | A single document with a **`BinData`** field, simpler, one round trip (see `mongodb-expert` `references/mongodb-bson-types.md`) [^gridfs] |
| Need files + metadata **synced across geo-distributed replica sets** | **GridFS** (MongoDB distributes chunks + metadata to all members) [^gridfs] |
| Need to read **ranges / stream portions** of a file | **GridFS** (chunking makes partial reads cheap) [^gridfs] |
| Need to **update the whole file atomically** | **Not GridFS**, GridFS cannot update an entire file's content atomically [^gridfs] |
| Large media served at scale / CDN | Consider **external object storage** (S3, etc.), outside GridFS's design point |

## Practical patterns

- **Keep application metadata in `fs.files`** (or the file document's `metadata`
  field) so you can query files without reading chunks. [^gridfs]
- **Let the driver create the indexes**, do not hand-roll the
  `{files_id:1, n:1}` unique index; spec-conformant drivers do it on first
  write. [^gridfs]
- **Tune `chunkSizeBytes`** only with evidence; 255 KiB is a sensible default for
  most workloads. [^gridfs]

## Anti-patterns

- **Using GridFS for files that all fit under 16 MB**, adds a chunking layer and
  a second collection for no benefit; store inline `BinData` instead. [^gridfs]
- **Expecting atomic whole-file replacement**, GridFS does not support updating
  the entire file content atomically; write a new file and swap the reference.
  [^gridfs]
- **Expecting atomic delete**, removing a file deletes its `fs.files` document
  and its `fs.chunks` documents as separate operations; an interrupted delete
  can leave orphaned chunks behind. [^gridfs]
- **Treating GridFS as a CDN / high-throughput media server**, that is object
  storage's job; GridFS is for keeping large files inside the database with the
  replica set's distribution and consistency.

## Troubleshooting

- **"Document too large" on insert of a big binary** → the file exceeds 16 MB;
  move it to GridFS (or object storage). [^gridfs]
- **Slow or duplicated chunk reads** → verify the `{files_id:1, n:1}` unique
  index on `fs.chunks` exists (normally driver-created). [^gridfs]
- **Cannot update a stored file in place** → expected; GridFS has no atomic
  whole-file update. Replace and repoint. [^gridfs]
- **Orphaned chunks after a failed delete** → a delete interrupted between
  removing the `fs.files` document and its `fs.chunks` documents leaves
  orphaned chunks; re-run the delete or clean up chunks matching the file's
  `_id`. [^gridfs]

## References

[^gridfs]: MongoDB Manual: GridFS (two-collection bucket model, 255 KiB default chunk, files_id+n unique index, when-to-use vs BinData, geo-distribution, no atomic whole-file update). https://www.mongodb.com/docs/manual/core/gridfs/
[^java-driver]: MongoDB Java Sync Driver: Large File Storage with GridFS (bucket API, upload/download streams). https://www.mongodb.com/docs/drivers/java/sync/current/crud/gridfs/
