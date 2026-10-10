import { checkAccess, connectorDisabled, type Denial } from "./auth.js";
import type { UsageClient } from "./client.js";
import { DeniedByApi, ServiceError } from "./client.js";
import type { EnvironmentPolicy, User } from "./policy.js";

const PERIOD = /^(last_7_days|last_30_days|\d{4}-W\d{2}|\d{4}-\d{2})$/;
const CAPABILITIES = new Set(["usage-connector", "web-search", "code-execution"]);
const PERIOD_REASON =
  "period must be last_7_days, last_30_days, an ISO week (2026-W36), or a month (2026-09).";

export interface Actor {
  user: User;
  env: EnvironmentPolicy;
  groups: Set<string>;
}

export interface ToolResult {
  isError: boolean;
  content: { type: "text"; text: string }[];
}

type Scope = "usage:read" | "capabilities:write";

function jsonResult(value: unknown, isError: boolean): ToolResult {
  return {
    isError,
    content: [{ type: "text", text: JSON.stringify(value) }],
  };
}

function invalid(reason: string): ToolResult {
  return jsonResult({ error: "invalid_argument", reason }, true);
}

function denied(denial: Denial): ToolResult {
  return jsonResult(denial, true);
}

function fromService(error: unknown): ToolResult {
  if (error instanceof DeniedByApi) return denied(error.denial);
  if (error instanceof ServiceError && error.body && typeof error.body === "object") {
    const body = error.body as { error?: unknown; reason?: unknown };
    return jsonResult(
      {
        error: typeof body.error === "string" ? body.error : "unavailable",
        reason: typeof body.reason === "string" ? body.reason : "The usage service rejected the request.",
      },
      true,
    );
  }
  return jsonResult(
    { error: "unavailable", reason: "The usage service could not be reached." },
    true,
  );
}

function resolveGroup(actor: Actor, requested: string | undefined): string | ToolResult {
  const group = requested ?? actor.user.group_ids[0];
  if (!group) return invalid("Your account is not in a group.");
  if (!actor.groups.has(group)) return invalid("Unknown group.");
  return group;
}

function requirePeriod(period: string | undefined): string | ToolResult {
  if (!period || !PERIOD.test(period)) return invalid(PERIOD_REASON);
  return period;
}

async function gate(
  actor: Actor,
  scope: Scope,
  group: string,
  client: UsageClient,
): Promise<Denial | null> {
  const access = checkAccess(actor.user, actor.env, scope, group);
  if (access) return access;
  const own = actor.user.group_ids[0];
  if (!own) {
    return { error: "permission_denied", reason: "Your account is not in a group." };
  }
  const rows = await client.capabilityStatus(own);
  const enabled = rows.some(
    (row) => row.group === own && row.capability === "usage-connector" && row.enabled === true,
  );
  if (!enabled) return connectorDisabled();
  return null;
}

/** Check scope, group, and the connector flag, then load. A denial never calls `load`. */
async function perform(
  actor: Actor,
  scope: Scope,
  group: string,
  client: UsageClient,
  load: () => Promise<unknown>,
): Promise<ToolResult> {
  try {
    const refusal = await gate(actor, scope, group, client);
    if (refusal) return denied(refusal);
    return jsonResult(await load(), false);
  } catch (error) {
    return fromService(error);
  }
}

export async function usageSummaryTool(
  actor: Actor,
  args: { group?: string; period?: string },
  client: UsageClient,
): Promise<ToolResult> {
  const period = requirePeriod(args.period);
  if (typeof period !== "string") return period;
  const group = resolveGroup(actor, args.group);
  if (typeof group !== "string") return group;
  return perform(actor, "usage:read", group, client, () => client.usageSummary(group, period));
}

export async function topUsersTool(
  actor: Actor,
  args: { group?: string; period?: string; limit?: number },
  client: UsageClient,
): Promise<ToolResult> {
  const period = requirePeriod(args.period);
  if (typeof period !== "string") return period;
  const limit = args.limit ?? 10;
  if (!Number.isInteger(limit) || limit < 1 || limit > 25) {
    return invalid("limit must be an integer from 1 to 25.");
  }
  const group = resolveGroup(actor, args.group);
  if (typeof group !== "string") return group;
  return perform(actor, "usage:read", group, client, () => client.topUsers(group, period, limit));
}

export async function capabilityStatusTool(
  actor: Actor,
  args: { group?: string },
  client: UsageClient,
): Promise<ToolResult> {
  const group = resolveGroup(actor, args.group);
  if (typeof group !== "string") return group;
  return perform(actor, "usage:read", group, client, () => client.capabilityStatus(group));
}

export async function setCapabilityTool(
  actor: Actor,
  args: { group?: string; capability?: string; enabled?: boolean },
  client: UsageClient,
): Promise<ToolResult> {
  if (!args.group) return invalid("group is required.");
  if (!args.capability || !CAPABILITIES.has(args.capability)) {
    return invalid("capability must be usage-connector, web-search, or code-execution.");
  }
  if (typeof args.enabled !== "boolean") return invalid("enabled must be true or false.");
  const group = resolveGroup(actor, args.group);
  if (typeof group !== "string") return group;
  const capability = args.capability;
  const enabled = args.enabled;
  return perform(actor, "capabilities:write", group, client, () =>
    client.setCapability(group, capability, enabled),
  );
}
