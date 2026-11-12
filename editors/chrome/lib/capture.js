// capture — get the text the user highlighted, from wherever they highlighted it.

export const MAX_INPUT = 200_000; // characters; larger selections are truncated before analysis
export const PENDING_TTL_MS = 60_000; // a context-menu handoff older than this is ignored

/**
 * Runs INSIDE the page (chrome.scripting.executeScript). Must be self-contained: no imports, no closure.
 * Returns { text, focused } for the textarea / text input or document selection.
 */
export function grabSelection() {
  const el = document.activeElement;
  const leaf = !/^(IFRAME|FRAME)$/.test(el?.tagName || "");
  let focused = document.hasFocus() && leaf;
  try {
    // The popup may own browser focus. Same-origin activeElement ancestry still identifies the leaf.
    let frame = window, active = true;
    while (frame !== frame.top) {
      if (frame.parent.document.activeElement !== frame.frameElement) { active = false; break; }
      frame = frame.parent;
    }
    focused = active && leaf;
  } catch { /* Cross-origin ancestry keeps the document.hasFocus fallback. */ }
  if (el && (el.tagName === "TEXTAREA" || (el.tagName === "INPUT" && /^(text|search|url|)$/i.test(el.type || "")))) {
    const s = String(el.value || "").slice(el.selectionStart ?? 0, el.selectionEnd ?? 0);
    if (s.trim()) return { text: s, focused };
  }
  const sel = typeof window.getSelection === "function" ? window.getSelection() : null;
  return { text: sel ? String(sel) : "", focused };
}

/** Prefer the focused frame; strings remain accepted for older captured results. */
export function pickSelection(frameResults) {
  const choices = (frameResults || []).map(r => typeof r?.result === "string" ? { text: r.result, focused: false } : r?.result)
    .filter(r => r && typeof r.text === "string");
  const focused = choices.filter(r => r.focused);
  const pool = focused.length ? focused : choices.filter(r => r.text.trim());
  return pool.reduce((best, r) => r.text.length > best.length ? r.text : best, "");
}

/** Clamp to MAX_INPUT. Returns { text, truncated }. */
export function clamp(text) {
  const t = String(text ?? "");
  return { text: truncateText(t, MAX_INPUT), truncated: t.length > MAX_INPUT };
}

/** Bound UTF-16 length without splitting code points; replace isolated surrogates for URL encoding. */
export function truncateText(text, limit) {
  let out = "";
  for (const c of String(text ?? "")) {
    if (out.length + c.length > limit) break;
    out += c.length === 1 && /[\uD800-\uDFFF]/.test(c) ? "\uFFFD" : c;
  }
  return out;
}

/** A context-menu handoff is usable when present, non-blank and recent. */
export function freshPending(pending, now = Date.now()) {
  return Boolean(pending && typeof pending.text === "string" && pending.text.trim() &&
    Number.isFinite(pending.ts) && now - pending.ts >= 0 && now - pending.ts < PENDING_TTL_MS);
}

export const HANDOFF_PREFIX = "selectionHandoff:";

/** Each destination owns one key. Remove only expired abandoned handoffs. */
export async function saveHandoff(session, payload, now = Date.now(), id = crypto.randomUUID()) {
  const entries = await session.get(null);
  const stale = Object.keys(entries).filter(k => k.startsWith(HANDOFF_PREFIX) && !freshPending(entries[k], now));
  if (stale.length) await session.remove(stale);
  const bounded = clamp(payload.text);
  await session.set({ [HANDOFF_PREFIX + id]: { ...payload, ...bounded, truncated: Boolean(payload.truncated || bounded.truncated), ts: now } });
  return id;
}

export async function consumeHandoff(session, id, now = Date.now(), locks = globalThis.navigator?.locks) {
  if (!id || !/^[a-zA-Z0-9-]{1,100}$/.test(id)) return null;
  const key = HANDOFF_PREFIX + id;
  if (!locks?.request) throw new Error("Handoff consumption requires an origin lock");
  return locks.request(key, async () => {
    const pending = (await session.get(key))[key];
    if (pending) await session.remove(key);
    return freshPending(pending, now) ? pending : null;
  });
}
