import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

export async function loadCapture(extDir) {
  return import(pathToFileURL(resolve(extDir, "lib/capture.js")).href);
}

export async function hasPackagedData(extDir, checkResponse) {
  if (!existsSync(resolve(extDir, "data/meta.json"))) return false;
  if (!(await checkResponse())) throw new Error("Packaged data/meta.json could not be loaded");
  return true;
}
