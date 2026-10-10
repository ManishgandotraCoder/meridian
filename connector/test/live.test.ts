import assert from "node:assert/strict";
import { spawn, type ChildProcess } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { after, before, describe, it } from "node:test";

import { HttpUsageClient } from "../src/client.js";
import { loadDirectory, loadEnvironment } from "../src/policy.js";
import { repoRoot } from "../src/paths.js";
import { setCapabilityTool, usageSummaryTool, type Actor } from "../src/tools.js";

const PRIYA = "user_E7691888F28227066DD2FB86";
const CHLOE = "user_533B58E6F66C98ACB833527A";
const PORT = 18765;
const root = repoRoot();

let child: ChildProcess | undefined;
let tmp: string;

function python(): string {
  const venv = path.join(root, ".venv", "bin", "python");
  return existsSync(venv) ? venv : "python3";
}

async function waitForHealth(): Promise<void> {
  const url = `http://127.0.0.1:${PORT}/api/health`;
  for (let attempt = 0; attempt < 50; attempt += 1) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {
      // The process is still binding the port.
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error("usage service did not become healthy");
}

describe("connector against the service", () => {
  before(async () => {
    tmp = await mkdtemp(path.join(os.tmpdir(), "meridian-"));
    child = spawn(python(), ["-m", "meridian"], {
      cwd: root,
      env: {
        ...process.env,
        PYTHONPATH: path.join(root, "service"),
        MERIDIAN_ENV: "prod",
        MERIDIAN_ROOT: root,
        MERIDIAN_DB: path.join(tmp, "meridian.db"),
        HOST: "127.0.0.1",
        PORT: String(PORT),
      },
      stdio: ["ignore", "pipe", "pipe"],
    });
    await waitForHealth();
  });

  after(async () => {
    child?.kill("SIGTERM");
    if (tmp) await rm(tmp, { recursive: true, force: true });
  });

  it("returns Priya's own usage, refuses finance, and refuses her write", async () => {
    const directory = loadDirectory(root);
    const env = loadEnvironment(root, "prod");
    const priya = directory.users.get(PRIYA);
    const chloe = directory.users.get(CHLOE);
    assert.ok(priya && chloe);
    const asPriya: Actor = { user: priya, env, groups: directory.groups };
    const client = new HttpUsageClient(`http://127.0.0.1:${PORT}`, PRIYA);

    const allowed = await usageSummaryTool(asPriya, { period: "last_7_days" }, client);
    assert.equal(allowed.isError, false);
    const summary = JSON.parse(allowed.content[0].text) as {
      group: string;
      platforms: { platform: string; total_tokens: number }[];
      totals: { total_tokens: number; cost_usd: number };
    };
    assert.equal(summary.group, "clinical-operations");
    assert.deepEqual(
      summary.platforms.map((row) => row.platform),
      ["claude", "gemini"],
    );
    assert.ok(summary.totals.total_tokens > 0);
    assert.ok(summary.totals.cost_usd > 0);

    const cross = await usageSummaryTool(asPriya, { period: "last_7_days", group: "finance" }, client);
    assert.equal(cross.isError, true);
    const denial = JSON.parse(cross.content[0].text) as { error: string; reason: string };
    assert.equal(denial.error, "permission_denied");
    assert.match(denial.reason, /own group/);
    assert.equal(cross.content[0].text.includes("total_tokens"), false);

    const write = await setCapabilityTool(
      asPriya,
      { group: "clinical-operations", capability: "web-search", enabled: false },
      client,
    );
    assert.equal(write.isError, true);
    const writeDenial = JSON.parse(write.content[0].text) as { required_scope?: string };
    assert.equal(writeDenial.required_scope, "capabilities:write");

    const asChloe: Actor = { user: chloe, env, groups: directory.groups };
    const admin = new HttpUsageClient(`http://127.0.0.1:${PORT}`, CHLOE);
    const updated = await setCapabilityTool(
      asChloe,
      { group: "hr", capability: "code-execution", enabled: true },
      admin,
    );
    assert.equal(updated.isError, false);
    const row = JSON.parse(updated.content[0].text) as { enabled: boolean; updated_by: string };
    assert.equal(row.enabled, true);
    assert.equal(row.updated_by, CHLOE);
  });
});
