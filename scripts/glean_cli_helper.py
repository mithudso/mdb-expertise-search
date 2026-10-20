#!/usr/bin/env python3
"""Glean CLI helper for mdbx — the fallback when no Glean API token or OAuth session is configured.

Same contract as the Glean native-messaging hosts in mdb-case-assistant / tam-dashboard: find the
``glean`` binary (even on a minimal PATH), verify it, probe ``glean auth status``, optionally run
``glean auth login`` (browser), retry transient network errors, and print exactly one JSON object.

    python scripts/glean_cli_helper.py check
    python scripts/glean_cli_helper.py login
    python scripts/glean_cli_helper.py search "Atlas Private Link" --page-size 5 [--datasource confluence]
    python scripts/glean_cli_helper.py api users/me
    python scripts/glean_cli_helper.py chat "Summarise ..."

Exit codes: 0 ok · 1 failed · 2 glean CLI not installed · 3 not authenticated (run login).
Requires the Glean CLI (``brew install gleanwork/tap/glean-cli``) and the ai-auth library, which owns the
implementation (``ai_auth/glean_helper.py``): ``pip install 'mdb-expertise-search[ai]'``.
"""
from __future__ import annotations

import json
import sys

try:
    from ai_auth.glean_helper import main
except ImportError:  # pragma: no cover
    print(json.dumps({"ok": False, "code": 2, "error": "ai-auth library not installed",
                      "remediation": "pip install 'mdb-expertise-search[ai]' or pip install -e ~/dev/libraries/ai-auth"}))
    sys.exit(2)

if __name__ == "__main__":
    sys.exit(main())
