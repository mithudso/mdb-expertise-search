// background — right-click menu items, the "mdb" address-bar keyword, and the self-reload check for
// unpacked installs kept current by scripts/chrome_extension_autoupdate.py.
// Optimize and lint use unique session-storage handoffs, cleared when the browser closes.
// Search puts the selection in the destination URL fragment. These launches make no network request.

import { HANDOFF_PREFIX, saveHandoff, truncateText } from "./lib/capture.js";
import { startAutoUpdate } from "./lib/autoupdate.js";

startAutoUpdate();

const MENUS = [
  { id: "mql-optimize-selection", title: "Optimize selected MQL" },
  { id: "mdb-search-selection", title: "Search MongoDB expertise for “%s”" },
  { id: "mql-lint-selection", title: "Lint selected MQL" },
];

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.removeAll(() => {
    for (const m of MENUS) chrome.contextMenus.create({ ...m, contexts: ["selection"] });
  });
});

function openApp(hash) {
  return chrome.tabs.create({ url: chrome.runtime.getURL(`app.html${hash}`) });
}

chrome.contextMenus.onClicked.addListener(async (info) => {
  const text = info.selectionText ?? "";
  let handoff;
  try {
  if (info.menuItemId === "mql-optimize-selection") {
    const id = handoff = await saveHandoff(chrome.storage.session, { text, tab: "optimize" });
    // A tab URL carries the handoff identity; openPopup cannot select a URL per invocation.
    await chrome.tabs.create({ url: chrome.runtime.getURL(`popup.html#tab?handoff=${id}`) });
  } else if (info.menuItemId === "mdb-search-selection") {
    await openApp(`#search?q=${encodeURIComponent(truncateText(text.replace(/\s+/g, " ").trim(), 500))}`);
  } else if (info.menuItemId === "mql-lint-selection") {
    const id = handoff = await saveHandoff(chrome.storage.session, { tab: "lint", text });
    await openApp(`#lint?handoff=${id}`);
  }
  } catch {
    if (handoff) await chrome.storage.session.remove(HANDOFF_PREFIX + handoff).catch(() => {});
    console.warn("MongoDB expertise could not open the selected action.");
  }
});

chrome.omnibox.setDefaultSuggestion({ description: "Search MongoDB expertise for: %s" });
chrome.omnibox.onInputEntered.addListener((text, disposition) => {
  const url = chrome.runtime.getURL(`app.html#search?q=${encodeURIComponent(truncateText(text.trim(), 500))}`);
  const opening = disposition === "currentTab" ? chrome.tabs.update({ url }) : chrome.tabs.create({ url, active: disposition === "newForegroundTab" });
  Promise.resolve(opening).catch(() => console.warn("MongoDB expertise could not open search."));
});
