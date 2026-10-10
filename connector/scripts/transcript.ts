import { HttpUsageClient } from "../src/client.ts";
import { loadDirectory, loadEnvironment } from "../src/policy.ts";
import { repoRoot } from "../src/paths.ts";
import { setCapabilityTool, usageSummaryTool } from "../src/tools.ts";

const root = repoRoot();
const directory = loadDirectory(root);
const env = loadEnvironment(root, "prod");
const priya = directory.users.get("user_E7691888F28227066DD2FB86");
if (!priya) throw new Error("Priya is missing from the directory");
const actor = { user: priya, env, groups: directory.groups };
const client = new HttpUsageClient(process.env.MERIDIAN_API_URL ?? "http://127.0.0.1:8000", priya.user_id);

const allowed = await usageSummaryTool(actor, { period: "last_7_days" }, client);
const denied = await usageSummaryTool(actor, { period: "last_7_days", group: "finance" }, client);
const write = await setCapabilityTool(
  actor,
  { group: "clinical-operations", capability: "web-search", enabled: false },
  client,
);

for (const [name, result] of [
  ["allowed read", allowed],
  ["cross-group read", denied],
  ["write", write],
] as const) {
  console.log(`\n## ${name}\nisError: ${result.isError}\n${result.content[0].text}\n`);
}
