import path from "node:path";
import { fileURLToPath } from "node:url";

/** Repo root when this file lives in connector/src or connector/dist. */
export function repoRoot(): string {
  if (process.env.MERIDIAN_ROOT) return process.env.MERIDIAN_ROOT;
  return path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
}
