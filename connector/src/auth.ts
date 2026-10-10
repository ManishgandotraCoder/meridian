/**
 * Same rules as service/meridian/auth.py. Enforced here, before any usage
 * fetch, so a prompt cannot talk the model into another group's numbers.
 */

import type { EnvironmentPolicy, Scope, User } from "./policy.js";

export interface Denial {
  error: "permission_denied";
  reason: string;
  required_scope?: string;
}

export function checkAccess(
  user: User,
  env: EnvironmentPolicy,
  scope: Scope,
  groupId: string,
): Denial | null {
  if (scope === "usage:read") {
    if (!env.usageReadRoles.includes(user.role)) {
      return {
        error: "permission_denied",
        reason: `${user.role} does not have usage:read in ${env.name}.`,
        required_scope: "usage:read",
      };
    }
    if (!canSeeGroup(user, env, groupId)) {
      return {
        error: "permission_denied",
        reason: "You can view usage for your own group only.",
      };
    }
    return null;
  }
  if (!env.writeRoles.includes(user.role)) {
    return {
      error: "permission_denied",
      reason: `${user.role} does not have capabilities:write in ${env.name}.`,
      required_scope: "capabilities:write",
    };
  }
  if (user.role !== "platform_admin" && !user.group_ids.includes(groupId)) {
    return {
      error: "permission_denied",
      reason: "You can change capabilities for your own group only.",
    };
  }
  return null;
}

export function canSeeGroup(user: User, env: EnvironmentPolicy, groupId: string): boolean {
  if (!env.usageReadRoles.includes(user.role)) return false;
  if (env.groupVisibility === "all") return true;
  if (user.role === "platform_admin") return true;
  return user.group_ids.includes(groupId);
}

export function connectorDisabled(): Denial {
  return {
    error: "permission_denied",
    reason: "The usage-connector capability is disabled for your group.",
  };
}
