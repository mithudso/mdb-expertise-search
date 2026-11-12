export function appComplete() {
  if (document.body.dataset.ready !== "true") return false;
  const [raw, query] = location.hash.slice(1).split("?");
  const supported = ["search", "doc", "recipes", "optimize", "lint", "operators", "about"];
  const route = supported.includes(raw) ? raw : "search";
  const panel = document.getElementById(`tab-${route}`);
  if (!panel || panel.hidden) return false;
  if (route === "search") {
    if (!(new URLSearchParams(query).get("q") || "").trim()) return true;
    const status = document.getElementById("search-status");
    return /results? in \d+ ms/.test(status.textContent) || status.classList.contains("error");
  }
  if (route === "about") return Boolean(document.getElementById("stats").textContent);
  if (route === "doc") return Boolean(document.getElementById("doc").textContent);
  if (route === "recipes") return document.getElementById("recipes").dataset.ready === "true";
  return true;
}
