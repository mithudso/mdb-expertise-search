"""operators — the built-in MQL operator table.

Each row: ``name | categories | argument kind | one-line doc``.

Categories: ``stage`` aggregation stage, ``query`` field-level query operator, ``qtop`` top-level
query operator, ``expr`` aggregation expression operator, ``acc`` accumulator / window operator,
``update`` update operator, ``mod`` update modifier, ``proj`` projection operator, ``sub`` sub-key of
another operator, ``ejson`` Extended JSON marker, ``removed`` no longer supported.

Argument kinds drive both argument checks and completion snippets:
``object``, ``array``, ``array+`` (non-empty), ``array2``, ``string``, ``bool``, ``int``, ``posint``,
``nonneg``, ``number``, ``string|object``, ``string|array``, ``any``.
"""
from __future__ import annotations

from dataclasses import dataclass

_TABLE = r"""
# ---- aggregation stages
$addFields|stage|object|Adds new fields to documents; synonym of $set.
$bucket|stage|object|Groups documents into buckets by explicit boundaries.
$bucketAuto|stage|object|Groups documents into a requested number of automatically sized buckets.
$changeStream|stage|object|Opens a change stream (must be the first stage).
$changeStreamSplitLargeEvent|stage|object|Splits change events larger than 16 MiB into fragments.
$collStats|stage|object|Returns collection statistics (must be the first stage).
$count|stage,acc|string|Stage: counts documents into a named field. Accumulator: counts documents in a group.
$currentOp|stage|object|Returns active operations (must be the first stage, run on admin).
$densify|stage|object|Creates missing documents in a sequence of values.
$documents|stage|array|Returns literal documents as the pipeline input (first stage).
$facet|stage|object|Runs several sub-pipelines on the same input, one output field each.
$fill|stage|object|Fills null or missing field values.
$geoNear|stage|object|Returns documents ordered by proximity to a point (must be the first stage).
$graphLookup|stage|object|Recursive search of a collection (graph traversal).
$group|stage|object|Groups documents by _id and computes accumulators.
$indexStats|stage|object|Returns index usage statistics (must be the first stage).
$limit|stage|posint|Passes only the first N documents.
$listLocalSessions|stage|object|Lists sessions cached in memory on the current mongod/mongos.
$listSampledQueries|stage|object|Lists sampled queries for analyzeShardKey.
$listSearchIndexes|stage|object|Returns the Atlas Search / Vector Search indexes of a collection.
$listSessions|stage|object|Lists sessions in system.sessions.
$lookup|stage|object|Left outer join with another collection (localField/foreignField or pipeline).
$match|stage|object|Filters documents with query syntax.
$merge|stage|string|object|Writes pipeline output into a collection, merging with existing documents (last stage).
$out|stage|string|object|Writes pipeline output to a collection, replacing it (last stage).
$planCacheStats|stage|object|Returns plan cache information (must be the first stage).
$project|stage|object|Includes, excludes or computes fields.
$queryStats|stage|object|Returns runtime statistics for recorded query shapes.
$rankFusion|stage|object|Combines several ranked pipelines with reciprocal rank fusion.
$redact|stage|any|Restricts document content based on stored access levels ($$PRUNE/$$KEEP/$$DESCEND).
$replaceRoot|stage|object|Replaces the document with the given embedded document.
$replaceWith|stage|any|Replaces the document with the given document; alias for $replaceRoot.
$sample|stage|object|Randomly selects N documents.
$score|stage|object|Assigns a relevance score to documents.
$scoreFusion|stage|object|Combines several scored pipelines into one ranking.
$search|stage,sub|object|Atlas Search full-text query (must be the first stage).
$searchMeta|stage|object|Returns Atlas Search metadata (counts, facets) instead of documents.
$set|stage,update|object|Stage: adds or overwrites fields. Update operator: sets field values.
$setMetadata|stage|object|Sets document metadata such as score.
$setWindowFields|stage|object|Computes window-function output over partitions of documents.
$shardedDataDistribution|stage|object|Returns data distribution information for sharded collections.
$skip|stage|nonneg|Skips the first N documents.
$sort|stage,mod|object|Stage: sorts documents. Update modifier: sorts array elements inside $push.
$sortByCount|stage|any|Groups by an expression and counts, sorted descending.
$unionWith|stage|string|object|Appends the results of another collection or pipeline.
$unset|stage,update|string|array|Stage: removes fields. Update operator: removes fields from documents.
$unwind|stage|string|object|Deconstructs an array field into one document per element.
$vectorSearch|stage|object|Atlas Vector Search approximate nearest-neighbour query (must be the first stage).
# ---- query: top level
$and|qtop,expr|array+|Logical AND over a non-empty array of conditions.
$or|qtop,expr|array+|Logical OR over a non-empty array of conditions.
$nor|qtop|array+|Matches documents that fail all conditions.
$comment|qtop|any|Attaches a comment to a query for logs and profiler.
$expr|qtop|any|Uses aggregation expressions inside a query (can compare fields).
$jsonSchema|qtop|object|Matches documents that validate against a JSON Schema.
$sampleRate|qtop,expr|number|Matches a random fraction (0-1) of documents.
$text|qtop|object|Text search on a text index; needs $search; must be the first $match in a pipeline.
$where|qtop|any|Matches using a JavaScript expression (slow; avoid, not allowed in $match).
# ---- query: field level
$eq|query,expr|any|Equals (query) / equality comparison (expression).
$gt|query,expr|any|Greater than.
$gte|query,expr|any|Greater than or equal.
$lt|query,expr|any|Less than.
$lte|query,expr|any|Less than or equal.
$ne|query,expr|any|Not equal.
$in|query,expr|array|Matches any value in the array (query) / tests array membership (expression).
$nin|query|array|Matches none of the values in the array.
$exists|query|bool|Matches documents that have (true) or lack (false) the field.
$type|query,expr|any|Matches by BSON type (query) / returns the BSON type name (expression).
$regex|query,sub|any|Regular-expression match; optional $options sibling.
$options|query,sub|string|Regex flags (i, m, x, s) for $regex.
$mod|query,expr|array2|Modulo: [divisor, remainder] (query) / remainder of division (expression).
$all|query|array|Matches arrays containing all listed elements.
$elemMatch|query,proj|object|Matches arrays with an element satisfying all conditions; also a projection operator.
$size|query,expr|int|Matches arrays of the given length (query) / returns array length (expression).
$not|query,expr|any|Inverts an operator expression (query) / boolean NOT (expression).
$bitsAllClear|query|any|Matches if all given bit positions are 0.
$bitsAllSet|query|any|Matches if all given bit positions are 1.
$bitsAnyClear|query|any|Matches if any given bit position is 0.
$bitsAnySet|query|any|Matches if any given bit position is 1.
$geoIntersects|query|object|Matches geometries that intersect a GeoJSON geometry.
$geoWithin|query|object|Matches geometries inside a shape.
$near|query|object|Returns documents near a point, sorted by distance (needs geospatial index).
$nearSphere|query|object|Like $near on a sphere (meters for GeoJSON).
# ---- sub-keys of other operators
$geometry|sub|object|GeoJSON geometry for geo operators.
$maxDistance|sub|number|Maximum distance for $near/$nearSphere.
$minDistance|sub|number|Minimum distance for $near/$nearSphere.
$box|sub|array|Bottom-left and top-right corners for $geoWithin.
$polygon|sub|array|Polygon vertices for $geoWithin.
$center|sub|array|Circle [center, radius] for $geoWithin (flat).
$centerSphere|sub|array|Circle [center, radians] for $geoWithin (spherical).
$language|sub|string|Language for $text.
$caseSensitive|sub|bool|Case-sensitive $text search.
$diacriticSensitive|sub|bool|Diacritic-sensitive $text search.
# ---- projection / sort misc
$slice|proj,expr,mod|any|Projection/expression: subset of an array. Update modifier: caps array length in $push.
$meta|proj,expr,sub|string|Metadata such as textScore, indexKey, searchScore.
$natural|sub|int|Natural (on-disk) order for sort() or hint().
# ---- expression operators
$abs|expr|any|Absolute value.
$add|expr|array|Adds numbers or dates.
$ceil|expr|any|Smallest integer greater than or equal.
$divide|expr|array2|Divides the first number by the second.
$exp|expr|any|Raises e to a power.
$floor|expr|any|Largest integer less than or equal.
$ln|expr|any|Natural logarithm.
$log|expr|array2|Logarithm in a given base.
$log10|expr|any|Base-10 logarithm.
$multiply|expr|array|Multiplies numbers.
$pow|expr|array2|Raises a number to an exponent.
$round|expr|any|Rounds to an integer or decimal place.
$sqrt|expr|any|Square root.
$subtract|expr|array2|Subtracts numbers or dates.
$trunc|expr|any|Truncates to an integer or decimal place.
$sin|expr|any|Sine.
$cos|expr|any|Cosine.
$tan|expr|any|Tangent.
$asin|expr|any|Inverse sine.
$acos|expr|any|Inverse cosine.
$atan|expr|any|Inverse tangent.
$atan2|expr|array2|Inverse tangent of y/x.
$sinh|expr|any|Hyperbolic sine.
$cosh|expr|any|Hyperbolic cosine.
$tanh|expr|any|Hyperbolic tangent.
$asinh|expr|any|Inverse hyperbolic sine.
$acosh|expr|any|Inverse hyperbolic cosine.
$atanh|expr|any|Inverse hyperbolic tangent.
$degreesToRadians|expr|any|Converts degrees to radians.
$radiansToDegrees|expr|any|Converts radians to degrees.
$arrayElemAt|expr|array2|Element at an array index (negative counts from the end).
$arrayToObject|expr|any|Converts an array of key/value pairs to an object.
$concatArrays|expr|array|Concatenates arrays.
$filter|expr|object|Selects array elements matching a condition.
$first|expr,acc|any|Accumulator: first value in a group. Expression: first array element.
$firstN|expr,acc|object|First N elements/values.
$indexOfArray|expr|array|Index of a value in an array, or -1.
$isArray|expr|any|True if the value is an array.
$last|expr,acc|any|Accumulator: last value in a group. Expression: last array element.
$lastN|expr,acc|object|Last N elements/values.
$map|expr|object|Applies an expression to each array element.
$maxN|expr,acc|object|Largest N values.
$minN|expr,acc|object|Smallest N values.
$objectToArray|expr|any|Converts an object to an array of {k, v} pairs.
$range|expr|array|Generates a number sequence.
$reduce|expr|object|Folds an array to a single value.
$reverseArray|expr|any|Reverses an array.
$sortArray|expr|object|Sorts an array by elements or fields.
$zip|expr|object|Transposes arrays into an array of arrays.
$cmp|expr|array2|Compares two values: -1, 0 or 1.
$cond|expr|any|If/then/else; array [if, then, else] or {if, then, else}.
$ifNull|expr|array|First non-null value.
$switch|expr|object|Multi-branch conditional with branches and default.
$accumulator|expr,acc|object|Custom JavaScript accumulator.
$function|expr|object|Custom JavaScript function (not allowed on Atlas free/shared tiers).
$binarySize|expr|any|Size in bytes of a string or binary value.
$bsonSize|expr|any|Size in bytes of a document as BSON.
$dateAdd|expr|object|Adds a time unit to a date.
$dateDiff|expr|object|Difference between two dates in a unit.
$dateFromParts|expr|object|Builds a date from components.
$dateFromString|expr|object|Parses a date string.
$dateSubtract|expr|object|Subtracts a time unit from a date.
$dateToParts|expr|object|Splits a date into components.
$dateToString|expr|object|Formats a date as a string.
$dateTrunc|expr|object|Truncates a date to a unit.
$dayOfMonth|expr|any|Day of month (1-31).
$dayOfWeek|expr|any|Day of week (1-7, Sunday = 1).
$dayOfYear|expr|any|Day of year (1-366).
$hour|expr|any|Hour (0-23).
$isoDayOfWeek|expr|any|ISO day of week (1-7, Monday = 1).
$isoWeek|expr|any|ISO week number.
$isoWeekYear|expr|any|ISO week-numbering year.
$millisecond|expr|any|Milliseconds (0-999).
$minute|expr|any|Minute (0-59).
$month|expr|any|Month (1-12).
$second|expr|any|Second (0-59).
$week|expr|any|Week of year (0-53).
$year|expr|any|Year.
$tsSecond|expr|any|Seconds of a timestamp.
$tsIncrement|expr|any|Increment ordinal of a timestamp.
$literal|expr|any|Returns the value without evaluating it.
$getField|expr|any|Reads a field value (supports names with $ or .).
$setField|expr|object|Sets a field on an object.
$unsetField|expr|object|Removes a field from an object.
$rand|expr|any|Random float in [0, 1).
$mergeObjects|expr,acc|any|Merges documents.
$allElementsTrue|expr|array|True if all array elements are true.
$anyElementTrue|expr|array|True if any array element is true.
$setDifference|expr|array2|Elements in the first set not in the second.
$setEquals|expr|array|True if sets are equal.
$setIntersection|expr|array|Elements common to all sets.
$setIsSubset|expr|array2|True if the first set is a subset of the second.
$setUnion|expr|array|Union of sets.
$concat|expr|array|Concatenates strings.
$indexOfBytes|expr|array|UTF-8 byte index of a substring.
$indexOfCP|expr|array|Code-point index of a substring.
$ltrim|expr|object|Trims leading characters.
$regexFind|expr|object|First regex match in a string.
$regexFindAll|expr|object|All regex matches in a string.
$regexMatch|expr|object|True if the string matches the regex.
$replaceOne|expr|object|Replaces the first occurrence of a string.
$replaceAll|expr|object|Replaces all occurrences of a string.
$rtrim|expr|object|Trims trailing characters.
$split|expr|array2|Splits a string by a delimiter.
$strLenBytes|expr|any|String length in UTF-8 bytes.
$strLenCP|expr|any|String length in code points.
$strcasecmp|expr|array2|Case-insensitive string comparison.
$substr|expr|array|Deprecated alias of $substrBytes.
$substrBytes|expr|array|Substring by UTF-8 bytes.
$substrCP|expr|array|Substring by code points.
$toLower|expr|any|Lowercases a string.
$toUpper|expr|any|Uppercases a string.
$trim|expr|object|Trims leading and trailing characters.
$convert|expr|object|Converts a value to a type with error handling.
$isNumber|expr|any|True if the value is numeric.
$toBool|expr|any|Converts to boolean.
$toDate|expr|any|Converts to date.
$toDecimal|expr|any|Converts to Decimal128.
$toDouble|expr|any|Converts to double.
$toInt|expr|any|Converts to 32-bit integer.
$toLong|expr|any|Converts to 64-bit integer.
$toObjectId|expr|any|Converts to ObjectId.
$toString|expr|any|Converts to string.
$let|expr|object|Defines variables for use in an expression.
$bitAnd|expr|array|Bitwise AND.
$bitNot|expr|any|Bitwise NOT.
$bitOr|expr|array|Bitwise OR.
$bitXor|expr|array|Bitwise XOR.
$toHashedIndexKey|expr|any|Computes the hashed index key of a value.
# ---- accumulators and window operators
$addToSet|acc,update|any|Accumulator: set of distinct values. Update: adds to an array if absent.
$avg|acc,expr|any|Average of numeric values.
$bottom|acc|object|Bottom element of a group by sortBy.
$bottomN|acc|object|Bottom N elements of a group by sortBy.
$covariancePop|acc|array2|Population covariance (window).
$covarianceSamp|acc|array2|Sample covariance (window).
$denseRank|acc|object|Dense rank in a window (no gaps).
$derivative|acc|object|Derivative over a window.
$documentNumber|acc|object|Position of a document in its partition.
$expMovingAvg|acc|object|Exponential moving average (window).
$integral|acc|object|Integral over a window.
$linearFill|acc|any|Fills nulls by linear interpolation (window).
$locf|acc|any|Last observation carried forward (window).
$max|acc,expr,update|any|Largest value (accumulator/expression) or update-if-greater.
$median|acc,expr|object|Approximate median.
$min|acc,expr,update|any|Smallest value (accumulator/expression) or update-if-smaller.
$percentile|acc,expr|object|Approximate percentiles.
$push|acc,update|any|Accumulator: array of values. Update: appends to an array.
$rank|acc|object|Rank in a window (gaps for ties).
$shift|acc|object|Value from another position in the window.
$stdDevPop|acc,expr|any|Population standard deviation.
$stdDevSamp|acc,expr|any|Sample standard deviation.
$sum|acc,expr|any|Sum of numeric values.
$top|acc|object|Top element of a group by sortBy.
$topN|acc|object|Top N elements of a group by sortBy.
# ---- update operators and modifiers
$currentDate|update|object|Sets a field to the current date or timestamp.
$inc|update|object|Increments numeric fields.
$mul|update|object|Multiplies numeric fields.
$rename|update|object|Renames fields.
$setOnInsert|update|object|Sets fields only when an upsert inserts.
$pop|update|object|Removes the first (-1) or last (1) array element.
$pull|update|object|Removes array elements matching a condition.
$pullAll|update|object|Removes all listed values from an array.
$bit|update|object|Bitwise and/or/xor update of an integer field.
$each|mod|array|Modifier for $push/$addToSet: append several elements.
$position|mod|int|Modifier for $push: insert position.
# ---- removed
$pushAll|removed|array|Removed in MongoDB 3.6; use $push with $each.
$isolated|removed|any|Removed in MongoDB 4.0; use transactions.
# ---- extended JSON
$oid|ejson|string|Extended JSON ObjectId.
$date|ejson|any|Extended JSON date.
$numberInt|ejson|string|Extended JSON int32.
$numberLong|ejson|string|Extended JSON int64.
$numberDouble|ejson|string|Extended JSON double.
$numberDecimal|ejson|string|Extended JSON Decimal128.
$binary|ejson|object|Extended JSON binary.
$uuid|ejson|string|Extended JSON UUID.
$timestamp|ejson|object|Extended JSON timestamp.
$regularExpression|ejson|object|Extended JSON regex.
$minKey|ejson|any|Extended JSON MinKey.
$maxKey|ejson|any|Extended JSON MaxKey.
$undefined|ejson|any|Extended JSON undefined.
$symbol|ejson|string|Extended JSON symbol.
$code|ejson|string|Extended JSON JavaScript code.
$scope|ejson|object|Scope for Extended JSON code.
$dbPointer|ejson|object|Extended JSON DBPointer.
$ref|ejson|string|DBRef collection.
$id|ejson|any|DBRef id.
$db|ejson|string|DBRef database.
"""

