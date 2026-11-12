# Caching and optimization

Vector bytes remain keyed by the historical text digest. A separate input hash
records the actual heading-plus-text embedding input for validated builds.
Keyword rebuilds mark changed or unproven cached inputs ineligible for retrieval;
they retain historical vector bytes. Explicit semantic builds stage bounded batches
in an invocation-owned temporary SQLite database. Publication validates the complete
candidate generation, captured model, current input hashes and dimensions under a
writer lock. The old generation remains until validation succeeds. No live vectors
or index were generated during this maintenance.

The builder records the validated dimension with the model identity. Incompatible
current rows are pending repair. Legacy mixed dimensions require a complete staged
candidate; unreferenced or unproven old vectors do not constrain its dimension.
A structurally coherent legacy cache cannot independently prove provider identity;
unlabelled vectors still require an explicit provenance migration.

VectorStore checks database identity, transactional revision, local monotonic change
count and external commit version before reuse. A rollback cannot make its matrix
appear current at a repeated revision. Hybrid search embeds its query outside the
read transaction, then retrieves both keyword and semantic ranks from one snapshot.
TUI and MCP reuse connection-local matrices without sharing SQLite connections
across worker threads. Query/model mismatches produce the documented keyword fallback.

Source substring filters reproduce SQLite ASCII LIKE case behavior and treat percent
and underscore literally. Deduplication uses the whole whitespace-normalized text;
ranked candidates are streamed until enough distinct results exist. FTS5 BM25 weights
remain heading4/text1/source2. Export rejects a weighted frequency that exceeds the
existing uint16 representation, preserving the previous export instead of clamping
or silently changing its on-disk format.

Historical short-section chunk anchors remain approximate. Precise line/breadcrumb
metadata and oversized heading representation need a separately authorized migration
of frozen search fixtures and embedding identities. Production chunk_text and
_merge_tiny remain unchanged in this maintenance.
