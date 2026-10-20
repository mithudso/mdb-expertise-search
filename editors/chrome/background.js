// background — right-click menu items, the "mdb" address-bar keyword, and the self-reload check for
// unpacked installs kept current by scripts/chrome_extension_autoupdate.py.
// Selected text reaches the popup / app through session storage (memory only, cleared when the browser
// closes); nothing is sent over the network.

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
  if (info.menuItemId === "mql-optimize-selection") {
    await chrome.storage.session.set({ pending: { text, ts: Date.now() } });
    try {
      await chrome.action.openPopup(); // Chrome 127+
    } catch {
      await chrome.tabs.create({ url: chrome.runtime.getURL("popup.html#tab") });
    }
  } else if (info.menuItemId === "mdb-search-selection") {
    await openApp(`#search?q=${encodeURIComponent(text.replace(/\s+/g, " ").trim().slice(0, 500))}`);
  } else if (info.menuItemId === "mql-lint-selection") {
    await chrome.storage.session.set({ appPending: { tab: "lint", text, ts: Date.now() } });
    await openApp("#lint");
  }
});

chrome.omnibox.setDefaultSuggestion({ description: "Search MongoDB expertise for: %s" });
chrome.omnibox.onInputEntered.addListener((text, disposition) => {
  const url = chrome.runtime.getURL(`app.html#search?q=${encodeURIComponent(text.trim())}`);
  if (disposition === "currentTab") chrome.tabs.update({ url });
  else chrome.tabs.create({ url, active: disposition === "newForegroundTab" });
});
