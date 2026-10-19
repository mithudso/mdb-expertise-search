// background — the right-click "Optimize selected MQL" menu item.
// The selected text goes to the popup through session storage (memory only, cleared when the browser
// closes); nothing is sent over the network.

const MENU_ID = "mql-optimize-selection";

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({ id: MENU_ID, title: "Optimize selected MQL", contexts: ["selection"] });
  });
});

chrome.contextMenus.onClicked.addListener(async (info) => {
  if (info.menuItemId !== MENU_ID) return;
  await chrome.storage.session.set({ pending: { text: info.selectionText ?? "", ts: Date.now() } });
  try {
    await chrome.action.openPopup(); // Chrome 127+
  } catch {
    await chrome.tabs.create({ url: chrome.runtime.getURL("popup.html#tab") });
  }
});
