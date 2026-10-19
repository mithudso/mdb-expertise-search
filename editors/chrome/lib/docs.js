// Public MongoDB documentation for each optimizer finding code (shown as "MongoDB docs" links in the
// popup and the Markdown report). URLs are checked by scripts/check_chrome_doc_links.py.
const M = "https://www.mongodb.com/docs/manual/";

export const ESR_DOC = M + "tutorial/equality-sort-range-rule/";

export const DOCS = {
  "where": M + "reference/operator/query/where/",
  "unanchored-regex": M + "reference/operator/query/regex/",
  "case-insensitive-regex": M + "reference/operator/query/regex/",
  "negation": M + "reference/operator/query/ne/",
  "kv-without-elemmatch": M + "reference/operator/query/elemMatch/",
  "huge-in": M + "reference/operator/query/in/",
  "large-in": M + "reference/operator/query/in/",
  "in-blocks-sort": M + "reference/operator/query/in/",
  "string-numeric-compare": M + "reference/bson-type-comparison-order/",
  "or-to-in": M + "reference/operator/query/or/",
  "rooted-or-sort": M + "reference/operator/query/or/",
  "or-branch-indexes": M + "reference/operator/query/or/",
  "degenerate-range": ESR_DOC,
  "expr-unindexable": M + "reference/operator/query/expr/",
  "deep-skip": M + "reference/method/cursor.skip/",
  "sort-no-limit": M + "reference/method/cursor.sort/",
  "pinned-hint": M + "reference/command/setQuerySettings/",
  "tiny-batch": M + "reference/method/cursor.batchSize/",
  "legacy-count": M + "reference/method/db.collection.countDocuments/",
  "count-all": M + "reference/method/db.collection.estimatedDocumentCount/",
  "distinct-16mb": M + "reference/method/db.collection.distinct/",
  "match-not-early": M + "core/aggregation-pipeline-optimization/",
  "group-root": M + "reference/operator/aggregation/group/",
  "push-then-slice": M + "reference/operator/aggregation/topN/",
  "distinct-scan-eligible": M + "reference/operator/aggregation/group/",
  "group-whole-collection": M + "reference/operator/aggregation/merge/",
  "lookup-pipeline": M + "reference/operator/aggregation/lookup/",
  "sample-not-first": M + "reference/operator/aggregation/sample/",
  "sort-after-search": "https://www.mongodb.com/docs/atlas/atlas-search/sort/",
  "search-overfetch": "https://www.mongodb.com/docs/atlas/atlas-search/sort/",
  "changestream-match-first": M + "changeStreams/",
  "log-collscan": M + "reference/explain-results/",
  "log-scan-ratio": M + "reference/explain-results/",
  "log-blocking-sort": M + "reference/method/cursor.sort/",
  "log-spill": M + "core/aggregation-pipeline-limits/",
  "log-replanned": M + "core/query-plans/",
  "log-timeout-bound": M + "reference/method/cursor.maxTimeMS/",
};

export function docFor(code) {
  return DOCS[code] ?? null;
}
