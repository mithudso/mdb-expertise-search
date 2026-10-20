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
    return null; // packaged without data/ (--no-data) or a transient read error
  }
}

/**
 * Wire the alarm. `api` is the chrome namespace (injectable for tests); returns the handlers so tests
 * can drive them. Safe to call on every worker start: alarms.create replaces an existing alarm.
 */
export function startAutoUpdate(api = globalThis.chrome, fetchImpl = globalThis.fetch) {
  const { alarms, runtime, storage } = api;
  if (!alarms || !runtime || !storage?.session) return null;

  async function remember() {
    const info = await readBuild(fetchImpl, runtime);
    const id = buildId(info);
    if (id) await storage.session.set({ [SESSION_KEY]: id });
    return id;
  }

  async function check() {
    const stored = (await storage.session.get(SESSION_KEY))?.[SESSION_KEY];
    const started = stored || (await remember());
    const current = buildId(await readBuild(fetchImpl, runtime));
    if (shouldReload(started, current)) {
      await storage.session.remove(SESSION_KEY);
      runtime.reload();
      return true;
    }
    return false;
  }

  alarms.create(ALARM, { periodInMinutes: INTERVAL_MINUTES, delayInMinutes: 1 });
  alarms.onAlarm.addListener((alarm) => (alarm?.name === ALARM ? check() : undefined));
  remember();
  return { remember, check };
}
