// autoupdate — reload the (unpacked) extension when a newer build lands in its folder.
//
// scripts/chrome_extension_autoupdate.py replaces the files of an unpacked install after every push to
// GitHub and writes data/build.json ({version, commit, built_at}). Chrome does not notice files changing
// under an unpacked extension, so the service worker re-reads its own build.json on an alarm and calls
// chrome.runtime.reload() when the build id differs from the one it started with. No network access: the
// fetch is to chrome-extension://<id>/data/build.json, i.e. the local folder.

export const BUILD_URL = "data/build.json";
export const ALARM = "mdbx-autoupdate";
export const INTERVAL_MINUTES = 5;
export const SESSION_KEY = "autoupdateBuild";

/** Stable identity of a build: the commit when known, else version + build time. */
export function buildId(info) {
  if (!info || typeof info !== "object") return "";
  const commit = String(info.commit || "").trim();
  if (commit && commit !== "unknown") return commit;
  const version = String(info.version || "").trim();
  const built = String(info.built_at || "").trim();
  return version || built ? `${version}@${built}` : "";
}

/** True when a newer build id is present and differs from the one this worker started with. */
export function shouldReload(startedWith, current) {
  return Boolean(startedWith) && Boolean(current) && startedWith !== current;
}

export async function readBuild(fetchImpl, runtime) {
  try {
    const res = await fetchImpl(runtime.getURL(BUILD_URL), { cache: "no-store" });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null; // missing metadata, invalid JSON, or a transient local read error
  }
}

/**
 * Wire the alarm. `api` is the chrome namespace (injectable for tests); returns the handlers so tests
 * can drive them. The stored baseline and existing alarm survive worker suspension.
 */
export function startAutoUpdate(api = globalThis.chrome, fetchImpl = globalThis.fetch) {
  const { alarms, runtime, storage } = api;
  if (!alarms || !runtime || !storage?.session) return null;

  // Serialize initialization and alarm checks so neither can replace an outstanding baseline.
  let queue = Promise.resolve();
  let reloading = false;
  const serial = fn => {
    const next = queue.then(fn);
    queue = next.catch(() => {});
    return next;
  };
  async function baseline() {
    const stored = (await storage.session.get(SESSION_KEY))?.[SESSION_KEY];
    if (stored) return stored;
    const id = buildId(await readBuild(fetchImpl, runtime));
    if (id) await storage.session.set({ [SESSION_KEY]: id });
    return id;
  }
  const remember = () => serial(baseline);
  const check = () => serial(async () => {
    if (reloading) return false;
    const started = await baseline();
    const current = buildId(await readBuild(fetchImpl, runtime));
    if (shouldReload(started, current)) {
      await storage.session.remove(SESSION_KEY);
      runtime.reload();
      reloading = true;
      return true;
    }
    return false;
  });

  // Register synchronously; every detached API boundary contains failures and permits a later retry.
  alarms.onAlarm.addListener(alarm => alarm?.name === ALARM ? check().catch(() => false) : undefined);
  const ready = Promise.all([
    Promise.resolve().then(async () => {
      if (!(await alarms.get(ALARM))) await alarms.create(ALARM, { periodInMinutes: INTERVAL_MINUTES, delayInMinutes: 1 });
    }).catch(() => {}),
    remember().catch(() => ""),
  ]);
  return { remember, check, ready };
}
