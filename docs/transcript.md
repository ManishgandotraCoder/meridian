# Connector transcript

Priya Nair (`user_E7691888F28227066DD2FB86`), team lead of Clinical Operations, in the `prod` environment. The usage service was already running on `http://127.0.0.1:8000`. The connector loaded her role and group from the directory, checked the prod grants itself, and only then called the service. Reproduce the tool results with the service up and `npm run transcript` in `connector/`.

To ask the same questions in Claude Code, start the service with `MERIDIAN_ENV=prod` and, from the repository root, run `claude --plugin-dir connector`. When the plugin asks, set the directory user to Priya's id, the environment to `prod`, and the service URL to `http://127.0.0.1:8000`. Do not start Claude inside `connector/`: `--plugin-dir connector` would miss the plugin, and `.mcp.json` would be read as a project server that does not expand `${CLAUDE_PLUGIN_ROOT}`. Use `staging` or `dev` only when the service was started with that same name.

To ask them in Gemini CLI, from the repository root run `gemini extensions link connector`, then `gemini extensions config meridian-usage`, and enter the same three values. Start `gemini` from the repository root as well. The extension sets `MERIDIAN_ROOT` to that workspace. A blank environment is `prod`, and a blank service URL is `http://127.0.0.1:8000`.

Gemini CLI 0.63.0 answered two of these in a session started from the repository root, with the extension linked and a Gemini API key. Personal Google sign-in is rejected for individual accounts. The finance refusal below is from the same server Claude loads (`node connector/dist/index.js` over stdio, Priya, `prod`, the service on port 8000). A headless `claude -p` still stops before a tool call with `401 OAuth access token is invalid`.

## Gemini CLI

### Denied write

Asked: "Turn off web search for clinical operations."

The host activated the `meridian-usage` skill and answered:

> Permission denied: team_lead does not have capabilities:write in prod. Only platform admins can change group capabilities. Please contact IT Platform to request this change.

Nothing was written.

### Allowed read

Asked: "How much did my team use in September 2026?"

`usage_summary` returned this, and the host repeated it:

```json
{
  "group": "clinical-operations",
  "period": { "start": "2026-09-01", "end_exclusive": "2026-10-01" },
  "platforms": [
    {
      "platform": "claude",
      "requests": 1087,
      "input_tokens": 4411485,
      "output_tokens": 661995,
      "total_tokens": 5073480,
      "cost_usd": 67.95067689
    },
    {
      "platform": "gemini",
      "requests": null,
      "input_tokens": 5001153,
      "output_tokens": 1525880,
      "total_tokens": 6527033,
      "cost_usd": 9.717985
    }
  ],
  "totals": { "total_tokens": 11600513, "cost_usd": 77.66866189 }
}
```

`isError` was false. Gemini requests are null because the billing export has no request count.

## Claude connector

Same actor, same server the plugin starts. September for her own group matched the Gemini tool result above. The other two calls:

### Denied cross-group read

`usage_summary` with `group=finance` and `period=2026-09`.

```json
{
  "error": "permission_denied",
  "reason": "You can view usage for your own group only."
}
```

`isError` was true. No token counts and no cost.

### Denied write

`set_capability` with `group=clinical-operations`, `capability=web-search`, `enabled=false`.

```json
{
  "error": "permission_denied",
  "reason": "team_lead does not have capabilities:write in prod.",
  "required_scope": "capabilities:write"
}
```

`isError` was true.

## Scripted tool results

`npm run transcript` calls the tools directly, without a host. It uses `last_7_days` rather than the calendar month.

## Allowed read

`usage_summary` with `period=last_7_days` and no group. The group defaults to hers.

```json
{
  "group": "clinical-operations",
  "period": { "start": "2026-09-21", "end_exclusive": "2026-09-28" },
  "platforms": [
    {
      "platform": "claude",
      "requests": 273,
      "input_tokens": 777862,
      "output_tokens": 146039,
      "total_tokens": 923901,
      "cost_usd": 13.13817588
    },
    {
      "platform": "gemini",
      "requests": null,
      "input_tokens": 1308144,
      "output_tokens": 332854,
      "total_tokens": 1640998,
      "cost_usd": 1.224578
    }
  ],
  "totals": { "total_tokens": 2564899, "cost_usd": 14.36275388 }
}
```

`isError` was false. Last 7 days is 21–27 September 2026, because relative periods end at the export window (28 September, exclusive).

## Denied cross-group read

`usage_summary` with `group=finance` and `period=last_7_days`.

```json
{
  "error": "permission_denied",
  "reason": "You can view usage for your own group only."
}
```

`isError` was true. The result has no token counts and no cost. The connector returned this before calling the usage endpoint. She does have `usage:read`, so there is no `required_scope`; the refusal is the group boundary.

## Denied write

`set_capability` with `group=clinical-operations`, `capability=web-search`, `enabled=false`. Her own group, her own control.

```json
{
  "error": "permission_denied",
  "reason": "team_lead does not have capabilities:write in prod.",
  "required_scope": "capabilities:write"
}
```

`isError` was true. Nothing was written. Web search for Clinical Operations stayed enabled.