#: System variables usable as ``$$NAME`` in aggregation expressions.
VARIABLES = {
    "NOW": "Current datetime, constant across the whole operation.",
    "CLUSTER_TIME": "Current timestamp (replica sets and sharded clusters only).",
    "ROOT": "The top-level document currently being processed.",
    "CURRENT": "The current path/document; defaults to ROOT.",
    "REMOVE": "Removes a field from the output when used as its value.",
    "DESCEND": "$redact: keep this level and examine embedded documents.",
    "PRUNE": "$redact: drop this document and everything under it.",
    "KEEP": "$redact: keep this document and everything under it.",
    "SEARCH_META": "Atlas Search metadata returned by $search.",
    "USER_ROLES": "Roles of the current user (for $redact access control).",
}


@dataclass(frozen=True)
class Operator:
    name: str
    cats: frozenset[str]
    arg: str
    doc: str

    def is_a(self, *cats: str) -> bool:
        return bool(self.cats & set(cats))


def _load() -> dict[str, Operator]:
    out: dict[str, Operator] = {}
    for line in _TABLE.strip().splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split("|")
        # docs may themselves contain '|': args kind may be 'string|object', so rejoin carefully
        name, cats = parts[0], parts[1].split(",")
        rest = parts[2:]
        kinds = {"object", "array", "array+", "array2", "string", "bool", "int", "posint",
                 "nonneg", "number", "any"}
        arg = rest[0]
        i = 1
        while i < len(rest) and rest[i] in kinds and rest[0] in kinds:
            arg += "|" + rest[i]
            i += 1
        doc = "|".join(rest[i:])
        out[name] = Operator(name, frozenset(cats), arg, doc.strip())
    return out


