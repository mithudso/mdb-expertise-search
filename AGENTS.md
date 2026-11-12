# AGENTS.md

No repo-local agents are defined. Use the global `uber-mongodb-diagnostician` or
`mongodb-claim-validator` agents with `mdbx search --json` output as evidence.

Agent rules: see [CLAUDE.md](CLAUDE.md). Search first with `mdbx search`, then read the cited
`path:line` in `corpus/` before acting.

Repository maintenance uses [docs/TESTING.md](docs/TESTING.md) before running checks.
Ordinary verification uses synthetic state and does not search or re-index live
corpora. Preserve the approved chunk/search serialization unless an explicit
migration is authorized. The maintained documentation index is [docs/wiki/README.md](docs/wiki/README.md).
