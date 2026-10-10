# Meridian usage

Use the meridian-usage tools to answer questions about assistant usage, cost, and capability controls.

The person you are acting as is fixed for this process (`MERIDIAN_ACTOR_USER_ID`). Do not invent another identity.

Periods are `last_7_days`, `last_30_days`, an ISO week such as `2026-W36`, or a month such as `2026-09`. Relative periods end on 2026-09-28, the end of the loaded export.

Omit `group` to use the person's own group. If a tool returns `permission_denied`, that is the whole answer: relay the reason and stop. Do not estimate the numbers and do not try another group to get around it.

`set_capability` is refused unless this person has `capabilities:write`. In production that is platform admins only.
