// capture — get the text the user highlighted, from wherever they highlighted it.

export const MAX_INPUT = 200_000; // characters; larger selections are truncated before analysis
export const PENDING_TTL_MS = 60_000; // a context-menu handoff older than this is ignored

/**
 * Runs INSIDE the page (chrome.scripting.executeScript). Must be self-contained: no imports, no closure.
 * Returns the selected text of the focused textarea / text input, else the document selection.
 */
export function grabSelection() {
  const el = document.activeElement;
  if (el && (el.tagName === "TEXTAREA" || (el.tagName === "INPUT" && /^(text|search|url|)$/i.test(el.type || "")))) {
    const s = String(el.value || "").slice(el.selectionStart ?? 0, el.selectionEnd ?? 0);
    if (s.trim()) return s;
  }
  const sel = typeof window.getSelection === "function" ? window.getSelection() : null;
  return sel ? String(sel) : "";
}

/** Pick the selection to analyse from per-frame results: the longest non-blank one. */
export function pickSelection(frameResults) {
  const texts = (frameResults || []).map((r) => (r && typeof r.result === "string" ? r.result : ""))
    .filter((t) => t.trim());
  if (!texts.length) return "";
  return texts.reduce((a, b) => (b.length > a.length ? b : a));
}

/** Clamp to MAX_INPUT. Returns { text, truncated }. */
export function clamp(text) {
  const t = String(text ?? "");
  return t.length > MAX_INPUT ? { text: t.slice(0, MAX_INPUT), truncated: true } : { text: t, truncated: false };
}

/** A context-menu handoff is usable when present, non-blank and recent. */
export function freshPending(pending, now = Date.now()) {
  return Boolean(pending && typeof pending.text === "string" && pending.text.trim() &&
    typeof pending.ts === "number" && now - pending.ts < PENDING_TTL_MS);
}
