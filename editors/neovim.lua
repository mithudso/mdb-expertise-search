-- Neovim 0.11+: put this in your config and fix the path.
vim.filetype.add({ extension = { mql = "mql" } })
vim.lsp.config("mql", { cmd = { vim.fn.expand("~/dev/mdb-expertise-search/.venv/bin/mql-lsp") }, filetypes = { "mql" } })
vim.lsp.enable("mql")
