# Security boundaries

MQL parsing and optimization are static. Query text is not evaluated. MCP and LSP
use stdio; they do not listen on a network port. File reads reject child symlinks
and remain confined to the selected corpus root. SQL values use bound parameters.

Chrome runs packaged scripts under MV3 CSP. It reads selected page text after an
explicit action and renders page/corpus text as text. Packaged-file fetches read
extension resources; optional semantic search sends query text to a permitted local
Ollama endpoint. Active-tab and storage permissions are described in its manifest.
Markdown copied to the clipboard can contain selected user text; review it before
sharing. Git tracking alone does not prove a file is safe to distribute.

Python semantic search sends query text to Ollama, or uses an already installed
ONNX model in process. Indexing sends document chunks to the configured embedder.
The optional AI adapter sends a question and selected passages to a configured
provider; the optional auth library owns credentials and its storage. This project
must not assume that every provider is local or that no credentials exist.

Import/sync/privacy tooling processes local files. Private rules and denylist values
stay outside Git. Automated checks use synthetic fixtures, scratch configuration,
mock embedding runtimes, a filtered semantic Git hook and process-tree egress
isolation. No real model, provider, index or customer corpus is part of routine CI.

The existing vulnerability-reporting route is [.github/SECURITY.md](../.github/SECURITY.md).
No response SLA or new legal commitment is established here. Maintainers must decide
redistribution rights and private-history remediation before any new corpus release.
