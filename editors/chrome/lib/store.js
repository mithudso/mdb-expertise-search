// store — load the packaged search index (data/*, written by `mdbx export-web`).
import { SearchIndex } from "./textsearch.js";

/**
 * Load the index through `read(name, kind)` where kind is "json" or "bytes" and a missing optional file
 * resolves to null. Returns a SearchIndex, or null when the extension was packaged without data.
 */
export async function loadIndex(read) {
  const meta = await read("meta.json", "json");
  if (!meta) return null;
  const [chunks, vocab, ids, wts, doclen, vectors] = await Promise.all([
    read("chunks.json", "json"), read("terms.json", "json"), read("postings.bin", "bytes"),
    read("weights.bin", "bytes"), read("doclen.bin", "bytes"), meta.vectors ? read("vectors.bin", "bytes") : null,
  ]);
  // slice() copies into a fresh, aligned ArrayBuffer (typed arrays need offsets aligned to their element size)
  const own = (u8) => u8.slice().buffer;
  return new SearchIndex({
    meta, chunks, vocab,
    ids: new Uint32Array(own(ids)),
    wts: new Uint16Array(own(wts)),
    doclen: new Uint32Array(own(doclen)),
    vectors: vectors ? new Int8Array(own(vectors)) : null,
  });
}

/** Reader for extension pages: fetches files packaged under data/. */
export function extensionReader(base = "data/") {
  return async (name, kind) => {
    let res;
    try {
      res = await fetch(chrome.runtime.getURL(base + name));
    } catch {
      return null;
    }
    if (!res.ok) return null;
    return kind === "json" ? res.json() : new Uint8Array(await res.arrayBuffer());
  };
}

let cached = null;

/** The extension's index, loaded once per page. */
export function getIndex() {
  if (!cached) cached = loadIndex(extensionReader());
  return cached;
}
