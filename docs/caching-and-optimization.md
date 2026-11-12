# Caching and optimization

Vector bytes remain keyed by the historical text digest. A separate input hash
records the actual heading-plus-text embedding input for newly validated builds.
Keyword rebuilds mark changed or unproven cached inputs ineligible for retrieval;
they retain historical vector bytes. Explicit semantic generation validates model,
shape, cardinality, dimensions and finite positive norms before publication. A
model change keeps its old generation until the full replacement is ready.

VectorStore detects local and externally committed database changes before reuse.
Search checks model identity, validates query dimensions and rejects malformed
vectors. Source filters treat percent and underscore literally. Deduplication uses
the entire whitespace-normalized text; ranked candidates are not capped before
unique results are selected. FTS5 BM25 weights remain heading4/text1/source2.

This maintenance generated no live vectors and refreshed no live index. Legacy
short-section chunk anchors remain approximate; a precise format requires an
explicit migration of frozen fixtures and semantic cache identity. Full candidate
semantic generations currently use memory proportional to the missing vectors;
a disk-backed staging design is a future scale decision.