OPERATORS: dict[str, Operator] = _load()

STAGES = frozenset(n for n, o in OPERATORS.items() if "stage" in o.cats)
UPDATE_OPS = frozenset(n for n, o in OPERATORS.items() if "update" in o.cats)
FIRST_STAGE_ONLY = frozenset({
    "$geoNear", "$collStats", "$indexStats", "$changeStream", "$currentOp", "$listSessions",
    "$listLocalSessions", "$documents", "$search", "$searchMeta", "$vectorSearch",
    "$planCacheStats", "$listSampledQueries", "$queryStats", "$shardedDataDistribution",
    "$listSearchIndexes",
})
LAST_STAGE_ONLY = frozenset({"$out", "$merge"})
NOT_IN_FACET = frozenset({
    "$collStats", "$facet", "$geoNear", "$indexStats", "$out", "$merge", "$planCacheStats",
    "$search", "$searchMeta", "$vectorSearch",
})
UPDATE_PIPELINE_STAGES = frozenset({
    "$addFields", "$set", "$project", "$unset", "$replaceRoot", "$replaceWith",
})


def get(name: str) -> Operator | None:
    return OPERATORS.get(name)


def suggest(name: str, n: int = 3) -> list[str]:
    import difflib

    return difflib.get_close_matches(name, list(OPERATORS), n=n, cutoff=0.72)
