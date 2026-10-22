# mdb-expertise-search

Hybrid **keyword + semantic** search, a **static MQL query optimizer**, an MQL linter/language server and
24+ runbooks — as a CLI, a terminal UI, an MCP server for AI agents and an editor extension — over a curated
MongoDB / Atlas expertise corpus: expert skills (indexes, aggregation, schema design, replication, sharding,
operations, Atlas, diagnostics, drivers, error codes), source-anchored MQL query-optimization fact packs and
`llms.txt` exports of the MongoDB docs.

## Why use it

| You want to… | Without mdbx | With mdbx |
|---|---|---|
| Know why a query is slow before it ships | Run it on a big dataset, read `explain()` by hand | `mdbx optimize q.mql` names the defect, the audit pass, the fix and the index — offline, in milliseconds |
| Get the right compound index | Remember ESR, the 201-element `$in` rule, covered-query disqualifiers | It prints `createIndex(...)` in Equality → Sort → Range order with the reason, and tells you when to test ERS |
| Answer "how does X work in MongoDB" | Search the manual, forums and old tickets | One query over expert notes + docs facts, each fact ending in its source URL |
| Catch MQL mistakes while typing | Find them at runtime (`$gtt`, `$group` without `_id`, `$out` not last) | The language server underlines them with a quick fix |
| Give an AI agent real MongoDB knowledge | Hope the model remembers | `mdbx mcp` gives it search, recipes, lint and the optimizer as tools |
| Follow a safe procedure (shard, upgrade, restore) | Stitch steps from several pages | `mdbx recipe shard a collection` — prerequisites, steps, verify, rollback |

