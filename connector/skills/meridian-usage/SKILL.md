---
name: meridian-usage
description: Answer questions about Meridian assistant usage, cost, and which capabilities a group has. Use when someone asks how much their team used Claude or Gemini, who used it most, or whether web search or code execution is on.
---

# Meridian usage

The signed-in person is fixed when the connector starts. You cannot act as someone else, and there is no tool argument for a user id.

- `usage_summary` and `top_users` take a period: `last_7_days`, `last_30_days`, an ISO week such as `2026-W36`, or a month such as `2026-09`. Relative periods end on 2026-09-28, which is the end of the export, not today.
- Omit `group` unless the person asked about a specific group. It defaults to their own.
- A result with `"error": "permission_denied"` is the whole answer. Tell them the reason. Do not infer, estimate, or call the tool again with a different group to see what happens.
- `set_capability` changes a control for a group. In production only platform admins can do that. If it is denied, say so and point them at IT Platform. Do not suggest a workaround.
