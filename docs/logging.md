# Logging

CLI progress/errors go to stderr and results to stdout. Python logging handlers
remain host-owned. There is no application telemetry server or central dashboard.

| Surface | Current records and behavior |
|---|---|
| mdbx.embed | Model/input counts at DEBUG; safe failure class at WARNING. No raw provider exception, URL credentials or request text. |
| mdbx.index | Counts/progress; failed preparation rolls back. Explicit semantic builds validate before publication. |
| mdbx.search | Corrupt-vector counts and observable semantic fallback categories. Callers can surface notes without duplicate warnings. |
| mdbx.tui | Safe status/fallback categories; worker-owned resources close on their owner thread. |
| mql-lsp | Stdio protocol/server events and content-free optional-enrichment failures. Query text is never evaluated. |
| Maintenance scripts | Safe bounded operation categories; privacy failures use opaque evidence rather than matched lines or private rules. |

Provider libraries and external CLIs have their own logging policies outside this
repository. Review deployment logging separately before handling sensitive input.
No security-response SLA or new retention policy is established by this document.
