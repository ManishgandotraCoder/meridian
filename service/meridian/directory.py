"""Identity directory. Stands in for the IdP SCIM export."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class User:
    user_id: str
    email: str
    name: str
    role: str
    group_ids: Tuple[str, ...]

    @property
    def own_group(self) -> str:
        if not self.group_ids:
            raise ValueError("User %s is not in a group" % self.user_id)
        return self.group_ids[0]


@dataclass(frozen=True)
class Group:
    group_id: str
    name: str
    team_lead_user_id: str
    claude_rbac_group_id: str
    gcp_project_id: str
    cost_centre: str


@dataclass(frozen=True)
class Directory:
    users_by_id: Dict[str, User]
    users_by_email: Dict[str, User]
    groups_by_id: Dict[str, Group]
    groups_by_rbac: Dict[str, Group]
    groups_by_project: Dict[str, Group]

    def user(self, user_id: str) -> Optional[User]:
        return self.users_by_id.get(user_id)

    def group_ids(self) -> Tuple[str, ...]:
        return tuple(self.groups_by_id)


def load_directory(directory: Path) -> Directory:
    users_doc = json.loads((directory / "users.json").read_text(encoding="utf-8"))
    groups_doc = json.loads((directory / "groups.json").read_text(encoding="utf-8"))

    users_by_id: Dict[str, User] = {}
    users_by_email: Dict[str, User] = {}
    for raw in users_doc["users"]:
        user = User(
            user_id=raw["user_id"],
            email=raw["email"],
            name=raw["name"],
            role=raw["role"],
            group_ids=tuple(raw["group_ids"]),
        )
        users_by_id[user.user_id] = user
        users_by_email[user.email] = user

    groups_by_id: Dict[str, Group] = {}
    groups_by_rbac: Dict[str, Group] = {}
    groups_by_project: Dict[str, Group] = {}
    for raw in groups_doc["groups"]:
        group = Group(
            group_id=raw["group_id"],
            name=raw["name"],
            team_lead_user_id=raw["team_lead_user_id"],
            claude_rbac_group_id=raw["claude_rbac_group_id"],
            gcp_project_id=raw["gcp_project_id"],
            cost_centre=raw["cost_centre"],
        )
        groups_by_id[group.group_id] = group
        groups_by_rbac[group.claude_rbac_group_id] = group
        groups_by_project[group.gcp_project_id] = group

    return Directory(
        users_by_id=users_by_id,
        users_by_email=users_by_email,
        groups_by_id=groups_by_id,
        groups_by_rbac=groups_by_rbac,
        groups_by_project=groups_by_project,
    )