Everything runs locally. Search works without network access (keyword mode); semantic search uses a local
[Ollama](https://ollama.com) model when one is running.

## What it can do — examples

### 1. Optimize a query (static MQL optimizer)

```console
$ echo 'db.events.find({ $or: [{ type: "click" }, { type: "view" }], ts: { $gte: 5, $lte: 5 } }).sort({ ts: -1 }).limit(50)' | mdbx optimize -
MQL optimizer (static audit) — -: 1 query, no open findings; 2 rewrite(s) applied in 1 iteration(s)

Applied rewrites (result-preserving):
  ✓ [P4 or-to-in] $or of equalities on one field (type) is an $in: one index scan with point bounds instead of a subplan per branch, and sort-compatible.
  ✓ [P4 degenerate-range] ts: $gte and $lte carry the same value, which is an equality the planner treats as a range (breaks ESR key order and invites near-tied plans).

Recommended indexes (recommend-only — build on non-prod first, check existing indexes):
  db.events.createIndex({ type: 1, ts: 1 })
      ESR order: equality type, ts.

Rewritten query:
db.events.find({ type: { $in: ["click", "view"] }, ts: 5 }).sort({ ts: -1 }).limit(50)
```

It audits `find`, `aggregate`, `count`/`countDocuments`, `distinct`, update/delete filters and change-stream
pipelines, including pipelines stored in `const` variables. It also reads what you paste from a case:
**slow-query log lines** (several at once; `getMore` lines use `originatingCommand`), **profiler entries**,
**command documents** (`{ find: …, filter: …, sort: … }`) and bare filters or pipelines — and turns the
logged measurements into evidence findings (COLLSCAN, `docsExamined` ≫ `nreturned`, in-memory sort, disk
spill, replanning, duration pinned at `maxTimeMS`). Rules come from the deep MQL query optimizer skill
(passes P2 index use, P4 operator anti-patterns, P5 stage order, P6 sort/cursor cost, P7 projection,
P8 pagination). Among them:

- **Blocking (reported, never rewritten — they change results):** numbers compared as strings
  (`{ qty: { $gte: "10" } }`), key/value attribute predicates outside `$elemMatch`.
- **High:** `$where` (deprecated in 8.0), `$push: "$$ROOT"` in `$group`, unbounded `$push` later `$slice`d
  (use `$topN`/`$firstN`), `$in` with 10,000+ values.
- **Medium:** unanchored or case-insensitive regex, `$ne`/`$nin`/`$exists: false`, `$in` ≥ 201 values ahead of
  a sort, rooted `$or` + sort (SERVER-19114), unindexable `$expr`, deep `skip()`/`$skip`, `batchSize(2)`,
  `$match` buried after stages it does not depend on, `$sort` after `$search`, `$sample` not first.
- **Auto-applied rewrites:** same-field `$or` → `$in`, degenerate range → equality, `$match` hoisting
  (layout preserved), `countDocuments({})` → `estimatedDocumentCount()`. It loops until nothing changes (cap 3).
- **Index recommendations:** ESR-ordered `createIndex`, one per `$or` branch, `$lookup` foreign-field indexes,
  covered-query hints (`add _id: 0`, `PROJECTION_COVERED`).

Every finding links the corpus page that explains it (`read more: mdbx show …`). Try the bundled example:
`mdbx optimize examples/slow-queries.mql` (5 queries, 10 findings, 4 rewrites, 5 index recommendations).
Flags: `--read-only`, `--write` (rewrite the file in place), `--json`. Exit code 1 when a high or blocking
finding remains, so it can gate CI. See the walkthrough in [docs/DEMO-mql-optimizer.md](docs/DEMO-mql-optimizer.md).

### 2. Search the expertise corpus

```console
$ mdbx search -m keyword -n 3 "in 201 elements SORT_MERGE blocking sort"
 1. [llms] mongodb-query-shape-optimization  ·  enable , DISTINCT_SCAN > Problems, failure modes and limitations
    llms/mongodb-query-shape-optimization.llms/llms-facts.txt:1160   score=26.3012 via=keyword
     … With a [sort], $in under [201] [elements] expands and merges via a [SORT_MERGE] stage (acts like equality); at [201] or more it behaves like …

 2. [llms] mongodb-query-shape-optimization  ·  enable , DISTINCT_SCAN > Problems, failure modes and limitations
    llms/mongodb-query-shape-optimization.llms/llms-facts.txt:1183   score=25.6035 via=keyword
     … With .[sort](), an $in of fewer than [201] [elements] is expanded and merged in index [sort] order by a [SORT_MERGE] stage, behaving like equality …

 3. [skill] mongodb-expert  ·  MongoDB Query Shape Optimization: Sort, Pagination, Operators and Sharded Targeting > Overview
    skills/mongodb-expert/references/mongodb-query-shape-optimization.md:28   score=25.5302 via=keyword
     … [sort], $in under [201] [elements] is expanded and merged by [SORT_MERGE] (equality-like under ESR); [201]+ [elements] act like a range and [block] index …
```

Filter by kind (`-k skill|llms|recipe`) or source (`-s compound-index`), print whole chunks (`--full`) or JSON.
Other good first questions: `"why is my compound index not used for sort"`, `"setQuerySettings vs hint"`,
`"time series metaField cardinality"`, `"DISTINCT_SCAN $first"`, `"oplog window too small"`.

### 3. Lint MQL while you type

```console
$ mdbx lint examples/orders.mql
examples/orders.mql:5:35: error: Unknown operator $gtt. Did you mean $gt? [unknown-operator]
examples/orders.mql:6:13: error: $group requires an _id field (use _id: null to aggregate all documents). [missing-field]
examples/orders.mql:7:21: error: Sort order for 'total' must be 1, -1 or { $meta: … }. [bad-argument]
examples/orders.mql:8:14: error: $unwind path must start with '$' (e.g. "$items"). [bad-argument]
examples/orders.mql:9:5: error: $out must be the last stage of the pipeline. [stage-position]
examples/orders.mql:14:53: error: 'note' mixes a plain field with update operators; wrap it in $set. [update-shape]
```

In an editor, `mql-lsp` shows the same diagnostics **plus the optimizer's findings** (source `mql-optimizer`),
completion by context, hover docs with corpus hits, an outline and quick fixes — VS Code, Neovim and Helix
configs ship in `editors/`.

### 4. Give an AI agent MongoDB tools (MCP)

`mdbx mcp` exposes `mdb_search`, `mdb_show`, `mdb_recipes`, `mdb_recipe`, `mdb_stats`, `mql_lint`,
`mql_operator` and `mql_optimize`. Ask Claude Code, Cursor or any MCP client "optimize this pipeline" and it gets
structured findings, index recommendations and the rewritten text (abridged):

```json
{"applied": [{"code": "or-to-in", "pass": "P4"}],
 "indexes": [{"shell": "db.c.createIndex({ a: 1 })", "rationale": "ESR order: equality a."}],
 "rewritten": "db.c.find({ a: { $in: [1, 2] } })"}
```

### 5. Follow a runbook

```console
$ mdbx recipes optimize
optimize-an-mql-query  [atlas/self-managed]  Run the static MQL optimizer on a find(), aggregation or write filter, apply its result-preserving rewrites, build the ESR index it recommends on non-prod, and confirm the gain with explain("executionStats").
$ mdbx recipe shard a collection
```

25 recipes: shard / reshard, Private Link, peering, upgrades and FCV rollback, backup and PITR restore, TTL and
Online Archive, Atlas Search and Vector Search indexes, encryption, SSO, alerts, safe index builds, slow-query
diagnosis and query optimization. See [docs/RECIPES.md](docs/RECIPES.md).

### 6. Browse in the terminal

`mdbx tui` — search with mode/kind cycling, MongoDB-area facets, topic hotkeys and a recipe browser.

### 7. All of it in Chrome (extension)

The **MongoDB Expertise** extension packages the corpus and its search index (~10 MB zip) with the optimizer,
linter, recipes and operator reference, so a TSE needs nothing but Chrome:

- Highlight a query or slow-query log line in a case, ticket or chat → click the icon (or **Alt+Shift+O**) →
  findings, log evidence, safe rewrites, index advice, **Copy as Markdown** for the case note.
- Highlight an error message or a question → the popup shows the best corpus passages.
- Type `mdb <question>` in the address bar, or open the app: Search (same BM25 ranking as `mdbx search`, area
  facets, document view; optional hybrid search with a local Ollama), Recipes, Optimize, Lint, Operators.
- Runs locally: no network access, `activeTab` only; only committed (redacted) corpus files are packaged.

Build it with `python scripts/package_chrome_extension.py`; install and team rollout:
[editors/chrome/README.md](editors/chrome/README.md). An unpacked install keeps itself current:
`python scripts/chrome_extension_autoupdate.py install-agent` polls GitHub, rebuilds after every push to `main`
and the extension reloads itself.

### 8. Ask a question, grounded in the corpus

```bash
$ mdbx ask "Why does my $lookup with a $match after it scan the whole foreign collection?"
A $match after $lookup cannot be pushed into the foreign collection scan; move the filter into the
$lookup pipeline (sub-pipeline form) or into a preceding $match on the local side [1][3] …

Sources:
  [1] mongodb-expert · Aggregation > $lookup  (skills/mongodb-expert/SKILL.md:412)
  [3] query-optimization-facts · $lookup pushdown  (llms/qo.llms/llms.txt:88)
[claude · oauth · claude-sonnet-5-5]
```

`mdbx ask` sends the question plus the best corpus passages to the first configured provider (Claude, Codex,
Antigravity, in the order you set with `mdbx auth prefer`) and falls back to on-device Apple Intelligence on a
Mac that has it, so the command works offline too. `mdbx glean "…"` searches Glean the same way: API token,
then an OAuth session, then the Glean CLI through `scripts/glean_cli_helper.py`.

## Quick start

```bash
git clone https://github.com/mithudso/mdb-expertise-search && cd mdb-expertise-search
python3 -m venv .venv && .venv/bin/pip install -e '.[all]'     # or pick: tui, lsp, mcp
ollama pull nomic-embed-text            # optional; enables semantic search
.venv/bin/mdbx index                    # builds data/mdbx.sqlite (keyword + vectors)
.venv/bin/mdbx optimize examples/slow-queries.mql
.venv/bin/mdbx search "why is my compound index not used for sort"
.venv/bin/mdbx tui
```

To get `mdbx` (and `mql-lsp`) on your PATH everywhere, install it as an editable tool instead; it still
reads this checkout's `corpus/` and `data/`, and picks up `git pull` changes without reinstalling:

```bash
uv tool install --editable '.[all]'     # or: pipx install --editable '.[all]'  -> ~/.local/bin/mdbx
mdbx index && mdbx tui
```

## Commands

| Command | Purpose |
|---|---|
| `mdbx index [--skip-semantic]` | Build the FTS5 index and embed any new chunks (resumable) |
| `mdbx search QUERY [-m hybrid\|keyword\|semantic] [-k skill\|llms\|memory\|recipe] [-s SOURCE] [-n N] [--full] [--json]` | Search |
| `mdbx optimize FILE [--read-only] [--write] [--json]` | Static MQL query optimizer for mongosh, log lines, profiler entries, commands (`-` for stdin; alias `opt`); exit 1 on high/blocking |
| `mdbx lint FILE` | Lint MQL (`-` for stdin); exit 1 on errors |
| `mdbx export-web OUT [--no-vectors]` | Write the corpus + search index as static files for the Chrome extension (committed files only) |
| `mdbx show PATH` | Print a corpus file (path as shown in results) |
| `mdbx stats [--sources]` | Index statistics |
| `mdbx recipes [WORDS]` / `mdbx recipe NAME` | List / print step-by-step recipes |
| `mdbx tui` | Interactive browser |
| `mdbx ask QUESTION [-p claude\|codex\|antigravity\|apple] [-n N] [-k KIND] [--json]` | Answer from corpus passages with the first available AI provider; falls back to on-device Apple Intelligence (`ai` extra) |
| `mdbx auth status\|set-key\|login\|unset\|mode\|prefer\|test` | AI provider credentials: API keys in the Keychain, or OAuth through the vendor CLIs / Glean PKCE ([docs/INSTALLATION.md](docs/INSTALLATION.md#ai-providers-mdbx-ask-mdbx-glean-mdbx-auth)) |
| `mdbx glean QUERY [-n N] [-d DATASOURCE] [--json]` | Search Glean: API token → OAuth session → Glean CLI helper (`scripts/glean_cli_helper.py`) |
| `mdbx mcp` | MCP server over stdio ([docs/MCP.md](docs/MCP.md)) |
| `mql-lsp` | Language server over stdio ([docs/LSP.md](docs/LSP.md)) |

TUI keys: `Enter` search, `Ctrl+T` cycle mode, `Ctrl+K` cycle kind, `Ctrl+F` focus MongoDB areas,
`Ctrl+R` recipes, `/` focus search, `1`-`9` topic shortcuts, `Esc` clear scope, `q` quit.

## How it works

- **Keyword**: SQLite FTS5 with BM25 ranking and Porter stemming.
- **Semantic**: Ollama `nomic-embed-text` embeddings, cosine similarity in NumPy.
- **Hybrid** (default): reciprocal-rank fusion of both. Falls back to keyword when Ollama is down.
- **Optimizer / linter**: a tolerant mongosh-syntax parser (never raises mid-edit) feeding context-aware rule
  passes; no database connection needed. Confirm any predicted gain with `explain("executionStats")`.

## Configuration

`MDBX_DB` (index path), `MDBX_CORPUS` (corpus dir), `MDBX_OLLAMA_HOST` / `OLLAMA_HOST`,
`MDBX_EMBED_MODEL`, `MDBX_LSP_OPTIMIZE=0` (hide optimizer findings in the editor). See `.env.example`.

AI providers (`mdbx ask`, `mdbx glean`): `mdbx auth set-key <provider>` or `mdbx auth login <provider>`; env vars
`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `GLEAN_API_TOKEN` + `GLEAN_BASE_URL` also work. Settings in
`~/.config/mdbx/config.json`, secrets in the macOS Keychain (service `ai-auth/mdbx`).

## Corpus

`corpus/` holds MongoDB skills (`corpus/skills/`), `llms.txt`-family exports (`corpus/llms/`, including 19
MQL query-optimization fact packs whose every line ends in its MongoDB-docs URL) and recipes (`corpus/recipes/`).
Customer and internal-tooling references are redacted by `scripts/redact_corpus.py` (customer-name rules live
outside the repo in `~/.config/mdbx/redactions.py`); material that cannot be redacted stays local (see `.gitignore`). `scripts/sweep_customers.py` fails if any marker remains in
committed corpus files. `scripts/sync_corpus.sh` rebuilds, redacts, sweeps and reindexes from your own skill tree;
`python scripts/corpus_autoupdate.py install-agent` schedules that refresh and pushes the result to GitHub.
Point `MDBX_CORPUS` at any directory of `.md` / `.txt` files to index your own material.

## Docs

[Optimizer demo](docs/DEMO-mql-optimizer.md) · [Chrome extension](editors/chrome/README.md) · [Recipes](docs/RECIPES.md) · [LSP](docs/LSP.md) · [VS Code](editors/vscode/README.md) · [MCP](docs/MCP.md) · [Architecture](docs/ARCHITECTURE.md) · [Development](docs/DEVELOPMENT.md) ·
[Components](docs/COMPONENTS.md) · [Testing](docs/TESTING.md) · [Installation](docs/INSTALLATION.md) ·
[Security](docs/SECURITY.md) · [Known issues](docs/known-issues.md) · [Onboarding](docs/onboarding.md)

## License

MIT
