import { readFileSync } from "node:fs";
import path from "node:path";
import { parse } from "yaml";

export type Role = "member" | "team_lead" | "platform_admin";
export type Scope = "usage:read" | "capabilities:write";

export interface User {
  user_id: string;
  email: string;
  name: string;
  role: Role;
  group_ids: string[];
}

export interface EnvironmentPolicy {
  name: string;
  usageReadRoles: Role[];
  groupVisibility: "all" | "own_group";
  writeRoles: Role[];
}

export interface DirectorySnapshot {
  users: Map<string, User>;
  groups: Set<string>;
}

export function loadDirectory(root: string): DirectorySnapshot {
  const file = path.join(root, "starter-kit", "data", "directory", "users.json");
  const groupsFile = path.join(root, "starter-kit", "data", "directory", "groups.json");
  const usersDoc = JSON.parse(readFileSync(file, "utf8")) as { users: User[] };
  const groupsDoc = JSON.parse(readFileSync(groupsFile, "utf8")) as {
    groups: { group_id: string }[];
  };
  const users = new Map<string, User>();
  for (const user of usersDoc.users) users.set(user.user_id, user);
  const groups = new Set(groupsDoc.groups.map((group) => group.group_id));
  return { users, groups };
}

export function loadEnvironment(root: string, name: string): EnvironmentPolicy {
  const file = path.join(root, "starter-kit", "environments", `${name}.yaml`);
  const raw = parse(readFileSync(file, "utf8")) as {
    environment: string;
    scopes: {
      "usage:read": { roles: Role[]; group_visibility: "all" | "own_group" };
      "capabilities:write": { roles: Role[] };
    };
  };
  return {
    name: raw.environment,
    usageReadRoles: raw.scopes["usage:read"].roles,
    groupVisibility: raw.scopes["usage:read"].group_visibility,
    writeRoles: raw.scopes["capabilities:write"].roles,
  };
}
