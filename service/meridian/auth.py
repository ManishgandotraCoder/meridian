"""Permission checks. Callers get a denial and nothing else when a check fails.

Keep the reason strings aligned with connector/src/auth.ts. Both sides enforce
the same rules; the connector does not trust this module to have done it.
"""

from __future__ import annotations

from typing import List, Optional, Sequence

from meridian.config import Environment
from meridian.directory import User


class PermissionDenied(Exception):
    def __init__(self, reason: str, required_scope: Optional[str] = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.required_scope = required_scope

    def as_dict(self) -> dict:
        body = {"error": "permission_denied", "reason": self.reason}
        if self.required_scope:
            body["required_scope"] = self.required_scope
        return body


def can_see_group(user: User, env: Environment, group_id: str) -> bool:
    if user.role not in env.usage_read_roles:
        return False
    if env.group_visibility == "all":
        return True
    if user.role == "platform_admin":
        return True
    return group_id in user.group_ids


def visible_group_ids(user: User, env: Environment, all_group_ids: Sequence[str]) -> List[str]:
    if user.role not in env.usage_read_roles:
        return []
    if env.group_visibility == "all" or user.role == "platform_admin":
        return list(all_group_ids)
    return [group_id for group_id in user.group_ids if group_id in all_group_ids]


def require_read(user: User, env: Environment, group_id: str) -> None:
    if user.role not in env.usage_read_roles:
        raise PermissionDenied(
            "%s does not have usage:read in %s." % (user.role, env.name),
            "usage:read",
        )
    if not can_see_group(user, env, group_id):
        raise PermissionDenied("You can view usage for your own group only.")


def require_write(user: User, env: Environment, group_id: str) -> None:
    if user.role not in env.write_roles:
        raise PermissionDenied(
            "%s does not have capabilities:write in %s." % (user.role, env.name),
            "capabilities:write",
        )
    # Admins may change any group. Everyone else with the scope may change only their own.
    if user.role != "platform_admin" and group_id not in user.group_ids:
        raise PermissionDenied("You can change capabilities for your own group only.")


def can_write_group(user: User, env: Environment, group_id: str) -> bool:
    try:
        require_write(user, env, group_id)
    except PermissionDenied:
        return False
    return True
