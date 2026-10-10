import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import type { CallToolResult } from "@modelcontextprotocol/sdk/types.js";
import { z } from "zod";

import type { UsageClient } from "./client.js";
import {
  capabilityStatusTool,
  setCapabilityTool,
  topUsersTool,
  usageSummaryTool,
  type Actor,
  type ToolResult,
} from "./tools.js";

const denialNote =
  "If the result is a permission denial, say so and stop. Do not retry as another person or guess the numbers.";

function callResult(result: ToolResult): CallToolResult {
  return { content: result.content, isError: result.isError };
}

export function buildServer(actor: Actor, client: UsageClient, groupIds: [string, ...string[]]): McpServer {
  const period = z
    .string()
    .regex(/^(last_7_days|last_30_days|\d{4}-W\d{2}|\d{4}-\d{2})$/)
    .describe("last_7_days, last_30_days, an ISO week such as 2026-W36, or a month such as 2026-09");
  const groupId = z.enum(groupIds);

  const server = new McpServer({ name: "meridian-usage", version: "1.0.0" });

  server.registerTool(
    "usage_summary",
    {
      title: "Usage summary",
      description: `Tokens and USD cost for one group, split by Claude and Gemini, plus a total. Omit group to use the signed-in user's own group. Relative periods end on 2026-09-28, the last day after the export. ${denialNote}`,
      inputSchema: {
        group: groupId.optional().describe("Directory group id. Defaults to the caller's own group."),
        period,
      },
      annotations: { readOnlyHint: true },
    },
    async (args) => callResult(await usageSummaryTool(actor, args, client)),
  );

  server.registerTool(
    "top_users",
    {
      title: "Top users",
      description: `People in one group ranked by total tokens for the period. limit is 1 to 25 and defaults to 10. ${denialNote}`,
      inputSchema: {
        group: groupId.optional(),
        period,
        limit: z.number().int().min(1).max(25).optional(),
      },
      annotations: { readOnlyHint: true },
    },
    async (args) => callResult(await topUsersTool(actor, args, client)),
  );

  server.registerTool(
    "capability_status",
    {
      title: "Capability status",
      description: `Whether usage-connector, web-search, and code-execution are enabled for a group. ${denialNote}`,
      inputSchema: { group: groupId.optional() },
      annotations: { readOnlyHint: true },
    },
    async (args) => callResult(await capabilityStatusTool(actor, args, client)),
  );

  server.registerTool(
    "set_capability",
    {
      title: "Set capability",
      description: `Enable or disable a capability for a group. Requires capabilities:write, which in production is limited to platform admins. The usage connector must also be enabled for the caller's own group. ${denialNote}`,
      inputSchema: {
        group: groupId,
        capability: z.enum(["usage-connector", "web-search", "code-execution"]),
        enabled: z.boolean(),
      },
      annotations: { readOnlyHint: false, destructiveHint: false },
    },
    async (args) => callResult(await setCapabilityTool(actor, args, client)),
  );

  return server;
}
