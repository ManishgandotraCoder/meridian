#!/usr/bin/env node
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

import { HttpUsageClient } from "./client.js";
import { loadDirectory, loadEnvironment } from "./policy.js";
import { repoRoot } from "./paths.js";
import { buildServer } from "./server.js";
import type { Actor } from "./tools.js";

function envValue(name: string): string {
  return process.env[name]?.trim() ?? "";
}

const userId = envValue("MERIDIAN_ACTOR_USER_ID");
if (!userId) {
  console.error("MERIDIAN_ACTOR_USER_ID is required. Set the directory user in the plugin configuration.");
  process.exit(1);
}
const environmentName = envValue("MERIDIAN_ENV") || "prod";
const apiUrl = envValue("MERIDIAN_API_URL") || "http://127.0.0.1:8000";

const root = repoRoot();
const directory = loadDirectory(root);
const user = directory.users.get(userId);
if (!user) {
  console.error(`Unknown directory user ${userId}.`);
  process.exit(1);
}

const actor: Actor = {
  user,
  env: loadEnvironment(root, environmentName),
  groups: directory.groups,
};
const client = new HttpUsageClient(apiUrl, user.user_id);
const groupIds = [...directory.groups] as [string, ...string[]];

await buildServer(actor, client, groupIds).connect(new StdioServerTransport());
