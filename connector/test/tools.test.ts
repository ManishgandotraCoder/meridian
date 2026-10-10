import assert from "node:assert/strict";
import { describe, it } from "node:test";

import type { UsageClient } from "../src/client.js";
import { loadDirectory, loadEnvironment } from "../src/policy.js";
import { repoRoot } from "../src/paths.js";
import {
  capabilityStatusTool,
  setCapabilityTool,
  topUsersTool,
  usageSummaryTool,
  type Actor,
  type ToolResult,
} from "../src/tools.js";

const PRIYA = "user_E7691888F28227066DD2FB86";
const DANIEL = "user_699C48763F6FA2958D2CDB5D";
const CHLOE = "user_533B58E6F66C98ACB833527A";
const SOFIA = "user_0CF0516C4D9067BED584DB3F";

const directory = loadDirectory(repoRoot());
const prod = loadEnvironment(repoRoot(), "prod");
const dev = loadEnvironment(repoRoot(), "dev");

function actor(userId: string, env = prod): Actor {
  const user = directory.users.get(userId);
  assert.ok(user);
  return { user, env, groups: directory.groups };
}

function body(result: ToolResult): Record<string, unknown> {
  return JSON.parse(result.content[0].text) as Record<string, unknown>;
}

function throwingClient(): UsageClient {
  const boom = async () => {
    throw new Error("usage was fetched");
  };
  return {
    usageSummary: boom,
    topUsers: boom,
    capabilityStatus: boom,
    setCapability: boom,
  };
}

function recordingClient(connectorEnabled = true): UsageClient & { calls: string[] } {
  const calls: string[] = [];
  return {
    calls,
    async capabilityStatus(group) {
      calls.push(`caps:${group}`);
      return [
        { group, capability: "usage-connector", enabled: connectorEnabled, updated_at: null, updated_by: null },
        { group, capability: "web-search", enabled: true, updated_at: null, updated_by: null },
        { group, capability: "code-execution", enabled: false, updated_at: null, updated_by: null },
      ];
    },
    async usageSummary(group, period) {
      calls.push(`summary:${group}:${period}`);
      return { group, period, totals: { total_tokens: 10, cost_usd: 1 } };
    },
    async topUsers(group, period, limit) {
      calls.push(`top:${group}:${period}:${limit}`);
      return [];
    },
    async setCapability(group, capability, enabled) {
      calls.push(`set:${group}:${capability}:${enabled}`);
      return { group, capability, enabled, updated_at: "2026-10-08T00:00:00Z", updated_by: CHLOE };
    },
  };
}

describe("prod access", () => {
  it("gives a team lead their own group and no one else's", async () => {
    const client = recordingClient();
    const allowed = await usageSummaryTool(actor(PRIYA), { period: "last_7_days" }, client);
    assert.equal(allowed.isError, false);
    assert.equal(body(allowed).group, "clinical-operations");
    assert.deepEqual(client.calls, ["caps:clinical-operations", "summary:clinical-operations:last_7_days"]);

    const denied = await usageSummaryTool(
      actor(PRIYA),
      { period: "last_30_days", group: "finance" },
      throwingClient(),
    );
    assert.equal(denied.isError, true);
    const payload = body(denied);
    assert.equal(payload.error, "permission_denied");
    assert.match(String(payload.reason), /own group/);
    assert.equal(payload.required_scope, undefined);
    assert.equal(JSON.stringify(payload).includes("total_tokens"), false);
    assert.equal(JSON.stringify(payload).includes("cost"), false);
  });

  it("denies a member before any fetch", async () => {
    const result = await topUsersTool(actor(DANIEL), { period: "2026-W36" }, throwingClient());
    assert.equal(result.isError, true);
    assert.equal(body(result).required_scope, "usage:read");
  });

  it("denies a team lead write, and allows an admin write", async () => {
    const refused = await setCapabilityTool(
      actor(PRIYA),
      { group: "clinical-operations", capability: "web-search", enabled: false },
      throwingClient(),
    );
    assert.equal(refused.isError, true);
    assert.equal(body(refused).required_scope, "capabilities:write");

    const client = recordingClient();
    const updated = await setCapabilityTool(
      actor(CHLOE),
      { group: "hr", capability: "code-execution", enabled: true },
      client,
    );
    assert.equal(updated.isError, false);
    assert.deepEqual(client.calls, ["caps:it-platform", "set:hr:code-execution:true"]);
  });

  it("denies every tool when usage-connector is off for the caller's group", async () => {
    const client = recordingClient(false);
    const result = await capabilityStatusTool(actor(SOFIA), { period: "ignored" } as { group?: string }, client);
    assert.equal(result.isError, true);
    assert.match(String(body(result).reason), /usage-connector/);
    assert.deepEqual(client.calls, ["caps:finance"]);
    assert.equal(JSON.stringify(body(result)).includes("web-search"), false);
  });
});

describe("dev access", () => {
  it("lets a member read another group", async () => {
    const client = recordingClient();
    const result = await usageSummaryTool(
      actor(DANIEL, dev),
      { group: "medical-writing", period: "2026-09" },
      client,
    );
    assert.equal(result.isError, false);
    assert.ok(client.calls.includes("summary:medical-writing:2026-09"));
  });
});

describe("arguments", () => {
  it("rejects a bad period and an out-of-range limit without fetching", async () => {
    const period = await usageSummaryTool(actor(PRIYA), { period: "yesterday" }, throwingClient());
    assert.equal(body(period).error, "invalid_argument");
    const limit = await topUsersTool(actor(PRIYA), { period: "last_7_days", limit: 50 }, throwingClient());
    assert.equal(body(limit).error, "invalid_argument");
  });
});
