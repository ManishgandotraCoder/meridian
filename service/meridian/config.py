"""Environment grants. The YAML files in the starter kit are the source of truth."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import yaml

CAPABILITIES = ("usage-connector", "web-search", "code-execution")
ROLES = ("member", "team_lead", "platform_admin")
DATA_AS_OF = "2026-09-28"  # exclusive end of the export window


@dataclass(frozen=True)
class Environment:
    name: str
    usage_read_roles: tuple
    group_visibility: str
    write_roles: tuple
    capability_defaults: Dict[str, Any]
    server_name: str

    def capability_enabled(self, capability: str, group_id: str) -> bool:
        spec = self.capability_defaults[capability]
        if spec == "enabled":
            return True
        if spec == "disabled":
            return False
        if isinstance(spec, dict) and "enabled_for" in spec:
            return group_id in list(spec["enabled_for"])
        raise ValueError("Unrecognised default for %s: %r" % (capability, spec))


def load_environment(path: Path) -> Environment:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Environment file %s is not a mapping" % path)
    scopes = raw["scopes"]
    read = scopes["usage:read"]
    write = scopes["capabilities:write"]
    visibility = read["group_visibility"]
    if visibility not in ("all", "own_group"):
        raise ValueError("group_visibility must be all or own_group, got %r" % visibility)
    read_roles = tuple(read["roles"])
    write_roles = tuple(write["roles"])
    for role in read_roles + write_roles:
        if role not in ROLES:
            raise ValueError("Unknown role %r in %s" % (role, path))
    defaults = raw["capability_defaults"]
    for capability in CAPABILITIES:
        if capability not in defaults:
            raise ValueError("%s is missing capability %s" % (path, capability))
    return Environment(
        name=str(raw["environment"]),
        usage_read_roles=read_roles,
        group_visibility=visibility,
        write_roles=write_roles,
        capability_defaults=dict(defaults),
        server_name=str(raw["host"]["server_name"]),
    )


def expand_capability_defaults(
    env: Environment, group_ids: list
) -> Dict[str, Dict[str, bool]]:
    """Turn shorthand defaults into an explicit group → enabled map."""
    expanded: Dict[str, Dict[str, bool]] = {}
    for capability in CAPABILITIES:
        expanded[capability] = {
            group_id: env.capability_enabled(capability, group_id) for group_id in group_ids
        }
    return expanded


def environment_path(root: Path, name: str) -> Path:
    return root / "starter-kit" / "environments" / ("%s.yaml" % name)
