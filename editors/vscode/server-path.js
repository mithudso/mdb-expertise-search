'use strict';
const fs = require('fs');
const path = require('path');

/**
 * Decide which mql-lsp executable to launch.
 * Order: explicit setting, then <workspace>/.venv/bin/mql-lsp (Scripts\mql-lsp.exe on Windows), then PATH.
 */
function resolveServerCommand(configured, workspaceFolders, platform = process.platform, exists = fs.existsSync) {
  if (configured && configured.trim()) return configured.trim();
  const rel = platform === 'win32' ? path.join('.venv', 'Scripts', 'mql-lsp.exe') : path.join('.venv', 'bin', 'mql-lsp');
  for (const folder of workspaceFolders || []) {
    const candidate = path.join(folder, rel);
    if (exists(candidate)) return candidate;
  }
  return 'mql-lsp';
}

module.exports = { resolveServerCommand };
