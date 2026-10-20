# prompts.md — user requests

## 2026-10-17
1. "create a new folder project and write a command line utility to do semantic searching across the
   entire MongoDB expertise corpus ... copy [the skills and LLMS files] into this folder ... semantically
   indexed as well as keyword indexed ... a TUI similar to the LLMS Explorer but specifically tailored for
   the MongoDB environment ... Make a remote GitHub repo that is public. And run the repo bootstrapper on
   the resulting code."

## 2026-10-17 (2)
2. "1. Yes [redact withheld files], also make the repo private for now until we can do a full sweep to make sure all
   customer information is withheld. 2. yes [add an MCP server]. Also as part of this create a mongodb lsp server
   for the mql language."

## 2026-10-17 (3)
3. "Yes do that pass [full customer-info review]. 2. Yes [VS Code extension] also include a recipes section for the
   most common series of actions like sharding a collection and adding private link and upgrading, etc."

## 2026-10-19
4. "pull this repo to here: https://github.com/mithudso/mdb-expertise-search.git then run the repo-bootstrapper skill
   on it, and then incorporate the mongodb query optimizer into it with the new skills and facts that were created
   recently in another session."
5. "Add more examples of what this can do and why someone should use it to the readme, and create a customer facing
   demo doc showcasing this as a skill. Also would a chrome extension be helpful?"
6. "1. Yes, I would like the TSE team to be able to use it with cases. Make it so you can highlight a query and
   then click the extension and it'll run the optimizer on it . 2. yes copy it [~/.config/mdbx redaction config]"
7. "mdbx tui -> zsh: command not found: mdbx" (installed as uv tool; README global-install section)
8. "The lefthand panel is crowded and linewrapped, expand it to fit" (TUI facet sidebar sizes to labels, caps at 45%, ellipsis instead of wrap)
9. "Package the mongodb expertise search, indexes, etc. All the functionality add it to the chrome plugin." (+ asked why the fact packs are marked never publish when based on public docs)

## 2026-10-20
10. "Add the ability to set the api key for claude, codex, glean, and antigravity with oauth options for all of them, as
    well as a fallback local apple intelligence model if those are unavailable and it's a mac that has it. For glean have
    an optional glean cli fallback which would require glean cli be installed along with a helper script in the same way
    as works in ~/dev/mdb-case-assistant and ~/dev/tam-dashboard, also create a library for doing this process since I do
    it often and store it in ~/dev/libraries" (→ `~/dev/libraries/ai-auth`, `mdbx auth|ask|glean`, `scripts/glean_cli_helper.py`)
11. "Also add an auto-updater so the plugin updates when I push new code." (→ `scripts/chrome_extension_autoupdate.py`,
    `editors/chrome/lib/autoupdate.js`, CI `chrome-latest` release)
12. "When attempting to do a symantic search but the symantic indexer is not running and cannot return a result then
    signal that" (→ `search.hybrid(notes=…)`, CLI/TUI/MCP warnings)
